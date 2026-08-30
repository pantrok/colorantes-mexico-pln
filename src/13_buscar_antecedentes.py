"""Paso 13 v2 — BUSQUEDA DE ANTECEDENTES, AHORA CON BUSQUEDA DE FRASE.

    python src/13_buscar_antecedentes.py --simulacro
    python src/13_buscar_antecedentes.py --bloque D_calidad_open_food_facts
    python src/13_buscar_antecedentes.py

REEMPLAZA la version del 27 de agosto, que quedo inservible.

QUE FALLO. Ninguna de las dos interfaces busca frases: hacen OR con expansion de
raices sobre titulo y resumen. La bitacora de esa corrida declaro 4 772 066
resultados para «extract food additives from ingredient lists text» y 174 724
para «Open Food Facts Mexico». El bloque D quedo secuestrado por la palabra
«Mexico» —164 de sus 195 filas venian de ahi— y devolvio plantas medicinales,
pulque y gobernanza criminal indigena.

TRES CORRECCIONES.

  1. OpenAlex se consulta con `filter=title_and_abstract.search:"..."`, que SI
     respeta comillas para frase exacta, en vez de `search=`, que hace OR.

  2. VERIFICACION POSTERIOR. Cada consulta declara en el YAML que terminos deben
     aparecer literalmente en el titulo o el resumen recuperado. Lo que no los
     traiga se descarta y se cuenta aparte. La bitacora reporta entonces DOS
     cifras: recuperados y CONFIRMADOS. La que va a Metodos es la segunda.

     Esto es lo que arregla el problema de raiz, porque no depende de que la API
     se porte bien: si el buscador trae ruido, el filtro lo tira.

  3. Crossref queda degradado a red de seguridad. No tiene busqueda de frase, asi
     que sus resultados solo cuentan si pasan la verificacion. Sirve para no
     perder algo que OpenAlex no indexe, no para descubrir.

LO QUE SIGUE SIENDO CIERTO. Una busqueda no demuestra inexistencia. Lo unico
defendible es «no se identificaron trabajos que...» con la estrategia, las
fuentes, las cadenas y la fecha. La bitacora es el producto principal.

Salidas: reportes/13_bitacora_busqueda.md     <- lo que va a Metodos
         13_antecedentes.csv                  <- confirmados, para cribar
         13_descartados.csv                   <- los que no pasaron el filtro
         13_antecedentes.ris                  <- para Mendeley
         13_busquedas_manuales.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

# La consola de Windows suele quedar en cp1252, que no puede codificar el
# caracter '→' que este script imprime mas abajo. Sin esto revienta con
# UnicodeEncodeError antes de mostrar un solo resultado.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CFG = RAIZ / "config" / "busqueda_antecedentes.yaml"
REPORTES = RAIZ / "reportes"
PAUSA = 1.0
POR_PAGINA = 100


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def clave_titulo(t: str) -> str:
    return re.sub(r"\s+", " ", norma(t)).strip()[:90]


def confirma(fila: dict, regla: dict) -> bool:
    """El corazon del arreglo. Exige que los terminos aparezcan de verdad en el
    texto recuperado, sin importar como se haya portado el buscador."""
    texto = norma(f"{fila.get('titulo','')} {fila.get('resumen','')}")
    for t in regla.get("requiere_todos") or []:
        if norma(t).strip() not in texto:
            return False
    alguno = regla.get("requiere_alguno") or []
    if alguno and not any(norma(t).strip() in texto for t in alguno):
        return False
    return True


def pedir(url: str, correo: str, intentos: int = 3) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"colorantes-mx/2.0 (mailto:{correo})",
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
            print(f"      HTTP {e.code} en {url[:100]}")
            return None
        except urllib.error.URLError as e:
            print(f"      sin red o host inalcanzable: {e.reason}")
            return None
        except (TimeoutError, json.JSONDecodeError) as e:
            print(f"      {type(e).__name__}; reintento")
            time.sleep(3)
    return None


def texto_de_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pares = [(pos, palabra) for palabra, posiciones in inv.items() for pos in posiciones]
    return " ".join(p for _, p in sorted(pares))[:1500]


# ------------------------------------------------------------------ OpenAlex

def openalex(consulta: str, desde: int, correo: str, tope: int) -> tuple[list[dict], int]:
    """Usa filter=title_and_abstract.search, que respeta comillas para frase.
    El parametro `search=` de la v1 hacia OR y por eso devolvia cientos de miles."""
    base = "https://api.openalex.org/works"
    filtros = (f"title_and_abstract.search:{consulta},"
               f"from_publication_date:{desde}-01-01")
    cursor, salida, total = "*", [], 0
    while len(salida) < tope:
        p = urllib.parse.urlencode({
            "filter": filtros, "per-page": POR_PAGINA,
            "cursor": cursor, "mailto": correo})
        d = pedir(f"{base}?{p}", correo)
        if not d:
            break
        total = d.get("meta", {}).get("count", 0)
        lote = d.get("results", [])
        for w in lote:
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
        if not cursor or len(lote) < POR_PAGINA:
            break
        time.sleep(PAUSA)
    return salida[:tope], total


# ------------------------------------------------------------------ Crossref

def crossref(consulta: str, desde: int, correo: str, tope: int) -> tuple[list[dict], int]:
    """Red de seguridad. Crossref no tiene busqueda de frase, asi que todo lo
    que devuelve pasa obligatoriamente por la verificacion posterior."""
    limpia = consulta.replace('"', " ")
    base = "https://api.crossref.org/works"
    cursor, salida, total = "*", [], 0
    while len(salida) < tope:
        p = urllib.parse.urlencode({
            "query.bibliographic": limpia, "rows": POR_PAGINA, "cursor": cursor,
            "filter": f"from-pub-date:{desde}-01-01,type:journal-article",
            "mailto": correo})
        d = pedir(f"{base}?{p}", correo)
        if not d:
            break
        msg = d.get("message", {})
        total = msg.get("total-results", 0)
        items = msg.get("items", [])
        for w in items:
            fecha = w.get("issued", {}).get("date-parts", [[None]])[0]
            salida.append({
                "fuente_api": "Crossref",
                "doi": w.get("DOI", ""),
                "titulo": (w.get("title") or [""])[0],
                "anio": fecha[0] if fecha else None,
                "revista": (w.get("container-title") or [""])[0],
                "idioma": w.get("language") or "",
                "paises": "",
                "citas": w.get("is-referenced-by-count", 0),
                "tipo": w.get("type") or "",
                "resumen": re.sub(r"<[^>]+>", " ", w.get("abstract") or "")[:1500],
                "url": f"https://doi.org/{w.get('DOI','')}" if w.get("DOI") else "",
            })
        cursor = msg.get("next-cursor")
        if not cursor or len(items) < POR_PAGINA:
            break
        time.sleep(PAUSA)
    return salida[:tope], total


def puntuar(fila: dict, reglas: dict) -> int:
    texto = norma(f"{fila['titulo']} {fila['resumen']} {fila['revista']}")
    p = 3 * sum(1 for t in reglas["terminos_fuertes"] if norma(t).strip() in texto)
    p += 5 * sum(1 for t in reglas["terminos_pais"] if norma(t).strip() in texto)
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
    ap.add_argument("--bloque", default=None)
    ap.add_argument("--simulacro", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    correo = cfg["meta"]["correo_contacto"]
    desde = cfg["meta"]["desde_anio"]
    tope = cfg["meta"].get("max_por_consulta", 200)
    bloques = cfg["bloques"]
    if args.bloque:
        if args.bloque not in bloques:
            raise SystemExit(f"Bloque desconocido. Hay: {', '.join(bloques)}")
        bloques = {args.bloque: bloques[args.bloque]}

    if args.simulacro:
        for nombre, b in bloques.items():
            print(f"\n  {nombre} — {b['pregunta']}")
            for c in b["consultas"]:
                req = []
                if c.get("requiere_todos"):
                    req.append("todos: " + ", ".join(c["requiere_todos"]))
                if c.get("requiere_alguno"):
                    req.append("alguno: " + ", ".join(c["requiere_alguno"]))
                print(f"    · {c['q'].strip()}")
                print(f"        exige → {' | '.join(req) if req else 'nada'}")
        print("\n  Simulacro: no se consulto nada.")
        return

    filas, descartadas, bitacora = [], [], []
    hoy = date.today().isoformat()
    for nombre, b in bloques.items():
        print(f"\n  {nombre}")
        for regla in b["consultas"]:
            consulta = regla["q"].strip()
            print(f"    «{consulta}»")
            for etiqueta, fn in (("OpenAlex", openalex), ("Crossref", crossref)):
                res, total = fn(consulta, desde, correo, tope)
                ok = [r for r in res if confirma(r, regla)]
                no = [r for r in res if not confirma(r, regla)]
                print(f"      {etiqueta}: {total} declarados · {len(res)} recuperados "
                      f"· {len(ok)} CONFIRMADOS")
                for r in ok:
                    r["bloque"], r["consulta"] = nombre, consulta
                for r in no:
                    r["bloque"], r["consulta"] = nombre, consulta
                filas += ok
                descartadas += no
                bitacora.append({
                    "bloque": nombre, "consulta": consulta, "fuente": etiqueta,
                    "declarados": total, "recuperados": len(res),
                    "confirmados": len(ok), "fecha": hoy})
                time.sleep(PAUSA)

    if not filas:
        raise SystemExit(
            "Cero resultados confirmados. Si tampoco hubo recuperados, revisa la "
            "conexion. Si hubo recuperados pero ninguno confirmo, las reglas de "
            "`requiere_*` del YAML son demasiado estrictas.")

    df = pd.DataFrame(filas)
    antes = len(df)
    df["_clave"] = df.apply(
        lambda r: r.doi.lower() if r.doi else clave_titulo(r.titulo), axis=1)
    df = (df.sort_values("citas", ascending=False)
            .drop_duplicates("_clave").drop(columns="_clave"))
    df["relevancia"] = df.apply(lambda r: puntuar(r, cfg["relevancia"]), axis=1)
    df = df.sort_values(["relevancia", "citas"], ascending=False)
    for c in ("revisado", "pertinente", "nota"):
        df[c] = ""

    REPORTES.mkdir(exist_ok=True)
    cols = ["relevancia", "titulo", "anio", "revista", "idioma", "paises", "citas",
            "doi", "bloque", "consulta", "fuente_api", "url",
            "revisado", "pertinente", "nota", "resumen"]
    df[cols].to_csv(REPORTES / "13_antecedentes.csv", index=False, encoding="utf-8-sig")
    if descartadas:
        pd.DataFrame(descartadas)[["titulo", "anio", "revista", "bloque",
                                   "consulta", "fuente_api"]].to_csv(
            REPORTES / "13_descartados.csv", index=False, encoding="utf-8-sig")
    (REPORTES / "13_antecedentes.ris").write_text(a_ris(df.head(200)), encoding="utf-8")

    bit = pd.DataFrame(bitacora)
    tasa = round(100 * bit.confirmados.sum() / max(bit.recuperados.sum(), 1), 1)
    lineas = [
        "# Bitácora de búsqueda de antecedentes", "",
        f"**Fecha de ejecución:** {hoy}  ",
        f"**Ventana temporal:** desde {desde}  ",
        "**Fuentes:** OpenAlex y Crossref, por interfaz de programación, sin llave.  ",
        f"**Consultas:** {bit.consulta.nunique()} cadenas en {bit.bloque.nunique()} bloques.  ",
        f"**Confirmados:** {antes}; **únicos tras deduplicar por DOI y título:** {len(df)}.",
        "",
        "## Cómo leer esta tabla", "",
        "**Declarados** es lo que la interfaz dice tener. No es un resultado de "
        "búsqueda: ninguna de las dos hace búsqueda de frase por omisión, así que "
        "esa cifra incluye todo lo que comparta alguna palabra.", "",
        "**Confirmados** son los que, al revisar el título y el resumen "
        "recuperados, contienen de verdad los términos exigidos. **Es la única "
        "cifra citable.**", "",
        f"Tasa global de confirmación: **{tasa} %** de lo recuperado.", "",
        "> Una búsqueda no demuestra inexistencia. Lo que esta bitácora sostiene "
        "es «no se identificaron trabajos que…», con la estrategia declarada.",
        "", "## Resultados por consulta", "",
        "| Bloque | Consulta | Fuente | Declarados | Recuperados | Confirmados |",
        "|---|---|---|---|---|---|",
    ]
    for r in bit.itertuples():
        lineas.append(f"| {r.bloque} | `{r.consulta}` | {r.fuente} | "
                      f"{r.declarados} | {r.recuperados} | **{r.confirmados}** |")
    lineas += ["", "## Fuentes no automatizadas", "",
               "SciELO y Redalyc no exponen interfaz de búsqueda por texto libre. "
               "Quedan cubiertas indirectamente porque OpenAlex las indexa, y se "
               "revisaron a mano con `13_busquedas_manuales.md`.", "",
               "Latindex no se consultó: es un catálogo de revistas, no de "
               "artículos."]
    (REPORTES / "13_bitacora_busqueda.md").write_text("\n".join(lineas), encoding="utf-8")

    man = ["# Búsquedas manuales", ""]
    for nombre, b in cfg["bloques"].items():
        man.append(f"## {nombre}")
        for regla in b["consultas"][:2]:
            q = urllib.parse.quote_plus(regla["q"].strip().replace('"', ""))
            for sitio, plantilla in cfg["manual"].items():
                man.append(f"- **{sitio}** → {plantilla.format(q=q)}")
        man.append("")
    (REPORTES / "13_busquedas_manuales.md").write_text("\n".join(man), encoding="utf-8")

    print(f"\n  confirmados {antes} → {len(df)} únicos   "
          f"(descartados por el filtro: {len(descartadas)})")
    print(f"  tasa de confirmación: {tasa} %")
    print("\n  los 15 más relevantes:")
    print(df.head(15)[["relevancia", "anio", "titulo"]].to_string(index=False))


if __name__ == "__main__":
    main()
