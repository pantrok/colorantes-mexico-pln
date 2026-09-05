"""Paso 11 — QUE HACE QUE OPEN FOOD FACTS RECUPERE UNA DECLARACION.

    python src/11_estructura_declaracion.py --pais en:mexico
    python src/11_estructura_declaracion.py --pais en:spain --crudo datos/crudo/food.parquet

POR QUE. La corrida del 27 dejo un resultado que ninguno de los dos mecanismos
que teniamos explica:

    carmin, brecha        Mexico 95.5 %   Espana 32.1 %    diferencia -63.4 pp
    cobertura vocabulario Mexico 96.4 %   Espana 97.4 %    practicamente igual

Mismo codigo, mismos terminos, misma regla `mandatory_additive_class`. Lo unico
distinto es como esta escrita la etiqueta. Hay dos explicaciones y hay que
separarlas antes de escribir una linea de la Introduccion:

  H1  ESTRUCTURA NORMATIVA. El Reglamento (CE) 1333/2008 obliga en la UE a
      declarar «categoria funcional + nombre o numero E» — «colorante: carmin».
      La NOM-051 y el articulo DECIMOSEGUNDO del Acuerdo obligan en Mexico solo
      al nombre comun, sin exigir la clase. La regla de OFF esta calibrada a la
      convencion europea, asi que el texto espanol la satisface y el mexicano no.

  H2  EL CODIGO EN EL TEXTO. Mas simple: en Espana se imprime «E120» y OFF lo
      reconoce por el codigo, sin necesitar la clase declarada.

Las dos predicen la misma diferencia agregada. Se distinguen mirando, dentro de
las detecciones recuperadas, DE DONDE viene la recuperacion.

CONTRA-EVIDENCIA QUE YA TENEMOS Y HAY QUE EXPLICAR. Los naturales sujetos a la
regla estan al 100 % de brecha en LOS DOS paises (Espana n=911 y n=184). Si en
Espana la clase funcional se declarara siempre, no deberian fallar. O sea que H1
en su version simple no basta, y puede que la respuesta sea por sustancia y no
por pais. El script reporta por codigo para poder verlo.

QUE MIDE. Para cada deteccion, dos marcas sobre el texto, independientes:

  tiene_codigo   el codigo E o SIN aparece en el texto, en cualquier posicion
  tiene_clase    'colorante'/'color'/'colour'/'pigmento' aparece ANTES del
                 termino y a menos de VENTANA_CLASE caracteres

Y las cruza contra si OFF etiqueto el codigo. La tabla resultante dice cual de
las dos marcas predice la recuperacion.

MARCA RETIRADA (parche 8, opcion B). Hubo una tercera marca, tiene_dos_puntos,
para detectar la forma europea «colorante: carmin». Salio 0.0 % en los DOS
paises, y eso no era un resultado: era un fallo de medicion. `normalizar()`
quita la puntuacion (incluidos los dos puntos) antes de que esta funcion
reciba el texto, asi que el caracter que la marca buscaba ya no podia existir
nunca. Se opto por quitarla en vez de repararla sobre el texto crudo, porque
la pregunta que motivaba la marca -si Espana usa la forma "colorante: X"- ya
quedo contestada por otro lado: tiene_clase (que si funciona, no depende de
puntuacion) muestra que declarar la clase funcional no predice la
recuperacion en ninguno de los dos paises. Una tercera marca mal medida solo
abria flanco sin cambiar el veredicto.

Salidas: reportes/11_estructura_<pais>.json
         11_estructura_<pais>.csv
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
EXTERNO = RAIZ / "datos" / "externo"
AMBIGUOS = REQUIEREN_CONTEXTO
VENTANA_CLASE = 40          # caracteres ANTES del termino donde buscar la clase
RE_CLASE = re.compile(r"colorantes?|colou?res?\b|pigmentos?")
CARMIN = "E120"
MINERALES = {"E170", "E171", "E172"}

COLUMNAS = {
    "code": ["code", "codigo"],
    "texto": ["ingredients_text", "ingredientes_texto"],
    "aditivos": ["additives_tags", "aditivos_tags"],
    "paises": ["countries_tags", "paises_tags"],
}


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def variantes(codigo: str) -> list[str]:
    k = norma(codigo).replace(" ", "")
    return [k] + [k + s for s in ("i", "ii", "iii", "iv", "a", "b", "c", "d", "e", "f")]


def leer_mandatory(ruta: Path) -> set[str]:
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Ver datos/externo/LEEME.md")
    mand = set()
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        m = re.search(r"^en:\s*(.+)$", bloque, re.M)
        if m and "mandatory_additive_class" in bloque:
            mand.add(norma(m.group(1).split(",")[0]).replace(" ", "")
                     .replace("(", "").replace(")", ""))
    return mand


def patron_codigo(codigo: str) -> re.Pattern:
    """Busca el codigo en el texto en sus formas usuales: e120, e 120, sin 120,
    ins 120, y con subletra opcional."""
    num = re.sub(r"\D", "", codigo)
    if not num:
        return re.compile(r"(?!x)x")          # nunca coincide
    return re.compile(rf"\b(?:e|sin|ins)\s*-?\s*{num}\s*\(?\s*[ivx]{{0,3}}[a-f]?\s*\)?")


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral_inorganico"
    return {"sinteticos": "sintetico", "naturales": "natural_botanico"}.get(bloque, "fuera")


def resolver(cols):
    hallado, faltan = {}, []
    for logico, cands in COLUMNAS.items():
        for c in cands:
            if c in cols:
                hallado[logico] = c
                break
        else:
            faltan.append(logico)
    if faltan:
        raise SystemExit(f"Faltan columnas {faltan}. Hay:\n  " + "\n  ".join(cols))
    return hallado


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="en:mexico")
    ap.add_argument("--crudo", default=None,
                    help="si se omite y el pais es mexico, usa el parquet intermedio")
    args = ap.parse_args()
    etiqueta = args.pais.replace("en:", "")

    if args.crudo:
        ruta, filtrar = Path(args.crudo), True
    elif etiqueta == "mexico" and (INTERMEDIO / "productos_mx.parquet").exists():
        ruta, filtrar = INTERMEDIO / "productos_mx.parquet", False
    else:
        cand = sorted((RAIZ / "datos" / "crudo").glob("*.parquet"))
        if not cand:
            raise SystemExit("Pasa --crudo con la ruta del volcado.")
        ruta, filtrar = cand[0], True

    esquema = {r[0]: r[1] for r in duckdb.sql(f"DESCRIBE SELECT * FROM '{ruta}' LIMIT 0").fetchall()}
    col = resolver(list(esquema.keys())) if filtrar else {
        "code": "code", "texto": "ingredientes_texto",
        "aditivos": "aditivos_tags", "paises": None}
    # El volcado crudo global trae ingredients_text anidado como lista de
    # STRUCT(lang, text) -igual que en 01_subconjunto_mx.py y 09_replica_pais.py-,
    # mientras que el intermedio ya viene aplanado a VARCHAR. Se detecta por el
    # tipo declarado, no por el nombre de columna.
    def expr(nombre: str) -> str:
        tipo = esquema.get(nombre, "").upper()
        if "STRUCT" in tipo and "[]" in tipo:
            return f"""coalesce(
                list_filter({nombre}, x -> x.lang = 'es')[1].text,
                list_filter({nombre}, x -> x.lang = 'main')[1].text,
                try({nombre}[1].text)
            ) AS {nombre}"""
        return nombre

    proyeccion = ", ".join(expr(v) for v in sorted({v for v in col.values() if v}))
    where = (f"list_contains({col['paises']}, '{args.pais}') AND " if filtrar else "")
    df = duckdb.sql(f"""
        SELECT * FROM (SELECT {proyeccion} FROM '{ruta}')
        WHERE {where} {col['texto']} IS NOT NULL
          AND length(trim({col['texto']})) > 0
    """).df()
    print(f"  {etiqueta}: {len(df):,} productos con texto")

    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)
    mand_off = leer_mandatory(EXTERNO / "additives.txt")
    es_mand = {cod: any(k in mand_off for k in variantes(cod))
               for _, cod, _ in ordenados}
    pat_cod = {cod: patron_codigo(cod) for _, cod, _ in ordenados}

    # CORREGIDO 05/09. Antes se emitia una fila por cada TERMINO que coincidia
    # con `restante`, sin agrupar por codigo. Como `ordenados` recorre todos
    # los sinonimos y `restante` solo descarta el tramo de texto ya consumido
    # -no el codigo entero-, un producto que trae dos sinonimos del mismo
    # colorante en puntos distintos del texto (p. ej. "cochinilla" en un lado
    # y "carmin" en otro, ambos E120) contaba dos veces para ese codigo. Es
    # el mismo bug encontrado y corregido en 07_forma_y_clase.py,
    # 08_vocabulario_off.py y 09_replica_pais.py; aqui era especialmente
    # delicado porque el guion de este script es precisamente la comparacion
    # de carmin entre paises. Ahora se agrupa por (producto, codigo) y
    # `tiene_clase` se combina con OR entre los terminos que coincidieron
    # -"tiene_codigo" y "en_tags" ya son por codigo, no dependen del termino-.
    # Detalle en BITACORA_PARCHES.md.
    filas = []
    for t in df.itertuples(index=False):
        texto = normalizar(getattr(t, col["texto"]))
        tags = {str(a).replace("en:", "").upper()
                for a in como_lista(getattr(t, col["aditivos"]))}
        restante = texto
        por_codigo = {}
        for termino, codigo, bloque in ordenados:
            if not termino:
                continue
            cl = clase_de(codigo, bloque)
            if cl == "fuera":
                continue
            pat = re.compile(r"\b" + re.escape(termino) + r"\b")
            m = pat.search(restante)
            if not m:
                continue
            restante = pat.sub(" ", restante)

            ini = max(0, m.start() - VENTANA_CLASE)
            antes = texto[ini:m.start()]
            mc = None
            for mm in RE_CLASE.finditer(antes):
                mc = mm
            entry = por_codigo.setdefault(codigo, {
                "clase": cl, "termino": termino, "tiene_clase": False})
            if mc is not None:
                entry["tiene_clase"] = True
        for codigo, info in por_codigo.items():
            filas.append({
                "code": t.code, "codigo": codigo, "clase": info["clase"],
                "termino": info["termino"],
                "sujeto_a_regla": bool(es_mand.get(codigo)),
                "tiene_codigo": bool(pat_cod[codigo].search(texto)),
                "tiene_clase": info["tiene_clase"],
                "en_tags": codigo in tags,
            })

    p = pd.DataFrame(filas)
    if p.empty:
        raise SystemExit("Cero detecciones.")
    # depuracion: mismo criterio que el resto de la tuberia
    p = p[~(p.codigo.isin(AMBIGUOS) & ~p.tiene_clase)]

    def tasa(sub):
        n = len(sub)
        return {"n": n, "recuperadas": int(sub.en_tags.sum()),
                "pct_recuperado": round(100 * sub.en_tags.mean(), 1) if n else None}

    # --- la tabla que decide entre H1 y H2
    decide = (p.groupby(["tiene_codigo", "tiene_clase"])
                .agg(n=("en_tags", "size"), recuperadas=("en_tags", "sum"))
                .reset_index())
    decide["pct_recuperado"] = (100 * decide.recuperadas / decide.n).round(1)

    # --- solo los sujetos a la regla, que es donde deberia notarse
    reg = p[p.sujeto_a_regla]
    decide_reg = (reg.groupby(["tiene_codigo", "tiene_clase"])
                    .agg(n=("en_tags", "size"), recuperadas=("en_tags", "sum"))
                    .reset_index())
    if len(decide_reg):
        decide_reg["pct_recuperado"] = (100 * decide_reg.recuperadas / decide_reg.n).round(1)

    # --- por codigo: por si la respuesta es por sustancia y no por pais
    porcod = (p.groupby(["codigo", "clase", "sujeto_a_regla"])
                .agg(n=("en_tags", "size"),
                     pct_con_codigo=("tiene_codigo", lambda s: round(100 * s.mean(), 1)),
                     pct_con_clase=("tiene_clase", lambda s: round(100 * s.mean(), 1)),
                     pct_recuperado=("en_tags", lambda s: round(100 * s.mean(), 1)))
                .reset_index().sort_values("n", ascending=False))

    prevalencia = {
        "pct_detecciones_con_codigo_en_texto": round(100 * p.tiene_codigo.mean(), 1),
        "pct_con_clase_declarada_antes": round(100 * p.tiene_clase.mean(), 1),
    }

    veredicto = {}
    try:
        solo_cod = decide[(decide.tiene_codigo) & (~decide.tiene_clase)].pct_recuperado.iloc[0]
        solo_cls = decide[(~decide.tiene_codigo) & (decide.tiene_clase)].pct_recuperado.iloc[0]
        ninguna = decide[(~decide.tiene_codigo) & (~decide.tiene_clase)].pct_recuperado.iloc[0]
        veredicto = {
            "solo_codigo_pct": float(solo_cod), "solo_clase_pct": float(solo_cls),
            "ninguna_pct": float(ninguna),
            "apoya": ("H2 el codigo en el texto" if solo_cod - ninguna > solo_cls - ninguna
                      else "H1 la clase declarada"),
            "nota": ("Se compara cuanto sube la recuperacion respecto de las detecciones "
                     "que no traen ni codigo ni clase. La marca que mas la suba es el "
                     "mecanismo."),
        }
    except (IndexError, KeyError):
        veredicto = {"error": "faltan celdas para comparar; revisa la tabla completa"}

    REPORTES.mkdir(exist_ok=True)
    porcod.to_csv(REPORTES / f"11_estructura_{etiqueta}.csv", index=False, encoding="utf-8")
    guardar_reporte(f"11_estructura_{etiqueta}", {
        "pais": args.pais, "fuente": str(ruta),
        "n_detecciones": len(p),
        "prevalencia_de_las_marcas": prevalencia,
        "tabla_decisoria": decide.to_dict("records"),
        "tabla_decisoria_solo_sujetos_a_la_regla": decide_reg.to_dict("records") if len(decide_reg) else None,
        "por_codigo": porcod.to_dict("records"),
        "por_clase": {cl: tasa(g) for cl, g in p.groupby("clase")},
        "VEREDICTO": veredicto,
        "advertencia": ("`tiene_codigo` mira todo el texto, no la vecindad del termino: "
                        "un producto con varios aditivos puede traer el codigo de OTRO. "
                        "Es una cota superior."),
    })

    print(f"\n  marcas sobre {len(p)} detecciones: {prevalencia}")
    print("\n  tabla decisoria (todas):\n", decide.to_string(index=False))
    if len(decide_reg):
        print("\n  solo sujetos a mandatory_additive_class:\n",
              decide_reg.to_string(index=False))
    print(f"\n  VEREDICTO: {veredicto.get('apoya', veredicto)}")
    print("\n  por codigo (top 12):\n", porcod.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
