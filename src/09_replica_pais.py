"""Paso 9 — REPLICA EN OTRO PAIS. La prueba directa del mecanismo.

    python src/09_replica_pais.py --pais en:spain
    python src/09_replica_pais.py --pais en:spain --crudo datos/crudo/off.parquet

QUE PRUEBA. El modelo del paso 8 dice que el factor dominante de la brecha es
que el termino no este en el vocabulario espanol de Open Food Facts, con una
razon de momios de ~23. Ese vocabulario esta escrito en espanol iberico: dice
"pimenton" y no "paprika", no tiene "extracto de achiote" ni "atsuete" ni
"extracto de betalaina".

De ahi sale una prediccion dura y barata: en el subconjunto de ESPANA, mismo
idioma y mismo diccionario pero otro regimen de etiquetado y otra poblacion de
contribuyentes, la brecha del lado natural deberia caer bastante. Si cae, el
mecanismo queda demostrado en vez de argumentado. Si NO cae, el mecanismo esta
mal y hay que volver a pensarlo antes de escribir.

Se registra la prediccion aqui, ANTES de correr, para que no se pueda reescribir
despues:

  P4  La brecha de la clase natural_botanico en Espana sera al menos 15 puntos
      porcentuales menor que en Mexico.
  P5  La brecha de la clase sintetico cambiara poco: menos de 10 puntos, porque
      los terminos sinteticos que OFF si cubre son los mismos en los dos paises.
  P6  La proporcion de detecciones naturales que caen dentro del vocabulario
      subira en Espana. En Mexico es 40 %.

OJO CON LA ASIMETRIA DE MUESTRA. Espana tiene muchisimos mas productos en Open
Food Facts que Mexico, y una comunidad de contribuyentes distinta. Eso NO
invalida la comparacion de brechas —la brecha condiciona sobre el texto— pero
si impide comparar prevalencias. El script no las compara.

Salidas: reportes/09_replica_<pais>.json
         09_mecanismos_<pais>.csv
         09_comparacion.csv          Mexico contra el pais nuevo
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from modelo import firth, separacion
from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
EXTERNO = RAIZ / "datos" / "externo"
AMBIGUOS = REQUIEREN_CONTEXTO
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60
CARMIN = "E120"
MINERALES = {"E170", "E171", "E172"}

# nombre logico -> nombres posibles en el volcado
COLUMNAS = {
    "code": ["code", "codigo"],
    "texto": ["ingredients_text", "ingredientes_texto", "ingredients_text_es"],
    "aditivos": ["additives_tags", "aditivos_tags"],
    "paises": ["countries_tags", "paises_tags", "countries"],
    "vitaminas": ["vitamins_tags", "vitaminas_tags"],
    "minerales": ["minerals_tags", "minerales_tags"],
}


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def variantes(codigo: str) -> list[str]:
    k = norma(codigo).replace(" ", "")
    return [k] + [k + s for s in ("i", "ii", "iii", "iv", "v", "vi",
                                  "a", "b", "c", "d", "e", "f")]


def leer_taxonomia(ruta: Path):
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Ver datos/externo/LEEME.md")
    vocab, mand = {}, {}
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        m_en = re.search(r"^en:\s*(.+)$", bloque, re.M)
        if not m_en:
            continue
        cod = norma(m_en.group(1).split(",")[0]).replace(" ", "") \
               .replace("(", "").replace(")", "")
        m_es = re.search(r"^es:\s*(.+)$", bloque, re.M)
        if m_es:
            vocab[cod] = {norma(x) for x in m_es.group(1).split(",")}
        mand[cod] = "mandatory_additive_class" in bloque
    return vocab, mand


def resolver(cols: list[str]) -> dict:
    hallado, faltan = {}, []
    for logico, candidatos in COLUMNAS.items():
        for c in candidatos:
            if c in cols:
                hallado[logico] = c
                break
        else:
            if logico in ("vitaminas", "minerales"):
                hallado[logico] = None
            else:
                faltan.append(logico)
    if faltan:
        raise SystemExit(
            f"No encuentro columnas para {faltan}.\nColumnas del archivo:\n  "
            + "\n  ".join(cols)
            + "\nAgrega el nombre correcto al diccionario COLUMNAS de este script.")
    return hallado


def detectar(texto: str, ordenados):
    restante, salida = texto, []
    for termino, codigo, bloque in ordenados:
        if not termino:
            continue
        pat = re.compile(r"\b" + re.escape(termino) + r"\b")
        if pat.search(restante):
            salida.append((codigo, bloque, termino))
            restante = pat.sub(" ", restante)
    return salida


def con_contexto(texto: str, termino: str) -> bool:
    pat = re.compile(r"\b" + re.escape(termino) + r"\b")
    for m in pat.finditer(texto):
        ini, fin = max(0, m.start() - VENTANA), min(len(texto), m.end() + VENTANA)
        if RE_CONTEXTO.search(texto[ini:fin]):
            return True
    return False


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral_inorganico"
    return {"sinteticos": "sintetico", "naturales": "natural_botanico"}.get(
        bloque, "fuera_de_eje")


def analizar(df: pd.DataFrame, col: dict, dic, ordenados, vocab, mand) -> pd.DataFrame:
    cob = {}
    for termino, codigo, _ in ordenados:
        vs, es_mand = set(), False
        for k in variantes(codigo):
            vs |= vocab.get(k, set())
            es_mand = es_mand or mand.get(k, False)
        cob[(codigo, norma(termino))] = (norma(termino) in vs, es_mand)

    pares = []
    for t in df.itertuples(index=False):
        texto = normalizar(getattr(t, col["texto"]))
        tags = {str(a).replace("en:", "").upper()
                for a in como_lista(getattr(t, col["aditivos"]))}
        for codigo, bloque, termino in detectar(texto, ordenados):
            cl = clase_de(codigo, bloque)
            if cl == "fuera_de_eje":
                continue
            if codigo in AMBIGUOS and not con_contexto(texto, termino):
                continue
            en_vocab, es_mand = cob.get((codigo, norma(termino)), (False, False))
            pares.append({"codigo": codigo, "clase": cl,
                          "en_vocab": en_vocab, "mandatory": es_mand,
                          "en_tags": codigo in tags})
    return pd.DataFrame(pares)


def mecanismos(p: pd.DataFrame) -> pd.DataFrame:
    m = (p.groupby(["clase", "en_vocab", "mandatory"])
           .agg(n=("en_tags", "size"),
                sin_tag=("en_tags", lambda s: int((~s).sum())))
           .reset_index())
    m["brecha_pct"] = (100 * m.sin_tag / m.n).round(1)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default="en:spain",
                    help="etiqueta de countries_tags, p. ej. en:spain")
    ap.add_argument("--crudo", default=None,
                    help="parquet del volcado; si se omite busca en datos/crudo/")
    args = ap.parse_args()

    etiqueta = args.pais.replace("en:", "")
    if args.crudo:
        ruta = Path(args.crudo)
    else:
        candidatos = sorted((RAIZ / "datos" / "crudo").glob("*.parquet"))
        if not candidatos:
            raise SystemExit("No hay parquet en datos/crudo/. Pasa --crudo con la ruta.")
        ruta = candidatos[0]
    print(f"  volcado: {ruta}")

    esquema = {r[0]: r[1] for r in duckdb.sql(f"DESCRIBE SELECT * FROM '{ruta}' LIMIT 0").fetchall()}
    col = resolver(list(esquema.keys()))
    # El volcado crudo global trae ingredients_text/product_name como lista de
    # STRUCT(lang, text) -igual que 01_subconjunto_mx.py-, mientras que el
    # intermedio ya viene aplanado a VARCHAR. Sin esto, correr contra el crudo
    # (necesario para paises que no sean Mexico) truena en trim() con un tipo
    # STRUCT[]. Se detecta por el tipo declarado, no por el nombre de columna.
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
    df = duckdb.sql(f"""
        SELECT * FROM (SELECT {proyeccion} FROM '{ruta}')
        WHERE list_contains({col['paises']}, '{args.pais}')
          AND {col['texto']} IS NOT NULL
          AND length(trim({col['texto']})) > 0
    """).df()
    print(f"  productos de {etiqueta} con texto: {len(df):,}")
    if len(df) < 500:
        print("  AVISO: menos de 500 productos. La comparacion va a ser ruidosa.")

    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)
    vocab, mand = leer_taxonomia(EXTERNO / "additives.txt")

    p = analizar(df, col, dic, ordenados, vocab, mand)
    if p.empty:
        raise SystemExit("Cero detecciones. Revisa que el idioma del texto sea espanol.")
    mec = mecanismos(p)

    # --- modelo con Firth, mismas dos clases que en Mexico
    m = mec[mec.clase.isin(["sintetico", "natural_botanico"])].copy()
    X = pd.DataFrame({"natural": (m.clase == "natural_botanico").astype(int),
                      "fuera_vocab": (~m.en_vocab).astype(int),
                      "mandatory": m.mandatory.astype(int)})
    tabla = firth(X, m.sin_tag.values, m.n.values) if len(m) >= 4 else pd.DataFrame()
    avisos = separacion(m.assign(**X), "sin_tag", "n", ["natural", "fuera_vocab", "mandatory"])

    # --- resumen por clase y prueba de las predicciones
    porclase = (p.groupby("clase")
                  .agg(n=("en_tags", "size"),
                       sin_tag=("en_tags", lambda s: int((~s).sum())),
                       pct_en_vocab=("en_vocab", lambda s: round(100 * s.mean(), 1)))
                  .reset_index())
    porclase["brecha_pct"] = (100 * porclase.sin_tag / porclase.n).round(1)

    # cifras de Mexico de la corrida del 27 de agosto, para comparar
    # Actualizado 02/09/2026 contra el diccionario congelado v1.1 (antes traia
    # la corrida del 27 de agosto, previa al veredicto de la Dra. y a la
    # fusion del DOF). Recalcular con:
    #   python src/09_replica_pais.py --pais en:mexico
    # y leer la tabla `por_clase` de reportes/09_replica_mexico.json.
    MEXICO = {"sintetico": {"brecha_pct": 35.7, "pct_en_vocab": 82.3, "n": 2693},
              "natural_botanico": {"brecha_pct": 90.5, "pct_en_vocab": 30.4, "n": 441},
              "carmin": {"brecha_pct": 95.7, "pct_en_vocab": 91.9, "n": 235}}

    comp = []
    for fila in porclase.itertuples():
        mx = MEXICO.get(fila.clase)
        if not mx:
            continue
        comp.append({
            "clase": fila.clase,
            "n_mexico": mx["n"], f"n_{etiqueta}": int(fila.n),
            "brecha_mexico_pct": mx["brecha_pct"],
            f"brecha_{etiqueta}_pct": fila.brecha_pct,
            "diferencia_pp": round(fila.brecha_pct - mx["brecha_pct"], 1),
            "en_vocab_mexico_pct": mx["pct_en_vocab"],
            f"en_vocab_{etiqueta}_pct": fila.pct_en_vocab,
        })
    comp = pd.DataFrame(comp)

    def dif(clase):
        f = comp[comp.clase == clase]
        return float(f.diferencia_pp.iloc[0]) if len(f) else None

    d_nat, d_sin = dif("natural_botanico"), dif("sintetico")
    veredicto = {
        "P4_natural_baja_15pp_o_mas": (None if d_nat is None else bool(d_nat <= -15)),
        "P4_diferencia_observada_pp": d_nat,
        "P5_sintetico_cambia_menos_de_10pp": (None if d_sin is None else bool(abs(d_sin) < 10)),
        "P5_diferencia_observada_pp": d_sin,
        "lectura": ("Si P4 se cumple y P5 tambien, el mecanismo de cobertura de "
                    "vocabulario queda demostrado. Si P4 falla, el mecanismo esta mal "
                    "planteado y hay que rehacerlo ANTES de escribir la Introduccion."),
    }

    REPORTES.mkdir(exist_ok=True)
    mec.to_csv(REPORTES / f"09_mecanismos_{etiqueta}.csv", index=False, encoding="utf-8")
    if len(comp):
        comp.to_csv(REPORTES / "09_comparacion.csv", index=False, encoding="utf-8")

    guardar_reporte(f"09_replica_{etiqueta}", {
        "pais": args.pais, "volcado": str(ruta),
        "n_productos_con_texto": len(df),
        "n_detecciones_depuradas": len(p),
        "por_clase": porclase.to_dict("records"),
        "mecanismos": mec.to_dict("records"),
        "modelo_firth": tabla.to_dict("records") if len(tabla) else None,
        "modelo_metodo": tabla.attrs.get("metodo") if len(tabla) else None,
        "separacion_detectada": avisos,
        "comparacion_con_mexico": comp.to_dict("records"),
        "VEREDICTO": veredicto,
        "advertencia": ("Solo se comparan BRECHAS, que condicionan sobre el texto. "
                        "Las prevalencias NO son comparables entre paises: el tamano y "
                        "la composicion del subconjunto son muy distintos."),
    })

    print("\n", porclase.to_string(index=False))
    if len(comp):
        print("\n", comp.to_string(index=False))
    if len(tabla):
        print("\n  modelo (Firth):\n", tabla.to_string(index=False))
    print(f"\n  P4 natural baja >=15 pp: {veredicto['P4_natural_baja_15pp_o_mas']} "
          f"(observado {d_nat} pp)")
    print(f"  P5 sintetico cambia <10 pp: {veredicto['P5_sintetico_cambia_menos_de_10pp']} "
          f"(observado {d_sin} pp)")


if __name__ == "__main__":
    main()
