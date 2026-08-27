"""Paso 1 — Extraccion del subconjunto mexicano.

Filtra por countries_tags que contenga 'en:mexico', desanida los campos de texto
multiidioma y guarda un parquet manejable en datos/intermedio/.

Los productos multipais SE INCLUYEN, con una bandera 'solo_mexico' que permite
repetir cualquier analisis restringiendo a los exclusivos. Esa decision se declara
en Metodos; excluirlos sesgaria contra las marcas transnacionales, que son
justamente las que mas reformulan.

IMPORTANTE: las expresiones de desanidado dependen del esquema. Corre antes
00_explorar_esquema.py y ajusta EXPR_* si tu version del volcado difiere.
"""
from __future__ import annotations
import sys, json, hashlib, datetime as dt
from pathlib import Path
import duckdb
from util import INTERMEDIO, guardar_reporte

# --- expresiones de desanidado; verificar contra la salida del paso 0 ---
# Caso habitual: lista de STRUCT(lang VARCHAR, text VARCHAR).
EXPR_NOMBRE = """
  coalesce(
    list_filter(product_name, x -> x.lang = 'es')[1].text,
    list_filter(product_name, x -> x.lang = 'main')[1].text,
    try(product_name[1].text)
  )"""
EXPR_INGREDIENTES = """
  coalesce(
    list_filter(ingredients_text, x -> x.lang = 'es')[1].text,
    list_filter(ingredients_text, x -> x.lang = 'main')[1].text,
    try(ingredients_text[1].text)
  )"""
EXPR_IDIOMA_ING = """
  coalesce(
    CASE WHEN list_filter(ingredients_text, x -> x.lang = 'es')[1].text IS NOT NULL
         THEN 'es' END,
    try(ingredients_text[1].lang)
  )"""


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Uso: python src/01_subconjunto_mx.py <ruta_o_url_del_volcado>")
    origen = sys.argv[1]
    INTERMEDIO.mkdir(parents=True, exist_ok=True)
    salida = INTERMEDIO / "productos_mx.parquet"

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    # La lectura del volcado remoto es larga; sin esto la conexion se cae a
    # mitad de camino en redes inestables.
    con.execute("SET http_retries=10;")
    con.execute("SET http_retry_wait_ms=2000;")
    con.execute("SET http_retry_backoff=2;")
    con.execute("SET http_timeout=120;")
    con.execute("SET http_keep_alive=false;")

    consulta = f"""
    SELECT
      code,
      {EXPR_NOMBRE}        AS nombre_producto,
      {EXPR_INGREDIENTES}  AS ingredientes_texto,
      {EXPR_IDIOMA_ING}    AS idioma_ingredientes,
      brands               AS marcas,
      categories_tags      AS categorias,
      countries_tags       AS paises,
      len(countries_tags) = 1 AS solo_mexico,
      additives_tags       AS aditivos_tags,
      additives_n          AS aditivos_n,
      -- OFF desvia vitaminas y minerales fuera de additives_tags por diseno
      -- (issue #1131), aunque tengan numero E. Sin esto, E101 y E170 se
      -- miden como "perdidos" por buscarlos en el campo equivocado.
      vitamins_tags        AS vitaminas_tags,
      minerals_tags        AS minerales_tags,
      labels_tags          AS etiquetas,
      nova_group           AS nova,
      nutriscore_grade     AS nutriscore,
      created_t            AS alta_ts,          -- alta del CONTRIBUIDOR, no reformulacion
      last_modified_t      AS modificado_ts,
      rev                  AS revisiones,
      creator              AS contribuidor
    FROM '{origen}'
    WHERE list_contains(countries_tags, 'en:mexico')
    """
    print("Extrayendo subconjunto mexicano...")
    con.execute(f"COPY ({consulta}) TO '{salida}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    r = con.execute(f"""
      SELECT count(*) n,
             count(*) FILTER (WHERE solo_mexico) n_solo_mx,
             count(*) FILTER (WHERE ingredientes_texto IS NOT NULL
                              AND length(trim(ingredientes_texto)) > 0) n_con_texto,
             count(*) FILTER (WHERE aditivos_tags IS NOT NULL
                              AND len(aditivos_tags) > 0) n_con_aditivos,
             count(*) FILTER (WHERE vitaminas_tags IS NOT NULL
                              AND len(vitaminas_tags) > 0) n_con_vitaminas,
             count(*) FILTER (WHERE minerales_tags IS NOT NULL
                              AND len(minerales_tags) > 0) n_con_minerales,
             count(DISTINCT contribuidor) n_contribuidores,
             count(DISTINCT marcas) n_marcas
      FROM '{salida}'
    """).fetchone()

    resumen = {
        "fecha_extraccion": dt.datetime.now().isoformat(timespec="seconds"),
        "origen": origen,
        "n_productos_mx": r[0],
        "n_solo_mexico": r[1],
        "n_multipais": r[0] - r[1],
        "n_con_ingredients_text": r[2],
        "pct_con_ingredients_text": round(100 * r[2] / r[0], 1) if r[0] else 0,
        "n_con_additives_tags": r[3],
        "pct_con_additives_tags": round(100 * r[3] / r[0], 1) if r[0] else 0,
        "n_con_vitamins_tags": r[4],
        "n_con_minerals_tags": r[5],
        "n_contribuidores_distintos": r[6],
        "n_marcas_distintas": r[7],
        "archivo": str(salida),
        "bytes": salida.stat().st_size,
    }
    for k, v in resumen.items():
        print(f"  {k}: {v}")

    # Procedencia: hay que poder decir en Metodos exactamente que volcado se uso.
    proc = {"origen": origen, "fecha": resumen["fecha_extraccion"],
            "licencia": "ODbL — Open Food Facts. Citar y respetar atribucion compartida.",
            "sha256_salida": hashlib.sha256(salida.read_bytes()).hexdigest()}
    (Path(__file__).resolve().parents[1] / "reportes").mkdir(exist_ok=True)
    (Path(__file__).resolve().parents[1] / "reportes" / "procedencia.json").write_text(
        json.dumps(proc, ensure_ascii=False, indent=2), encoding="utf-8")

    guardar_reporte("01_subconjunto_mx", resumen)


if __name__ == "__main__":
    main()
