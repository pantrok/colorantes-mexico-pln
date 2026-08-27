"""Paso 8 — EL QUE EXPLICA LA BRECHA. Corre ANTES de interpretar el 07.

Motivo (25 de agosto de 2026). Se leyo el codigo fuente de Product Opener y la
hipotesis con la que veniamos trabajando resulto FALSA:

  `additives_tags` NO es un campo capturado aparte, y NO reconoce solo codigos E.
  Se calcula en cada guardado con `extract_additives_from_text()`
  (lib/ProductOpener/Ingredients.pm), que segmenta `ingredients_text` y
  canonicaliza cada segmento contra la taxonomia multilingue `additives`
  (659 entradas, 631 con traduccion al espanol, 622 con sinonimos nominales).

Entonces la brecha no puede explicarse por "OFF solo ve numeros E". Hay tres
mecanismos candidatos, y este script los separa:

  M1  COBERTURA DE VOCABULARIO. El termino que nosotros reconocimos, ¿existe en
      la taxonomia de OFF en espanol? La taxonomia esta construida con espanol
      iberico ("pimenton", no "paprika") y le faltan las formas comerciales
      mexicanas y las de estilo FD&C.

  M2  REGLA mandatory_additive_class. Para 45 entradas de la taxonomia, el
      nombre de la sustancia NO basta: OFF exige que el texto haya declarado
      antes la clase tecnologica ("colorante:"), o que venga el codigo E.
      Entre colorantes aplica a E120, E123, E150, E160a, E164 y E170(i).
      Es, casi literalmente, nuestra propia regla de sesenta caracteres, pero
      mas estricta: OFF exige la clase en posicion estructural, nosotros
      aceptamos proximidad.

  M3  DESVIO A OTRAS TAXONOMIAS. Vitaminas, minerales, aminoacidos y nucleotidos
      se etiquetan en `vitamins_tags` / `minerals_tags`, NO en `additives_tags`,
      aunque tengan numero E (issue #1131). Afecta directo a E101 riboflavina y
      a E170 carbonato de calcio, que son el primero y el segundo codigo mas
      "perdidos" de nuestra corrida bruta. Buscarlos solo en `additives_tags` es
      un error de medicion nuestro, no una omision de OFF.

Si M1 + M2 + M3 explican la brecha, el hallazgo del articulo deja de ser
"el campo estructurado es ciego al origen" y pasa a ser algo mejor porque esta
diagnosticado al mecanismo: el vocabulario fijo de una base internacional no
cubre las formas de declaracion locales, y falla de forma asimetrica porque los
naturales se declaran con muchas formas que varian por region mientras los
sinteticos tienen pocas y estables.

REQUISITO: descargar la taxonomia y ponerla en datos/externo/additives.txt
  curl -sL https://raw.githubusercontent.com/openfoodfacts/openfoodfacts-server/main/taxonomies/additives.txt \
       -o datos/externo/additives.txt
Anotar el commit exacto en reportes/procedencia.json: la taxonomia cambia y el
resultado depende de su version.

Salidas: reportes/08_vocabulario_off.json
         08_cobertura_terminos.csv   termino nuestro x presencia en OFF
         08_mecanismos.csv           brecha por mecanismo
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
TAXONOMIA = RAIZ / "datos" / "externo" / "additives.txt"
AMBIGUOS = REQUIEREN_CONTEXTO
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def leer_taxonomia(ruta: Path) -> tuple[dict, dict]:
    """{codigo_normalizado: set(terminos es)} y {codigo: bool mandatory}."""
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Descargala primero (ver docstring).")
    vocab, mand = {}, {}
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        m_en = re.search(r"^en:\s*(.+)$", bloque, re.M)
        if not m_en:
            continue
        cod = norma(m_en.group(1).split(",")[0]).replace(" ", "").replace("(", "").replace(")", "")
        m_es = re.search(r"^es:\s*(.+)$", bloque, re.M)
        if m_es:
            vocab[cod] = {norma(x) for x in m_es.group(1).split(",")}
        mand[cod] = "mandatory_additive_class" in bloque
    return vocab, mand


def variantes(codigo: str) -> list[str]:
    k = norma(codigo).replace(" ", "")
    return [k] + [k + s for s in ("i", "ii", "iii", "iv")]


def detectar_con_termino(texto: str, ordenados):
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


def main() -> None:
    vocab, mand = leer_taxonomia(TAXONOMIA)
    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)

    # ---- M1/M2 a nivel de diccionario: que cubre OFF y que no
    cobertura = []
    for termino, codigo, bloque in ordenados:
        vs = set()
        es_mand = False
        for k in variantes(codigo):
            vs |= vocab.get(k, set())
            es_mand = es_mand or mand.get(k, False)
        t = norma(termino)
        cobertura.append({
            "codigo": codigo, "bloque": bloque, "termino": termino,
            "en_vocabulario_off": t in vs,
            "es_codigo_e": bool(re.match(r"^e\s?-?\d", t)),
            "off_mandatory_class": es_mand,
            "n_terminos_off_es": len(vs),
        })
    cob = pd.DataFrame(cobertura)

    # ---- lectura del parquet, buscando TAMBIEN vitamins/minerals (M3)
    cols = duckdb.sql(f"SELECT * FROM '{INTERMEDIO/'productos_mx.parquet'}' LIMIT 1").df().columns.tolist()
    extra = [c for c in ("vitaminas_tags", "vitamins_tags", "minerales_tags", "minerals_tags")
             if c in cols]
    if not extra:
        print("  AVISO: el parquet no trae vitamins_tags ni minerals_tags. "
              "M3 no se puede evaluar; hay que reextraer del volcado.")
    sel = "code, ingredientes_texto, aditivos_tags" + ("," + ",".join(extra) if extra else "")
    df = duckdb.sql(f"""
        SELECT {sel} FROM '{INTERMEDIO/'productos_mx.parquet'}'
        WHERE ingredientes_texto IS NOT NULL AND length(trim(ingredientes_texto)) > 0
    """).df()

    idx = {(r.codigo, norma(r.termino)): r for r in cob.itertuples()}
    pares = []
    for t in df.itertuples(index=False):
        texto = normalizar(t.ingredientes_texto)
        tags_add = {str(a).replace("en:", "").upper() for a in como_lista(t.aditivos_tags)}
        tags_otro = set()
        for c in extra:
            tags_otro |= {str(a).replace("en:", "").upper() for a in como_lista(getattr(t, c))}
        for codigo, bloque, termino in detectar_con_termino(texto, ordenados):
            if bloque not in ("sinteticos", "naturales"):
                continue
            if codigo in AMBIGUOS and not con_contexto(texto, termino):
                continue                       # mismo criterio de depuracion
            meta = idx.get((codigo, norma(termino)))
            pares.append({
                "code": t.code, "codigo": codigo, "bloque": bloque, "termino": termino,
                "en_vocab_off": bool(meta.en_vocabulario_off) if meta else False,
                "off_mandatory": bool(meta.off_mandatory_class) if meta else False,
                "en_additives_tags": codigo in tags_add,
                "en_otras_taxonomias": codigo in tags_otro,
            })
    p = pd.DataFrame(pares)
    if p.empty:
        raise SystemExit("Cero detecciones depuradas.")
    p["visible_en_alguna"] = p.en_additives_tags | p.en_otras_taxonomias

    def brecha(sub, campo="en_additives_tags"):
        n = len(sub)
        return {"n": n, "sin_tag": int((~sub[campo]).sum()),
                "brecha_pct": round(100 * float((~sub[campo]).mean()), 1) if n else None}

    mecanismos = []
    for (bl, vocab_ok, mnd), g in p.groupby(["bloque", "en_vocab_off", "off_mandatory"]):
        mecanismos.append({
            "clase": bl, "termino_en_vocabulario_off": bool(vocab_ok),
            "sujeto_a_mandatory_class": bool(mnd),
            **brecha(g),
            "brecha_pct_si_se_cuentan_otras_taxonomias":
                round(100 * float((~g.visible_en_alguna).mean()), 1),
        })
    mec = pd.DataFrame(mecanismos).sort_values("n", ascending=False)

    resumen = {
        "taxonomia": {"ruta": str(TAXONOMIA),
                      "entradas_con_es": len(vocab),
                      "entradas_mandatory": int(sum(mand.values()))},
        "M1_cobertura_diccionario": {
            "terminos_nuestros": len(cob),
            "cubiertos_por_off": int(cob.en_vocabulario_off.sum()),
            "no_cubiertos": int((~cob.en_vocabulario_off).sum()),
            "por_clase": cob.groupby("bloque").en_vocabulario_off
                            .agg(["size", "sum"]).to_dict("index"),
        },
        "M2_mandatory_class": sorted({r.codigo for r in cob.itertuples()
                                      if r.off_mandatory_class}),
        "M3_otras_taxonomias": {
            "columnas_disponibles": extra,
            "detecciones_recuperadas": int(p.en_otras_taxonomias.sum()),
        },
        "brecha_global": brecha(p),
        "brecha_global_contando_otras_taxonomias":
            round(100 * float((~p.visible_en_alguna).mean()), 1),
        "tabla_mecanismos": mec.to_dict("records"),
        "LECTURA": ("Si la brecha cae fuerte al condicionar por en_vocab_off, el "
                    "mecanismo es cobertura de vocabulario y no ceguera al origen. "
                    "Si cae al contar otras taxonomias, parte de la brecha era error "
                    "de medicion nuestro. Lo que quede sin explicar es el hallazgo."),
    }

    REPORTES.mkdir(exist_ok=True)
    cob.to_csv(REPORTES / "08_cobertura_terminos.csv", index=False, encoding="utf-8")
    mec.to_csv(REPORTES / "08_mecanismos.csv", index=False, encoding="utf-8")
    guardar_reporte("08_vocabulario_off", resumen)

    print(f"  terminos nuestros: {len(cob)}  cubiertos por OFF: {int(cob.en_vocabulario_off.sum())}")
    print(f"  brecha global (solo additives_tags): {resumen['brecha_global']['brecha_pct']} %")
    print(f"  brecha global (contando vitaminas/minerales): "
          f"{resumen['brecha_global_contando_otras_taxonomias']} %")
    print("\n", mec.to_string(index=False))


if __name__ == "__main__":
    main()
