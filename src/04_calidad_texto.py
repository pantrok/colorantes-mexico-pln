"""Paso 4 — Calidad de ingredients_text: decide si el pipeline de PLN es viable.

Si el campo esta mayormente vacio, truncado o en ingles, el aporte metodologico
del articulo no se puede construir y hay que saberlo ahora, no en tres meses.

Mide: presencia, longitud, idioma aparente, truncamiento, indicios de OCR,
y densidad de menciones de color.
"""
from __future__ import annotations
import re
from collections import Counter
import duckdb, pandas as pd
from util import (INTERMEDIO, REPORTES, cargar_diccionario, construir_matchers,
                  detectar, normalizar, guardar_reporte)

# Palabras funcionales frecuentes, para distinguir espanol de ingles sin dependencias.
ES = {"agua", "azucar", "sal", "aceite", "harina", "leche", "acido", "y", "de",
      "con", "colorante", "saborizante", "conservador", "almidon", "jarabe"}
EN = {"water", "sugar", "salt", "oil", "flour", "milk", "acid", "and", "with",
      "color", "flavor", "preservative", "starch", "syrup", "contains"}

# Indicios de reconocimiento optico defectuoso o captura sucia.
RE_OCR = re.compile(r"[|¦~^`]{1,}|\b[a-z]{1,2}\d{2,}[a-z]{1,2}\b|\s{4,}")
RE_TRUNCADO = re.compile(r"(\.\.\.|…)\s*$|[a-z,]\s*$")


def idioma(texto_norm: str) -> str:
    fichas = set(texto_norm.split())
    es, en = len(fichas & ES), len(fichas & EN)
    if es == en == 0:
        return "indeterminado"
    return "es" if es > en else ("en" if en > es else "mixto")


def main() -> None:
    ruta = INTERMEDIO / "productos_mx.parquet"
    if not ruta.exists():
        raise SystemExit("Falta productos_mx.parquet. Corre 01 primero.")

    df = duckdb.sql(f"SELECT code, ingredientes_texto, idioma_ingredientes FROM '{ruta}'").df()
    n = len(df)
    con_texto = df[df.ingredientes_texto.notna() &
                   (df.ingredientes_texto.astype(str).str.strip() != "")].copy()

    con_texto["norm"] = con_texto.ingredientes_texto.map(normalizar)
    con_texto["n_car"] = con_texto.ingredientes_texto.astype(str).str.len()
    con_texto["idioma_inferido"] = con_texto.norm.map(idioma)
    con_texto["posible_ocr"] = con_texto.ingredientes_texto.astype(str).map(
        lambda t: bool(RE_OCR.search(t)))
    con_texto["posible_truncado"] = con_texto.ingredientes_texto.astype(str).str.strip().map(
        lambda t: bool(RE_TRUNCADO.search(t)) and len(t) > 30)

    dic = cargar_diccionario()
    matchers = construir_matchers(dic)
    con_texto["n_colorantes"] = con_texto.norm.map(lambda t: len(detectar(t, matchers)))

    q = con_texto.n_car.quantile([.05, .25, .5, .75, .95]).round(0).to_dict()
    resumen = {
        "n_total_mx": n,
        "n_con_texto": len(con_texto),
        "pct_con_texto": round(100 * len(con_texto) / n, 1) if n else 0,
        "longitud_caracteres": {f"p{int(k*100)}": int(v) for k, v in q.items()},
        "pct_muy_corto_menos_30_car": round(
            100 * (con_texto.n_car < 30).sum() / len(con_texto), 1),
        "idioma_inferido": {k: round(100 * v / len(con_texto), 1)
                            for k, v in Counter(con_texto.idioma_inferido).items()},
        "idioma_declarado_en_volcado": {
            str(k): int(v) for k, v in Counter(df.idioma_ingredientes.fillna("nulo")).items()},
        "pct_posible_ocr": round(100 * con_texto.posible_ocr.sum() / len(con_texto), 1),
        "pct_posible_truncado": round(100 * con_texto.posible_truncado.sum() / len(con_texto), 1),
        "pct_con_al_menos_un_colorante": round(
            100 * (con_texto.n_colorantes > 0).sum() / len(con_texto), 1),
        "colorantes_por_producto_media": round(float(con_texto.n_colorantes.mean()), 2),
    }
    for k, v in resumen.items():
        print(f"  {k}: {v}")

    guardar_reporte("04_calidad_texto", resumen)

    REPORTES.mkdir(exist_ok=True)
    sospechosos = con_texto[con_texto.posible_ocr | con_texto.posible_truncado |
                            (con_texto.idioma_inferido == "en")]
    sospechosos.head(300)[["code", "ingredientes_texto", "idioma_inferido",
                           "posible_ocr", "posible_truncado"]].to_csv(
        REPORTES / "04_textos_sospechosos.csv", index=False, encoding="utf-8")
    print(f"-> {REPORTES / '04_textos_sospechosos.csv'}")

    # Semaforo explicito: el criterio se fija aqui, antes de ver el resultado.
    pct = resumen["pct_con_texto"]
    veredicto = ("VIABLE" if pct >= 60 else
                 "VIABLE CON RESERVAS" if pct >= 35 else
                 "NO VIABLE — replantear el aporte metodologico")
    print(f"\nVeredicto de viabilidad del PLN: {veredicto} ({pct} % con texto)")
    print("Umbrales fijados antes de correr: >=60 viable, 35-60 con reservas, <35 no viable.")


if __name__ == "__main__":
    main()
