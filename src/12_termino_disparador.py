"""Paso 12 — EL TERMINO, QUE ES LA UNIDAD QUE FALTABA MIRAR.

    python src/12_termino_disparador.py --pais en:mexico
    python src/12_termino_disparador.py --pais en:spain --crudo datos/crudo/food.parquet
    python src/12_termino_disparador.py --comparar        # despues de correr los dos

CIERRA EL ULTIMO CABO. La corrida del 27 dejo dos cosas sin explicar:

    E120 carmin    Mexico  4.5 %   Espana 67.9 %   recuperado
    E100 curcuma   Mexico 25.9 %   Espana 78.3 %

No es la clase declarada (probado, no ayuda) ni el codigo en el texto (probado,
aparece en menos del 10 %). Queda una hipotesis: **dentro del mismo codigo, cada
pais imprime terminos distintos, y solo algunos estan en la taxonomia de Open
Food Facts**. «Carmin» y «cochinilla» no son la misma cadena que «acido
carminico», y la taxonomia no las trata igual.

Hasta ahora siempre agregamos por codigo o por clase. El termino es la unidad
que de verdad decide si el analizador reconoce o no, y nunca la habiamos mirado.

LA PRUEBA ES LIMPIA Y TIENE DOS RESULTADOS POSIBLES:

  Si el MISMO termino se recupera parecido en los dos paises, el mecanismo es el
  termino, y la diferencia entre paises es solo de mezcla: cada mercado escribe
  cosas distintas. Eso cierra el capitulo de metodos.

  Si el MISMO termino se recupera distinto segun el pais, el termino tampoco es
  la explicacion y hay algo mas —version del volcado, comportamiento del
  contribuyente, momento de la captura— que habria que declarar como limitacion
  en vez de seguir buscando.

Se registra aqui, antes de correr:

  P7  Al menos el 70 % de los terminos con n>=20 en ambos paises tendran una
      diferencia de recuperacion menor a 20 puntos porcentuales.

Salidas: reportes/12_terminos_<pais>.json
         12_terminos_<pais>.csv
         12_comparacion_terminos.csv    (con --comparar)
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, quitar_advertencia_trazas,
                  terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
EXTERNO = RAIZ / "datos" / "externo"
AMBIGUOS = REQUIEREN_CONTEXTO
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60
CARMIN = "E120"
MINERALES = {"E170", "E171", "E172"}
N_MINIMO_COMPARAR = 20

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


def leer_taxonomia(ruta: Path):
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Ver datos/externo/LEEME.md")
    vocab = {}
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        m = re.search(r"^en:\s*(.+)$", bloque, re.M)
        if not m:
            continue
        cod = norma(m.group(1).split(",")[0]).replace(" ", "") \
               .replace("(", "").replace(")", "")
        m_es = re.search(r"^es:\s*(.+)$", bloque, re.M)
        if m_es:
            vocab[cod] = {norma(x) for x in m_es.group(1).split(",")}
    return vocab


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral_inorganico"
    return {"sinteticos": "sintetico", "naturales": "natural_botanico"}.get(bloque, "fuera")


def con_contexto(texto: str, termino: str) -> bool:
    pat = re.compile(r"\b" + re.escape(termino) + r"\b")
    for m in pat.finditer(texto):
        ini, fin = max(0, m.start() - VENTANA), min(len(texto), m.end() + VENTANA)
        if RE_CONTEXTO.search(texto[ini:fin]):
            return True
    return False


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


def analizar(args) -> None:
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
    # Mismo bug ya visto en 09_replica_pais.py y 11_estructura_declaracion.py:
    # contra el volcado crudo global, ingredients_text llega como lista de
    # STRUCT(lang, text), no como VARCHAR plano. Se detecta por el tipo
    # declarado y se desanida solo cuando hace falta.
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
    where = f"list_contains({col['paises']}, '{args.pais}') AND " if filtrar else ""
    df = duckdb.sql(f"""
        SELECT * FROM (SELECT {proyeccion} FROM '{ruta}')
        WHERE {where} {col['texto']} IS NOT NULL
          AND length(trim({col['texto']})) > 0
    """).df()
    print(f"  {etiqueta}: {len(df):,} productos con texto")

    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)
    vocab = leer_taxonomia(EXTERNO / "additives.txt")
    en_vocab = {}
    for termino, codigo, _ in ordenados:
        vs = set()
        for k in variantes(codigo):
            vs |= vocab.get(k, set())
        en_vocab[(codigo, norma(termino))] = norma(termino) in vs

    filas, textos_rotos = [], []
    for t in df.itertuples(index=False):
        texto = normalizar(getattr(t, col["texto"]))
        # CORREGIDO parche 14: un colorante mencionado solo dentro de una
        # advertencia de trazas no cuenta como deteccion. Ver
        # util.py::quitar_advertencia_trazas y BITACORA_PARCHES.md.
        texto_det, roto = quitar_advertencia_trazas(texto)
        if roto:
            textos_rotos.append(t.code)
        tags = {str(a).replace("en:", "").upper()
                for a in como_lista(getattr(t, col["aditivos"]))}
        restante = texto_det
        for termino, codigo, bloque in ordenados:
            if not termino:
                continue
            cl = clase_de(codigo, bloque)
            if cl == "fuera":
                continue
            pat = re.compile(r"\b" + re.escape(termino) + r"\b")
            if not pat.search(restante):
                continue
            restante = pat.sub(" ", restante)
            if codigo in AMBIGUOS and not con_contexto(texto_det, termino):
                continue
            filas.append({
                "codigo": codigo, "clase": cl, "termino": termino,
                "en_vocab_off": en_vocab.get((codigo, norma(termino)), False),
                "en_tags": codigo in tags,
            })

    p = pd.DataFrame(filas)
    if p.empty:
        raise SystemExit("Cero detecciones.")

    tab = (p.groupby(["codigo", "clase", "termino", "en_vocab_off"])
             .agg(n=("en_tags", "size"),
                  recuperadas=("en_tags", "sum"))
             .reset_index())
    tab["pct_recuperado"] = (100 * tab.recuperadas / tab.n).round(1)
    tab = tab.sort_values("n", ascending=False)

    # la prueba directa: el vocabulario predice la recuperacion?
    porvocab = (p.groupby("en_vocab_off")
                  .agg(n=("en_tags", "size"), recuperadas=("en_tags", "sum"))
                  .reset_index())
    porvocab["pct_recuperado"] = (100 * porvocab.recuperadas / porvocab.n).round(1)

    REPORTES.mkdir(exist_ok=True)
    tab.to_csv(REPORTES / f"12_terminos_{etiqueta}.csv", index=False, encoding="utf-8")
    guardar_reporte(f"12_terminos_{etiqueta}", {
        "pais": args.pais, "fuente": str(ruta),
        "n_detecciones": len(p),
        "n_terminos_distintos": int(tab.termino.nunique()),
        "recuperacion_por_cobertura": porvocab.to_dict("records"),
        "por_termino": tab.to_dict("records"),
        "terminos_clave": tab[tab.codigo.isin(["E120", "E100", "E160a", "E160c"])]
                             .to_dict("records"),
        "textos_rotos_advertencia": {"n": len(textos_rotos), "codigos": textos_rotos},
    })
    print(f"\n  recuperacion segun cobertura del termino:\n{porvocab.to_string(index=False)}")
    print(f"\n  los codigos que quedaron abiertos:")
    print(tab[tab.codigo.isin(["E120", "E100"])].to_string(index=False))


def comparar() -> None:
    """Cruza los dos paises por termino. Es el veredicto."""
    archivos = {}
    for etiqueta in ("mexico", "spain"):
        f = REPORTES / f"12_terminos_{etiqueta}.csv"
        if not f.exists():
            raise SystemExit(f"Falta {f.name}. Corre primero --pais en:{etiqueta}")
        archivos[etiqueta] = pd.read_csv(f)

    mx, es = archivos["mexico"], archivos["spain"]
    comp = mx.merge(es, on=["codigo", "clase", "termino"],
                    suffixes=("_mx", "_es"), how="inner")
    comp = comp[(comp.n_mx >= N_MINIMO_COMPARAR) & (comp.n_es >= N_MINIMO_COMPARAR)].copy()
    if comp.empty:
        raise SystemExit(f"Ningun termino alcanza n>={N_MINIMO_COMPARAR} en los dos paises.")
    comp["dif_pp"] = (comp.pct_recuperado_es - comp.pct_recuperado_mx).round(1)
    comp["estable"] = comp.dif_pp.abs() < 20
    comp = comp.sort_values("dif_pp", key=abs, ascending=False)

    pct_estables = round(100 * comp.estable.mean(), 1)
    veredicto = {
        "n_terminos_comparables": int(len(comp)),
        "pct_estables_menos_20pp": pct_estables,
        "P7_se_cumple": bool(pct_estables >= 70),
        "lectura": (
            "Si P7 se cumple, el TERMINO es la unidad que decide y la diferencia entre "
            "paises es solo de mezcla: cada mercado escribe cosas distintas. Cierra el "
            "capitulo de metodos. Si NO se cumple, el termino tampoco explica y hay algo "
            "mas (version del volcado, comportamiento del contribuyente, momento de "
            "captura) que hay que declarar como limitacion en vez de seguir buscando."),
    }

    comp[["codigo", "clase", "termino", "en_vocab_off_mx",
          "n_mx", "pct_recuperado_mx", "n_es", "pct_recuperado_es",
          "dif_pp", "estable"]].to_csv(
        REPORTES / "12_comparacion_terminos.csv", index=False, encoding="utf-8")
    guardar_reporte("12_comparacion_terminos", {
        "VEREDICTO": veredicto,
        "N_MINIMO": N_MINIMO_COMPARAR,
        "comparacion": comp.to_dict("records"),
    })

    print(f"\n  terminos comparables (n>={N_MINIMO_COMPARAR} en ambos): {len(comp)}")
    print(f"  estables (dif < 20 pp): {pct_estables} %   P7: {veredicto['P7_se_cumple']}")
    print("\n", comp[["codigo", "termino", "en_vocab_off_mx", "n_mx",
                      "pct_recuperado_mx", "n_es", "pct_recuperado_es",
                      "dif_pp"]].to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", default=None)
    ap.add_argument("--crudo", default=None)
    ap.add_argument("--comparar", action="store_true")
    args = ap.parse_args()
    if args.comparar:
        comparar()
    elif args.pais:
        analizar(args)
    else:
        ap.error("pasa --pais o --comparar")


if __name__ == "__main__":
    main()
