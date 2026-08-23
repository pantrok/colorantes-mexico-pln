"""Paso 2 — LA BRECHA. El numero que decide el encuadre del articulo.

Pregunta: de los productos mexicanos cuyo texto de ingredientes menciona un
colorante por nombre, cuantos NO lo tienen declarado en additives_tags?

La Dra. Granados-Balbuena senala que en Mexico las etiquetas declaran por nombre
de compuesto ('extracto de betalaina', 'acido carminico') y no por codigo E.
Si eso es asi, additives_tags —construido sobre coincidencia de codigos— pierde
informacion de forma sistematica, y esa perdida es el aporte del articulo.

Salidas:
  reportes/02_brecha_tags.json
  reportes/02_brecha_ejemplos.csv   <- muestra para revision manual
"""
from __future__ import annotations
from collections import Counter, defaultdict
import duckdb, pandas as pd
from util import (INTERMEDIO, REPORTES, cargar_diccionario, construir_matchers,
                  detectar, normalizar, guardar_reporte)

SEMILLA = 20260823   # muestra reproducible
N_EJEMPLOS = 400     # tamano de la muestra para revision manual


def main() -> None:
    ruta = INTERMEDIO / "productos_mx.parquet"
    if not ruta.exists():
        raise SystemExit("Falta datos/intermedio/productos_mx.parquet. Corre 01 primero.")

    df = duckdb.sql(f"""
        SELECT code, nombre_producto, ingredientes_texto, aditivos_tags,
               categorias, marcas
        FROM '{ruta}'
        WHERE ingredientes_texto IS NOT NULL
          AND length(trim(ingredientes_texto)) > 0
    """).df()
    print(f"Productos con texto de ingredientes: {len(df):,}")

    dic = cargar_diccionario()
    matchers = construir_matchers(dic)
    genericos = dic["genericos"]["terminos_norm"]

    filas = []
    for t in df.itertuples(index=False):
        texto = normalizar(t.ingredientes_texto)
        detectados = detectar(texto, matchers)
        aditivos = t.aditivos_tags if t.aditivos_tags is not None else []
        tags = {str(a).replace("en:", "").upper() for a in aditivos}
        en_texto = set(detectados)
        # Solo cuentan los del eje de sustitucion: caramelo queda fuera por decision.
        eje = {c for c in en_texto if detectados[c] in ("sinteticos", "naturales")}
        filas.append({
            "code": t.code,
            "nombre": t.nombre_producto,
            "categorias": t.categorias,
            "marcas": t.marcas,
            "en_texto": sorted(en_texto),
            "en_eje": sorted(eje),
            "en_tags": sorted(tags & set(dic["sinteticos"]) | tags & set(dic["naturales"])),
            "solo_en_texto": sorted(eje - tags),
            "solo_en_tags": sorted((tags & (set(dic["sinteticos"]) | set(dic["naturales"]))) - eje),
            "generico_sin_sustancia": any(g in texto for g in genericos) and not eje,
        })
    res = pd.DataFrame(filas)

    con_texto = res[res.en_eje.map(bool)]
    con_brecha = con_texto[con_texto.solo_en_texto.map(bool)]
    n_ct, n_cb = len(con_texto), len(con_brecha)

    por_codigo = Counter(c for l in con_texto.solo_en_texto for c in l)
    detectados_txt = Counter(c for l in con_texto.en_eje for c in l)
    brecha_rel = {c: round(100 * por_codigo[c] / detectados_txt[c], 1)
                  for c in detectados_txt if detectados_txt[c] >= 10}

    resumen = {
        "n_con_texto_ingredientes": len(df),
        "n_con_colorante_en_texto": n_ct,
        "n_con_brecha": n_cb,
        "PCT_BRECHA": round(100 * n_cb / n_ct, 1) if n_ct else None,
        "n_solo_en_tags": int(res.solo_en_tags.map(bool).sum()),
        "n_generico_sin_sustancia": int(res.generico_sin_sustancia.sum()),
        "codigos_mas_perdidos": por_codigo.most_common(15),
        "brecha_relativa_por_codigo_pct": dict(
            sorted(brecha_rel.items(), key=lambda x: -x[1])),
        "nota": ("PCT_BRECHA es la proporcion de productos con colorante nombrado en el "
                 "texto que no lo tienen en additives_tags. Es el numero de portada. "
                 "'solo_en_tags' es el caso inverso y sirve de control: si es alto, el "
                 "diccionario semilla esta incompleto, no additives_tags."),
    }
    for k, v in resumen.items():
        if k != "nota":
            print(f"  {k}: {v}")

    guardar_reporte("02_brecha_tags", resumen)

    # Muestra para revision manual: es la semilla del conjunto anotado.
    REPORTES.mkdir(exist_ok=True)
    muestra = con_brecha.sample(min(N_EJEMPLOS, n_cb), random_state=SEMILLA) if n_cb else con_brecha
    muestra_out = muestra[["code", "nombre", "solo_en_texto", "en_tags"]].copy()
    muestra_out = muestra_out.merge(df[["code", "ingredientes_texto"]], on="code", how="left")
    muestra_out.to_csv(REPORTES / "02_brecha_ejemplos.csv", index=False, encoding="utf-8")
    print(f"-> {REPORTES / '02_brecha_ejemplos.csv'} ({len(muestra_out)} filas)")

    print("\nLee la muestra a mano antes de creerte el porcentaje. Falsos positivos "
          "esperables: 'curcuma' como especia, 'extracto de zanahoria' como ingrediente. "
          "Si abundan, el numero honesto es menor y hay que ajustar el diccionario "
          "ANTES de reportar nada.")


if __name__ == "__main__":
    main()
