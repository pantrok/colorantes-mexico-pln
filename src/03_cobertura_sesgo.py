"""Paso 3 — Cobertura y sesgo del subconjunto mexicano (Riesgo 1 del brief).

Open Food Facts es una muestra de conveniencia autoseleccionada. Este paso no la
corrige: la caracteriza, que es lo unico defendible. Produce las cifras con las
que se redacta el parrafo de limitaciones y, de paso, una comparacion de cobertura
que no existe publicada para ningun pais.

Referencias externas de cobertura:
  Contreras-Manzano et al. 2022, PLOS Medicine — censo INSP, 38 872 productos
  Zancheta et al. 2025, Globalization and Health — 15 846 productos MX (2017)
"""
from __future__ import annotations
from collections import Counter
import duckdb, pandas as pd
from util import INTERMEDIO, REPORTES, guardar_reporte

CENSO_INSP = 38872
CENSO_ZANCHETA = 15846


def gini(valores) -> float:
    """Concentracion 0 (uniforme) a 1 (todo en uno). Para marcas y contribuidores."""
    v = sorted(x for x in valores if x > 0)
    n = len(v)
    if n == 0:
        return float("nan")
    acum = sum((2 * i - n - 1) * x for i, x in enumerate(v, 1))
    return round(acum / (n * sum(v)), 3)


def main() -> None:
    ruta = INTERMEDIO / "productos_mx.parquet"
    if not ruta.exists():
        raise SystemExit("Falta productos_mx.parquet. Corre 01 primero.")

    df = duckdb.sql(f"SELECT * FROM '{ruta}'").df()
    n = len(df)

    # --- concentracion por marca y por contribuidor ---
    marcas = Counter(m for m in df.marcas.dropna() if str(m).strip())
    contrib = Counter(c for c in df.contribuidor.dropna() if str(c).strip())

    def top_share(cnt, k):
        return round(100 * sum(v for _, v in cnt.most_common(k)) / max(sum(cnt.values()), 1), 1)

    # --- categorias: se usa la etiqueta de primer nivel para no fragmentar ---
    cats = Counter()
    for lista in df.categorias.dropna():
        for c in (lista if isinstance(lista, (list, tuple)) else []):
            if str(c).startswith("en:"):
                cats[str(c)] += 1
    top_cats = cats.most_common(40)

    # --- actividad de contribucion en el tiempo ---
    # OJO: esto NO es reformulacion. Es actividad de la comunidad. Etiquetar asi
    # cualquier grafica que salga de aqui (ver CLAUDE.md).
    altas = duckdb.sql(f"""
        SELECT year(to_timestamp(alta_ts)) AS anio, count(*) AS n
        FROM '{ruta}' WHERE alta_ts IS NOT NULL GROUP BY 1 ORDER BY 1
    """).df()

    # --- completitud campo por campo ---
    completitud = {
        c: round(100 * df[c].notna().sum() / n, 1)
        for c in ["nombre_producto", "ingredientes_texto", "aditivos_tags",
                  "categorias", "marcas", "nova", "nutriscore"]
        if c in df.columns
    }

    resumen = {
        "n_productos_mx": n,
        "cobertura_vs_censo_INSP_pct": round(100 * n / CENSO_INSP, 1),
        "cobertura_vs_Zancheta_pct": round(100 * n / CENSO_ZANCHETA, 1),
        "advertencia_cobertura": ("Las razones anteriores comparan conteos, no universos. "
                                  "El censo del INSP se levanto en autoservicio en 2016-2017; "
                                  "OFF acumula desde 2012 sin marco muestral. Sirve como orden "
                                  "de magnitud, no como tasa de cobertura formal."),
        "n_marcas": len(marcas),
        "pct_top10_marcas": top_share(marcas, 10),
        "pct_top50_marcas": top_share(marcas, 50),
        "gini_marcas": gini(marcas.values()),
        "n_contribuidores": len(contrib),
        "pct_top10_contribuidores": top_share(contrib, 10),
        "gini_contribuidores": gini(contrib.values()),
        "top20_marcas": marcas.most_common(20),
        "top20_contribuidores": contrib.most_common(20),
        "top40_categorias": top_cats,
        "completitud_pct": completitud,
        "altas_por_anio": altas.to_dict("records"),
        "nota_altas": "Actividad de contribucion, NO reformulacion de producto.",
    }

    print(f"  productos MX: {n:,}")
    print(f"  vs censo INSP: {resumen['cobertura_vs_censo_INSP_pct']} %")
    print(f"  top-10 contribuidores aportan: {resumen['pct_top10_contribuidores']} %")
    print(f"  gini contribuidores: {resumen['gini_contribuidores']}")
    print(f"  top-10 marcas: {resumen['pct_top10_marcas']} %")

    guardar_reporte("03_cobertura_sesgo", resumen)

    REPORTES.mkdir(exist_ok=True)
    pd.DataFrame(top_cats, columns=["categoria", "n"]).to_csv(
        REPORTES / "03_categorias.csv", index=False, encoding="utf-8")
    print(f"-> {REPORTES / '03_categorias.csv'}")

    if resumen["pct_top10_contribuidores"] > 50:
        print("\nAVISO: mas de la mitad del subconjunto viene de diez cuentas. "
              "Eso hay que declararlo en el resumen del articulo, no en una nota al pie.")


if __name__ == "__main__":
    main()
