"""Paso 0 — Introspeccion del volcado de Open Food Facts.

El esquema del Parquet cambia entre versiones y varias columnas relevantes
(product_name, ingredients_text) suelen venir anidadas como lista de estructuras
con lang/text. NO asumas nombres ni tipos: corre esto primero y lee la salida.

Uso:
    python src/00_explorar_esquema.py datos/crudo/food.parquet
    python src/00_explorar_esquema.py            # intenta leer del remoto de HF
"""
from __future__ import annotations
import sys
from pathlib import Path
import duckdb
from util import guardar_reporte

REMOTO = ("hf://datasets/openfoodfacts/product-database/food.parquet")

INTERESAN = [
    "code", "product_name", "brands", "brands_tags", "categories_tags",
    "countries_tags", "additives_n", "additives_tags", "ingredients_text",
    "ingredients_tags", "ingredients_analysis_tags", "labels_tags",
    "nova_group", "nutriscore_grade", "created_t", "last_modified_t",
    "creator", "rev", "states_tags", "packaging_tags", "quantity", "owner",
]


def main() -> None:
    origen = sys.argv[1] if len(sys.argv) > 1 else REMOTO
    if not origen.startswith("hf://") and not Path(origen).exists():
        sys.exit(f"No existe: {origen}")

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    print(f"Origen: {origen}\n")

    esquema = con.execute(
        f"SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM '{origen}' LIMIT 0)"
    ).fetchall()

    print(f"{len(esquema)} columnas en el volcado.\n")
    print("Columnas de interes encontradas:")
    presentes = {n: t for n, t in esquema}
    for c in INTERESAN:
        marca = "OK " if c in presentes else "-- "
        print(f"  {marca}{c:32s} {presentes.get(c, 'AUSENTE')}")

    faltan = [c for c in INTERESAN if c not in presentes]
    if faltan:
        print(f"\nATENCION: faltan {len(faltan)}. Busca equivalentes antes de seguir:")
        for c in faltan:
            parecidas = [n for n in presentes if c.split("_")[0] in n][:6]
            print(f"  {c}: {parecidas or 'sin candidatos'}")

    # Anidadas: hay que saber como desanidarlas en los pasos siguientes.
    anidadas = {n: t for n, t in esquema if any(k in t.upper() for k in ("STRUCT", "[]", "MAP"))}
    print(f"\n{len(anidadas)} columnas anidadas. Las relevantes:")
    for n in ("product_name", "ingredients_text", "countries_tags", "additives_tags"):
        if n in anidadas:
            print(f"  {n}: {anidadas[n]}")

    total = con.execute(f"SELECT count(*) FROM '{origen}'").fetchone()[0]
    print(f"\nTotal de productos en el volcado: {total:,}")

    guardar_reporte("00_esquema", {
        "origen": origen,
        "n_columnas": len(esquema),
        "n_productos": total,
        "columnas": {n: t for n, t in esquema},
        "de_interes_ausentes": faltan,
    })
    print("\nSiguiente: 01_subconjunto_mx.py, ajustando el desanidado segun lo de arriba.")


if __name__ == "__main__":
    main()
