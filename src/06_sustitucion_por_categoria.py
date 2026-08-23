"""Paso 6 — Sustitucion por categoria. Es la pregunta de investigacion.

Cruza colorantes depurados contra categorias analiticas y evalua las tres
predicciones que se fijaron ANTES de ver los datos:

  P1  El azul no tiene reemplazo natural viable. Las categorias que dependen de
      E132/E133 no habran sustituido.
  P2  El amarillo hidrosoluble es el cuello de botella. La tartrazina (E102)
      persistira en bebidas mas que otros sinteticos.
  P3  La sustitucion llega como producto nuevo, no como reformulacion. Los
      productos con natural apareceran como referencias distintas.

P1 y P2 se evaluan aqui. P3 requiere emparejar por marca y no se resuelve en
este paso; el script deja preparado el conteo por marca.

Reglas heredadas y no negociables en este paso:
  - El caramelo E150 queda FUERA del eje. No cuenta ni como natural ni sintetico.
  - El carmin E120 se reporta APARTE del agregado natural: su barrera es de
    certificacion, no de estabilidad.
  - Los codigos de origen indeterminado (E101, E170, E171, E100, E160a, E160c,
    E140) solo cuentan si el contexto los avala, igual que en el paso 5.

Salidas: reportes/06_sustitucion.json, 06_matriz_categoria_clase.csv,
         06_predicciones.md
"""
from __future__ import annotations
import re
from collections import Counter, defaultdict
from pathlib import Path
import duckdb, pandas as pd, yaml
from util import (INTERMEDIO, REPORTES, cargar_diccionario, como_lista,
                  construir_matchers, detectar, normalizar, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
AMBIGUOS = {"E101", "E170", "E171", "E100", "E160a", "E160c", "E140"}
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60
N_MINIMO = 30   # celdas con menos productos no se interpretan; se reportan igual


def cargar_categorias() -> dict:
    with open(RAIZ / "config" / "categorias.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clasificar(tags: list[str], cfg: dict) -> str:
    """Devuelve UNA categoria. Primera coincidencia segun el orden de prioridad."""
    t = set(tags)
    if t & set(cfg["excluir"]):
        return "_excluido"
    for nombre, lista in cfg["aparte"].items():
        if t & set(lista):
            return f"_{nombre}"
    for nombre in cfg["prioridad"]:
        if t & set(cfg["categorias"][nombre]["tags"]):
            return nombre
    return "_sin_clasificar"


def con_contexto(texto: str, patron: re.Pattern) -> bool:
    for m in patron.finditer(texto):
        ini, fin = max(0, m.start() - VENTANA), min(len(texto), m.end() + VENTANA)
        if RE_CONTEXTO.search(texto[ini:fin]):
            return True
    return False


def main() -> None:
    cfg = cargar_categorias()
    dic = cargar_diccionario()
    matchers = construir_matchers(dic)
    patrones = {c: p for c, _, p in matchers}
    tono = {**{k: v["tono"] for k, v in dic["sinteticos"].items()},
            **{k: v["tono"] for k, v in dic["naturales"].items()}}

    df = duckdb.sql(f"""
        SELECT code, nombre_producto, ingredientes_texto, categorias, marcas
        FROM '{INTERMEDIO / 'productos_mx.parquet'}'
        WHERE ingredientes_texto IS NOT NULL
          AND length(trim(ingredientes_texto)) > 0
    """).df()

    filas = []
    for t in df.itertuples(index=False):
        tags = [x for x in como_lista(t.categorias) if x.startswith("en:")]
        if not tags:
            continue
        cat = clasificar(tags, cfg)
        texto = normalizar(t.ingredientes_texto)
        det = detectar(texto, matchers)
        eje = {c: k for c, k in det.items() if k in ("sinteticos", "naturales")
               and (c not in AMBIGUOS or con_contexto(texto, patrones[c]))}
        filas.append({
            "code": t.code, "marca": t.marcas, "categoria": cat,
            "sinteticos": {c for c, k in eje.items() if k == "sinteticos"},
            # El carmin sale del agregado natural y se cuenta por su cuenta.
            "naturales": {c for c, k in eje.items() if k == "naturales" and c != "E120"},
            "carmin": "E120" in eje,
        })
    r = pd.DataFrame(filas)
    analizables = r[~r.categoria.str.startswith("_")].copy()

    # --- matriz categoria x clase ---
    filas_mat = []
    for cat, g in analizables.groupby("categoria"):
        n = len(g)
        n_sin = int(g.sinteticos.map(bool).sum())
        n_nat = int(g.naturales.map(bool).sum())
        n_car = int(g.carmin.sum())
        n_amb = int((g.sinteticos.map(bool) & (g.naturales.map(bool) | g.carmin)).sum())
        con_color = int((g.sinteticos.map(bool) | g.naturales.map(bool) | g.carmin).sum())
        filas_mat.append({
            "categoria": cfg["categorias"][cat]["etiqueta"], "clave": cat, "n": n,
            "n_con_colorante": con_color,
            "pct_con_colorante": round(100 * con_color / n, 1),
            "n_sintetico": n_sin, "pct_sintetico": round(100 * n_sin / n, 1),
            "n_natural_sin_carmin": n_nat, "pct_natural": round(100 * n_nat / n, 1),
            "n_carmin": n_car, "pct_carmin": round(100 * n_car / n, 1),
            "n_ambos": n_amb,
            # Indice de sustitucion: entre los que declaran color, que fraccion es
            # solo natural. No mide reformulacion; describe composicion actual.
            "pct_solo_natural_entre_coloreados": (
                round(100 * int(((g.naturales.map(bool) | g.carmin) &
                                 ~g.sinteticos.map(bool)).sum()) / con_color, 1)
                if con_color else None),
            "potencia_suficiente": n >= N_MINIMO,
        })
    mat = pd.DataFrame(filas_mat).sort_values("n", ascending=False)

    # --- P1: azul ---
    azules_sin = {"E131", "E132", "E133"}
    azul_por_cat = {}
    for cat, g in analizables.groupby("categoria"):
        con_azul_sin = int(g.sinteticos.map(lambda s: bool(s & azules_sin)).sum())
        con_azul_nat = int(g.naturales.map(lambda s: "SPIRULINA" in s).sum())
        if con_azul_sin or con_azul_nat:
            azul_por_cat[cfg["categorias"][cat]["etiqueta"]] = {
                "sintetico": con_azul_sin, "natural_espirulina": con_azul_nat}
    tot_azul_sin = sum(v["sintetico"] for v in azul_por_cat.values())
    tot_azul_nat = sum(v["natural_espirulina"] for v in azul_por_cat.values())

    # --- P2: amarillo en bebidas ---
    bebidas = analizables[analizables.categoria == "bebidas_no_alcoholicas"]
    otras = analizables[analizables.categoria != "bebidas_no_alcoholicas"]
    def tasa(g, cod):
        return round(100 * g.sinteticos.map(lambda s: cod in s).sum() / len(g), 2) if len(g) else None
    p2 = {
        "n_bebidas": len(bebidas), "n_otras": len(otras),
        "E102_en_bebidas_pct": tasa(bebidas, "E102"),
        "E102_en_otras_pct": tasa(otras, "E102"),
        "E129_en_bebidas_pct": tasa(bebidas, "E129"),
        "E129_en_otras_pct": tasa(otras, "E129"),
        "amarillo_natural_en_bebidas_pct": round(
            100 * bebidas.naturales.map(
                lambda s: any(tono.get(c) == "amarillo" for c in s)).sum() / len(bebidas), 2
        ) if len(bebidas) else None,
    }

    # --- P3: preparacion, no evaluacion ---
    p3 = {}
    for cat in ("bebidas_no_alcoholicas", "lacteos", "confiteria"):
        g = analizables[analizables.categoria == cat]
        if not len(g):
            continue
        marcas_nat = set(g[g.naturales.map(bool)].marca.dropna())
        marcas_sin = set(g[g.sinteticos.map(bool)].marca.dropna())
        p3[cat] = {"marcas_con_natural": len(marcas_nat),
                   "marcas_con_sintetico": len(marcas_sin),
                   "marcas_con_ambos": len(marcas_nat & marcas_sin)}

    resumen = {
        "n_con_texto_y_categoria": len(r),
        "reparto_universo": Counter(
            r.categoria.map(lambda c: c if c.startswith("_") else "analizable")).most_common(),
        "n_analizables": len(analizables),
        "n_categorias_con_potencia": int(mat.potencia_suficiente.sum()),
        "N_MINIMO": N_MINIMO,
        "matriz": mat.to_dict("records"),
        "P1_azul": {"por_categoria": azul_por_cat,
                    "total_sintetico": tot_azul_sin,
                    "total_espirulina": tot_azul_nat,
                    "veredicto": ("APOYA P1" if tot_azul_nat < max(1, 0.1 * tot_azul_sin)
                                  else "NO APOYA P1")},
        "P2_amarillo": p2,
        "P3_marcas": p3,
        "advertencia": ("El indice de sustitucion describe composicion actual del anaquel "
                        "documentado, NO reformulacion. El diseno es transversal."),
    }

    print(f"  analizables: {len(analizables):,} de {len(r):,} con texto y categoria")
    print(f"  categorias con n >= {N_MINIMO}: {int(mat.potencia_suficiente.sum())}")
    print(f"  P1 azul: {tot_azul_sin} sinteticos vs {tot_azul_nat} espirulina "
          f"-> {resumen['P1_azul']['veredicto']}")
    print(f"  P2 E102 bebidas {p2['E102_en_bebidas_pct']} % vs otras {p2['E102_en_otras_pct']} %")

    guardar_reporte("06_sustitucion", resumen)
    REPORTES.mkdir(exist_ok=True)
    mat.to_csv(REPORTES / "06_matriz_categoria_clase.csv", index=False, encoding="utf-8")
    print(f"-> {REPORTES / '06_matriz_categoria_clase.csv'}")

    sin_clasificar = r[r.categoria == "_sin_clasificar"]
    if len(sin_clasificar) > 0.25 * len(r):
        print(f"\nAVISO: {len(sin_clasificar):,} productos ({100*len(sin_clasificar)/len(r):.0f} %) "
              f"no cayeron en ninguna categoria. Revisa config/categorias.yaml antes de "
              f"interpretar la matriz: el mapeo esta incompleto.")


if __name__ == "__main__":
    main()
