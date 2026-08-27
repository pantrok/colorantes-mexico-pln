"""Paso 13 — BUSQUEDA DE ANTECEDENTES, AUTOMATIZADA Y CON BITACORA.

    python src/13_buscar_antecedentes.py                    # todo
    python src/13_buscar_antecedentes.py --bloque A_colorantes_mercado_mx
    python src/13_buscar_antecedentes.py --simulacro        # no consulta, solo imprime

PARA QUE. El manuscrito necesita poder decir que nadie ha hecho esto en Mexico.
Esa afirmacion, tal cual, es indemostrable: una busqueda **no prueba
inexistencia**. Lo unico defendible es «no se identificaron trabajos que...»
acompanado de la estrategia, las fuentes, las cadenas exactas y la fecha.

Por eso lo importante de este script no son los resultados sino la BITACORA:
`reportes/13_bitacora_busqueda.md` deja escrito que se busco, donde, cuando y
cuantos resultados dio cada consulta. Sin ese registro, la afirmacion no aguanta
a un arbitro; con el, es una estrategia reproducible que puede ir en Metodos.

QUE FUENTES Y POR QUE ESAS.

  OpenAlex   es el motor principal. Abierto, sin llave, ~250 millones de obras,
             e indexa SciELO, Redalyc, Dialnet y repositorios latinoamericanos.
             Permite filtrar por idioma y por pais de la institucion firmante.
  Crossref   segundo motor, para cruzar. Cubre todo lo que tiene DOI.

  NO se automatizan, y hay que decirlo: SciELO y Redalyc no exponen API de
  busqueda por texto libre —ArticleMeta de SciELO consulta por identificador, no
  por consulta—. Se cubren de forma indirecta via OpenAlex, y el script genera
  las URLs para revisarlas a mano.

  LATINDEX NO APLICA. Es un catalogo de REVISTAS, no de articulos. Sirve para
  verificar que CienciaUAT esta indexada; no para buscar antecedentes.

NO PROBADO CONTRA LA RED. Se escribio sin poder ejecutarlo contra las APIs
reales. Corre primero con --simulacro para ver las consultas, y luego una sola
con --bloque para comprobar que responde antes de lanzarlo completo.

Salidas: reportes/13_bitacora_busqueda.md     <- lo que va a Metodos
         13_antecedentes.csv                  <- para cribar a mano
         13_antecedentes.ris                  <- para Mendeley
         13_busquedas_manuales.md             <- URLs de SciELO y Redalyc
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CFG = RAIZ / "config" / "busqueda_antecedentes.yaml"
REPORTES = RAIZ / "reportes"
PAUSA = 1.0          # segundos entre llamadas: las dos APIs lo piden por cortesia
POR_PAGINA = 100
MAX_PAGINAS = 5      # tope duro: 500 resultados por consulta y fuente


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def clave_titulo(t: str) -> str:
    """Para deduplicar cuando no hay DOI."""
    return re.sub(r"\s+", " ", norma(t)).strip()[:90]


def pedir(url: str, correo: str, intentos: int = 3) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"colorantes-mx/1.0 (mailto:{correo})",
        "Accept": "application/json"})
    for i in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                espera = 5 * (i + 1)
                print(f"      limite de tasa ({e.code}); espero {espera}s")
                time.sleep(espera)
                continue
            print(f"      HTTP {e.code} en {url[:90]}")
            return None
        except urllib.error.URLError as e:
            print(f"      sin red o host inalcanzable: {e.reason}")
            return None
        except (TimeoutError, json.JSONDecodeError) as e:
            print(f"      {type(e).__name__}; reintento")
            time.sleep(3)
    return None


def texto_de_abstract(inv: dict | None) -> str:
    """OpenAlex guarda el resumen como indice invertido."""
    if not inv:
        return ""
    pares = [(pos, palabra) for palabra, posiciones in inv.items() for pos in posiciones]
    return " ".join(p for _, p in sorted(pares))[:1200]


# ------------------------------------------------------------------ OpenAlex

def openalex(consulta: str, desde: int, correo: str) -> tuple[list[dict], int]:
    base = "https://api.openalex.org/works"
    filtros = f"from_publication_date:{desde}-01-01"
    cursor, salida, total = "*", [], 0
    for _ in range(MAX_PAGINAS):
        p = urllib.parse.urlencode({
            "search": consulta, "filter": filtros, "per-page": POR_PAGINA,
            "cursor": cursor, "mailto": correo})
        d = pedir(f"{base}?{p}", correo)
        if not d:
            break
        total = d.get("meta", {}).get("count", 0)
        for w in d.get("results", []):
            paises = {i.get("country_code")
                      for a in w.get("authorships", [])
                      for i in a.get("institutions", []) if i.get("country_code")}
            fuente = (w.get("primary_location") or {}).get("source") or {}
            salida.append({
                "fuente_api": "OpenAlex",
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "titulo": w.get("title") or w.get("display_name") or "",
                "anio": w.get("publication_year"),
                "revista": fuente.get("display_name") or "",
                "idioma": w.get("language") or "",
                "paises": ",".join(sorted(paises)),
                "citas": w.get("cited_by_count", 0),
                "tipo": w.get("type") or "",
                "resumen": texto_de_abstract(w.get("abstract_inverted_index")),
                "url": w.get("id") or "",
            })
        cursor = d.get("meta", {}).get("next_cursor")
        if not cursor or len(d.get("results", [])) < POR_PAGINA:
            break
        time.sleep(PAUSA)
    return salida, total


# ------------------------------------------------------------------ Crossref

def crossref(consulta: str, desde: int, correo: str) -> tuple[list[dict], int]:
    base = "https://api.crossref.org/works"
    cursor, salida, total = "*", [], 0
    for _ in range(MAX_PAGINAS):
        p = urllib.parse.urlencode({
            "query.bibliographic": consulta, "rows": POR_PAGINA, "cursor": cursor,
            "filter": f"from-pub-date:{desde}-01-01,type:journal-article",
            "mailto": correo})
        d = pedir(f"{base}?{p}", correo)
        if not d:
            break
        msg = d.get("message", {})
        total = msg.get("total-results", 0)
        items = msg.get("items", [])
        for w in items:
            titulo = (w.get("title") or [""])[0]
            fecha = w.get("issued", {}).get("date-parts", [[None]])[0]
            salida.append({
                "fuente_api": "Crossref",
                "doi": w.get("DOI", ""),
                "titulo": titulo,
                "anio": fecha[0] if fecha else None,
                "revista": (w.get("container-title") or [""])[0],
                "idioma": w.get("language") or "",
                "paises": "",
                "citas": w.get("is-referenced-by-count", 0),
                "tipo": w.get("type") or "",
                "resumen": re.sub(r"<[^>]+>", " ", w.get("abstract") or "")[:1200],
                "url": f"https://doi.org/{w.get('DOI','')}" if w.get("DOI") else "",
            })
        cursor = msg.get("next-cursor")
        if not cursor or len(items) < POR_PAGINA:
            break
        time.sleep(PAUSA)
    return salida, total


# ----------------------------------------------------------------- relevancia

def puntuar(fila: dict, reglas: dict) -> int:
    """Ordena la revision manual. NO descarta: todo se conserva en el CSV."""
    texto = norma(f"{fila['titulo']} {fila['resumen']} {fila['revista']}")
    p = 0
    p += 3 * sum(1 for t in reglas["terminos_fuertes"] if norma(t) in texto)
    p += 5 * sum(1 for t in reglas["terminos_pais"] if norma(t) in texto)
    if "mx" in (fila.get("paises") or "").lower():
        p += 6
    if fila.get("idioma") in reglas["idiomas_interes"]:
        p += 1
    return p


def a_ris(df: pd.DataFrame) -> str:
    fuera = []
    for r in df.itertuples():
        fuera += ["TY  - JOUR", f"TI  - {r.titulo}"]
        if r.anio and str(r.anio) != "nan":
            fuera.append(f"PY  - {int(r.anio)}")
        if r.revista:
            fuera.append(f"JO  - {r.revista}")
        if r.doi:
            fuera.append(f"DO  - {r.doi}")
        fuera += [f"KW  - bloque:{r.bloque}",
                  "KW  - proyecto:colorantes-mx-cienciauat",
                  "KW  - busqueda-antecedentes", "ER  - ", ""]
    return "\n".join(fuera)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bloque", default=None, help="corre un solo bloque")
    ap.add_argument("--simulacro", action="store_true",
                    help="imprime las consultas sin salir a la red")
    args = ap.parse_args()

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    correo = cfg["meta"]["correo_contacto"]
    desde = cfg["meta"]["desde_anio"]
    bloques = cfg["bloques"]
    if args.bloque:
        if args.bloque not in bloques:
            raise SystemExit(f"Bloque desconocido. Hay: {', '.join(bloques)}")
        bloques = {args.bloque: bloques[args.bloque]}

    if args.simulacro:
        print(f"  correo: {correo}   desde: {desde}")
        for nombre, b in bloques.items():
            print(f"\n  {nombre} — {b['pregunta']}")
            for c in b["consultas"]:
                print(f"    · {c}")
        print(f"\n  {sum(len(b['consultas']) for b in bloques.values())} consultas "
              f"x 2 fuentes. Simulacro: no se consulto nada.")
        return

    filas, bitacora = [], []
    hoy = date.today().isoformat()
    for nombre, b in bloques.items():
        print(f"\n  {nombre}")
        for consulta in b["consultas"]:
            print(f"    «{consulta}»")
            for etiqueta, fn in (("OpenAlex", openalex), ("Crossref", crossref)):
                res, total = fn(consulta, desde, correo)
                print(f"      {etiqueta}: {len(res)} recuperados de {total} declarados")
                for r in res:
                    r["bloque"] = nombre
                    r["consulta"] = consulta
                filas += res
                bitacora.append({"bloque": nombre, "consulta": consulta,
                                 "fuente": etiqueta, "total_declarado": total,
                                 "recuperados": len(res), "fecha": hoy})
                time.sleep(PAUSA)

    if not filas:
        raise SystemExit(
            "Cero resultados. Revisa la conexion: este script necesita internet.\n"
            "Corre con --simulacro para ver las consultas sin salir a la red.")

    df = pd.DataFrame(filas)
    antes = len(df)
    df["_clave"] = df.apply(
        lambda r: r.doi.lower() if r.doi else clave_titulo(r.titulo), axis=1)
    df = (df.sort_values("citas", ascending=False)
            .drop_duplicates("_clave")
            .drop(columns="_clave"))
    df["relevancia"] = df.apply(lambda r: puntuar(r, cfg["relevancia"]), axis=1)
    df = df.sort_values(["relevancia", "citas"], ascending=False)
    df["revisado"] = ""
    df["pertinente"] = ""
    df["nota"] = ""

    REPORTES.mkdir(exist_ok=True)
    cols = ["relevancia", "titulo", "anio", "revista", "idioma", "paises", "citas",
            "doi", "bloque", "consulta", "fuente_api", "url",
            "revisado", "pertinente", "nota", "resumen"]
    df[cols].to_csv(REPORTES / "13_antecedentes.csv", index=False, encoding="utf-8-sig")
    (REPORTES / "13_antecedentes.ris").write_text(
        a_ris(df.head(200)), encoding="utf-8")

    bit = pd.DataFrame(bitacora)
    lineas = [
        "# Bitácora de búsqueda de antecedentes", "",
        f"**Fecha de ejecución:** {hoy}  ",
        f"**Ventana temporal:** desde {desde}  ",
        f"**Fuentes consultadas:** OpenAlex y Crossref, por interfaz de programación, "
        f"sin llave de acceso.  ",
        f"**Consultas:** {bit.consulta.nunique()} cadenas en {bit.bloque.nunique()} bloques temáticos.  ",
        f"**Registros recuperados:** {antes}; **únicos tras deduplicar por DOI y "
        f"título:** {len(df)}.", "",
        "> Una búsqueda no demuestra inexistencia. La afirmación que esta bitácora "
        "sostiene es «no se identificaron trabajos que…», con la estrategia declarada.",
        "", "## Resultados por consulta", "",
        "| Bloque | Consulta | Fuente | Declarados | Recuperados |",
        "|---|---|---|---|---|",
    ]
    for r in bit.itertuples():
        lineas.append(f"| {r.bloque} | {r.consulta} | {r.fuente} | "
                      f"{r.total_declarado} | {r.recuperados} |")
    lineas += ["", "## Fuentes NO automatizadas", "",
               "SciELO y Redalyc no exponen interfaz de búsqueda por texto libre. "
               "Quedan cubiertas de forma indirecta porque OpenAlex las indexa, y "
               "además se revisaron a mano con las URL de "
               "`13_busquedas_manuales.md`.", "",
               "Latindex no se consultó: es un catálogo de revistas, no de "
               "artículos, y no permite buscar antecedentes."]
    (REPORTES / "13_bitacora_busqueda.md").write_text("\n".join(lineas), encoding="utf-8")

    man = ["# Búsquedas que hay que hacer a mano", "",
           "Pega cada liga en el navegador y revisa la primera página de "
           "resultados. Anota lo pertinente en la hoja del CSV.", ""]
    for nombre, b in cfg["bloques"].items():
        man.append(f"## {nombre}")
        for consulta in b["consultas"][:2]:
            q = urllib.parse.quote_plus(consulta)
            for sitio, plantilla in cfg["manual"].items():
                man.append(f"- **{sitio}** · «{consulta}» → {plantilla.format(q=q)}")
        man.append("")
    (REPORTES / "13_busquedas_manuales.md").write_text("\n".join(man), encoding="utf-8")

    print(f"\n  {antes} registros -> {len(df)} únicos tras deduplicar")
    print(f"  con relevancia alta (>=10): {int((df.relevancia >= 10).sum())}")
    print("\n  los 12 más relevantes:")
    print(df.head(12)[["relevancia", "anio", "titulo"]].to_string(index=False))
    print(f"\n-> {REPORTES}/13_bitacora_busqueda.md   (esto va a Métodos)")


if __name__ == "__main__":
    main()
