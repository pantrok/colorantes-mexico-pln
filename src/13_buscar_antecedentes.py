"""Paso 13 v3 — BUSQUEDA DE ANTECEDENTES. La regla es la frase de la consulta.

    python src/13_buscar_antecedentes.py --simulacro
    python src/13_buscar_antecedentes.py --bloque D_calidad_open_food_facts
    python src/13_buscar_antecedentes.py

REEMPLAZA la version del 29 de agosto.

QUE FALLO EN LA V2. La verificacion posterior si se aplico —el bloque D quedo
limpio, 90 de 109 mencionan Open Food Facts de verdad—, pero las reglas que
declaraba el YAML eran raices sueltas y no las frases de la consulta:

    q: '"aditivos alimentarios" preenvasados'   ->  requiere_todos: [aditivo]

Con eso pasaron «aditivos fitogenicos para leitoes desmamados» y «aditivos
quimicos para paineis cimento-madeira». Al exigir a posteriori las frases
entrecomilladas de la propia consulta, de las 191 filas confirmadas por Crossref
sobrevivio UNA; de las 195 de OpenAlex, 172. La tasa global del 9.6 % promediaba
dos brazos incomparables.

TRES CORRECCIONES.

  1. LAS EXIGENCIAS SE DERIVAN DE LA CONSULTA. `exigencias()` lee las comillas
     de `q` y las suma a lo que declare el YAML. Ya no hay forma de que la
     bitacora prometa una verificacion mas dura de la que hace.

  2. TRES CAJONES. `clasifica()` devuelve 'estricto' (trae las frases; es el
     corpus citable), 'laxo' (cumple las reglas del YAML pero no las frases; va
     a 13_por_revisar.csv para cribar a mano y NO cuenta en Metodos) y 'fuera'.
     La v2 tiraba los laxos, y ahi se perdian vecinos buenos que el buscador
     habia traido emparejando por otro campo.

  3. CONTROL DE RECUPERACION. Se comprueba por DOI si la estrategia alcanza
     cinco trabajos que ya sabemos que son los vecinos mas cercanos, y se separa
     «no recuperado» (falla la cadena) de «recuperado y descartado» (falla la
     regla, que es peor). La v2 recuperaba dos de cuatro y no lo decia.

ADEMAS, dos defectos menores del .ris: salia con `df.head(200)`, truncado a 200
de 407, y sin autores ni resumenes, porque el flujo nunca recolectaba el campo
de autor. Ahora se recolecta y se escribe completo.

LO QUE SIGUE SIENDO CIERTO. Una busqueda no demuestra inexistencia. Lo unico
defendible es «no se identificaron trabajos que...» con la estrategia, las
fuentes, las cadenas, el control de recuperacion y la fecha. La bitacora es el
producto principal.

Salidas: reportes/13_bitacora_busqueda.md     <- lo que va a Metodos
         13_antecedentes.csv                  <- corpus citable (estrictos)
         13_por_revisar.csv                   <- laxos, para cribar a mano
         13_descartados.csv                   <- los que no pasaron nada
         13_antecedentes.ris                  <- completo, con autores
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
import yaml

# La consola de Windows suele quedar en cp1252, que no puede codificar el
# caracter '→' que este script imprime mas abajo. Sin esto revienta con
# UnicodeEncodeError antes de mostrar un solo resultado (ya paso en la v2).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

RAIZ = Path(__file__).resolve().parents[1]
CFG = RAIZ / "config" / "busqueda_antecedentes.yaml"
REPORTES = RAIZ / "reportes"
PAUSA = 1.0
POR_PAGINA = 100


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def aplana(s: str) -> str:
    """Normaliza y colapsa espacios. Sin esto, «pre-packaged foods» normalizado
    queda «pre packaged foods» con dos espacios y nunca casa."""
    return re.sub(r"\s+", " ", norma(s)).strip()


def clave_titulo(t: str) -> str:
    return aplana(t)[:90]


def clave_doi(d: str) -> str:
    d = str(d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d


def frases_de(consulta: str) -> list[str]:
    """Las frases entrecomilladas de la consulta. Son lo que el investigador
    quiso buscar; el resto de la cadena son palabras de contexto."""
    return [f for f in (aplana(x) for x in re.findall(r'"([^"]+)"', consulta)) if f]


def exigencias(consulta: str, regla: dict, usar_frases: bool = True) -> list[str]:
    """Todo lo que tiene que aparecer literalmente. Las frases de la consulta
    se SUMAN a lo que declare el YAML; nunca lo sustituyen."""
    fuera = list(frases_de(consulta)) if usar_frases else []
    fuera += [aplana(t) for t in (regla.get("requiere_todos") or [])]
    return [t for t in fuera if t]


def texto_de(fila: dict) -> str:
    return aplana(f"{fila.get('titulo','')} {fila.get('resumen','')}")


def cumple_reglas_yaml(fila: dict, regla: dict) -> bool:
    """La verificacion de la v2, conservada tal cual para poder comparar."""
    texto = texto_de(fila)
    for t in regla.get("requiere_todos") or []:
        if aplana(t) not in texto:
            return False
    alguno = regla.get("requiere_alguno") or []
    if alguno and not any(aplana(t) in texto for t in alguno):
        return False
    return True


def clasifica(fila: dict, regla: dict, consulta: str,
              usar_frases: bool = True) -> str:
    """Tres cajones.

    estricto -> trae TODAS las frases de la consulta y todo lo que exige el
                YAML. Es lo unico citable.
    laxo     -> cumple las reglas del YAML pero le falta alguna frase. El
                buscador lo emparejo por otro campo. Puede ser bueno; se criba
                a mano.
    fuera    -> ni una cosa ni la otra.
    """
    texto = texto_de(fila)
    if not cumple_reglas_yaml(fila, regla):
        return "fuera"
    faltantes = [t for t in exigencias(consulta, regla, usar_frases) if t not in texto]
    return "laxo" if faltantes else "estricto"


def pedir(url: str, correo: str, intentos: int = 3) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"colorantes-mx/3.0 (mailto:{correo})",
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
    """Usa filter=title_and_abstract.search, que respeta comillas para frase."""
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
            autorias = w.get("authorships", [])
            paises = {i.get("country_code")
                      for a in autorias
                      for i in a.get("institutions", []) if i.get("country_code")}
            autores = [(a.get("author") or {}).get("display_name")
                       for a in autorias]
            fuente = (w.get("primary_location") or {}).get("source") or {}
            salida.append({
                "fuente_api": "OpenAlex",
                "doi": clave_doi(w.get("doi") or ""),
                "titulo": w.get("title") or w.get("display_name") or "",
                "autores": "; ".join(a for a in autores if a),
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
    """Red de seguridad y nada mas. No tiene busqueda de frase y no devuelve
    resumen en dos de cada tres registros, asi que casi todo lo suyo muere en la
    verificacion. Se conserva para no perder algo que OpenAlex no indexe."""
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
            autores = [", ".join(x for x in (a.get("family"), a.get("given")) if x)
                       or a.get("name", "")
                       for a in (w.get("author") or [])]
            salida.append({
                "fuente_api": "Crossref",
                "doi": clave_doi(w.get("DOI", "")),
                "titulo": (w.get("title") or [""])[0],
                "autores": "; ".join(a for a in autores if a),
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
    texto = aplana(f"{fila['titulo']} {fila['resumen']} {fila['revista']}")
    p = 3 * sum(1 for t in reglas["terminos_fuertes"] if aplana(t) in texto)
    p += 5 * sum(1 for t in reglas["terminos_pais"] if aplana(t) in texto)
    if "mx" in (fila.get("paises") or "").lower():
        p += 6
    if fila.get("idioma") in reglas["idiomas_interes"]:
        p += 1
    return p


def a_ris(df: pd.DataFrame) -> str:
    """Completo y con autores. La v2 escribia df.head(200) sin AU ni AB, y al
    importarlo a Zotero quedaban 200 fichas sin autor."""
    fuera = []
    for r in df.itertuples():
        fuera += ["TY  - JOUR", f"TI  - {r.titulo}"]
        for a in str(getattr(r, "autores", "") or "").split(";"):
            if a.strip():
                fuera.append(f"AU  - {a.strip()}")
        if r.anio and str(r.anio) != "nan":
            fuera.append(f"PY  - {int(r.anio)}")
        if r.revista:
            fuera.append(f"JO  - {r.revista}")
        if r.doi:
            fuera.append(f"DO  - {r.doi}")
        if getattr(r, "url", ""):
            fuera.append(f"UR  - {r.url}")
        if getattr(r, "idioma", ""):
            fuera.append(f"LA  - {r.idioma}")
        resumen = str(getattr(r, "resumen", "") or "")
        if resumen and resumen != "nan":
            fuera.append("AB  - " + re.sub(r"\s+", " ", resumen))
        fuera += [f"KW  - bloque:{r.bloque}",
                  "KW  - proyecto:colorantes-mx-cienciauat",
                  "KW  - busqueda-antecedentes", "ER  - ", ""]
    return "\n".join(fuera)


def revisa_control(cfg: dict, corpus: pd.DataFrame, laxos: list[dict],
                   descartados: list[dict]) -> list[dict]:
    """Donde murio cada trabajo conocido. La distincion que importa no es «lo
    trajo o no», sino si lo mato la cadena o la regla."""
    en_corpus = {clave_doi(d) for d in corpus.get("doi", [])}
    en_laxo = {clave_doi(f.get("doi", "")) for f in laxos}
    en_fuera = {clave_doi(f.get("doi", "")) for f in descartados}
    fuera = []
    for c in cfg.get("control_recuperacion") or []:
        d = clave_doi(c["doi"])
        if d in en_corpus:
            estado = "en el corpus"
        elif d in en_laxo:
            estado = "solo por revisar"
        elif d in en_fuera:
            estado = "recuperado y descartado"
        else:
            estado = "no recuperado"
        fuera.append({"etiqueta": c["etiqueta"], "doi": c["doi"], "estado": estado})
    return fuera


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bloque", default=None)
    ap.add_argument("--simulacro", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    correo = cfg["meta"]["correo_contacto"]
    desde = cfg["meta"]["desde_anio"]
    tope = cfg["meta"].get("max_por_consulta", 200)
    usar_frases = cfg["meta"].get("exigir_frases_de_la_consulta", True)
    bloques = cfg["bloques"]
    if args.bloque:
        if args.bloque not in bloques:
            raise SystemExit(f"Bloque desconocido. Hay: {', '.join(bloques)}")
        bloques = {args.bloque: bloques[args.bloque]}

    if args.simulacro:
        for nombre, b in bloques.items():
            print(f"\n  {nombre} — {b['pregunta']}")
            for c in b["consultas"]:
                q = c["q"].strip()
                ex = exigencias(q, c, usar_frases)
                alguno = c.get("requiere_alguno") or []
                print(f"    · {q}")
                print(f"        exige todos → {', '.join(ex) if ex else '(nada)'}")
                if alguno:
                    print(f"        exige alguno → {', '.join(alguno)}")
        print(f"\n  Frases de la consulta como regla: {usar_frases}.")
        print("  Simulacro: no se consulto nada.")
        return

    filas, laxos, descartadas, bitacora = [], [], [], []
    hoy = date.today().isoformat()
    for nombre, b in bloques.items():
        print(f"\n  {nombre}")
        for regla in b["consultas"]:
            consulta = regla["q"].strip()
            print(f"    «{consulta}»")
            for etiqueta, fn in (("OpenAlex", openalex), ("Crossref", crossref)):
                res, total = fn(consulta, desde, correo, tope)
                cajones = {"estricto": [], "laxo": [], "fuera": []}
                for r in res:
                    r["bloque"], r["consulta"] = nombre, consulta
                    cajones[clasifica(r, regla, consulta, usar_frases)].append(r)
                print(f"      {etiqueta}: {total} declarados · {len(res)} recuperados "
                      f"· {len(cajones['estricto'])} CONFIRMADOS "
                      f"· {len(cajones['laxo'])} por revisar")
                filas += cajones["estricto"]
                laxos += cajones["laxo"]
                descartadas += cajones["fuera"]
                bitacora.append({
                    "bloque": nombre, "consulta": consulta, "fuente": etiqueta,
                    "declarados": total, "recuperados": len(res),
                    "confirmados": len(cajones["estricto"]),
                    "por_revisar": len(cajones["laxo"]), "fecha": hoy})
                time.sleep(PAUSA)

    if not filas:
        raise SystemExit(
            "Cero confirmados. Si tampoco hubo recuperados, revisa la conexion. "
            "Si hubo recuperados pero todos cayeron en 'por revisar', las frases "
            "de las consultas no aparecen en los textos: revisa 13_por_revisar.csv "
            "antes de aflojar nada.")

    df = pd.DataFrame(filas)
    antes = len(df)
    df["_clave"] = df.apply(
        lambda r: clave_doi(r.doi) if r.doi else clave_titulo(r.titulo), axis=1)
    df = (df.sort_values("citas", ascending=False)
            .drop_duplicates("_clave").drop(columns="_clave"))
    df["relevancia"] = df.apply(lambda r: puntuar(r, cfg["relevancia"]), axis=1)
    df = df.sort_values(["relevancia", "citas"], ascending=False)
    for c in ("revisado", "pertinente", "nota"):
        df[c] = ""

    REPORTES.mkdir(exist_ok=True)
    cols = ["relevancia", "titulo", "autores", "anio", "revista", "idioma", "paises",
            "citas", "doi", "bloque", "consulta", "fuente_api", "url",
            "revisado", "pertinente", "nota", "resumen"]
    df[cols].to_csv(REPORTES / "13_antecedentes.csv", index=False, encoding="utf-8-sig")
    (REPORTES / "13_antecedentes.ris").write_text(a_ris(df), encoding="utf-8")

    cols_cortas = ["titulo", "autores", "anio", "revista", "doi", "bloque",
                   "consulta", "fuente_api"]
    if laxos:
        lx = pd.DataFrame(laxos).drop_duplicates(subset="titulo")
        lx.reindex(columns=cols_cortas + ["resumen"]).to_csv(
            REPORTES / "13_por_revisar.csv", index=False, encoding="utf-8-sig")
    if descartadas:
        pd.DataFrame(descartadas).reindex(columns=cols_cortas).to_csv(
            REPORTES / "13_descartados.csv", index=False, encoding="utf-8-sig")

    control = revisa_control(cfg, df, laxos, descartadas)

    bit = pd.DataFrame(bitacora)
    tasa = round(100 * bit.confirmados.sum() / max(bit.recuperados.sum(), 1), 1)
    por_fuente = (bit.groupby("fuente")[["recuperados", "confirmados"]]
                    .sum().reset_index())
    n_control = sum(1 for c in control if c["estado"] == "en el corpus")

    lineas = [
        "# Bitácora de búsqueda de antecedentes", "",
        f"**Fecha de ejecución:** {hoy}  ",
        f"**Ventana temporal:** desde {desde}  ",
        "**Fuentes:** OpenAlex y Crossref, por interfaz de programación, sin llave.  ",
        f"**Consultas:** {bit.consulta.nunique()} cadenas en {bit.bloque.nunique()} bloques.  ",
        f"**Confirmados:** {antes}; **únicos tras deduplicar por DOI y título:** {len(df)}.",
        "",
        "## Qué significa cada columna", "",
        "**Declarados** es lo que la interfaz dice tener. No es un resultado de "
        "búsqueda: incluye todo lo que comparta alguna palabra.", "",
        "**Confirmados** son los que contienen literalmente, en el título o el "
        "resumen recuperados, **todas las frases entrecomilladas de la propia "
        "consulta** más lo que exija la regla. **Es la única cifra citable.**", "",
        "**Por revisar** cumplen la regla pero les falta alguna frase: el buscador "
        "los emparejó por otro campo. Quedan en `13_por_revisar.csv` para cribado "
        "manual y **no cuentan** en ninguna afirmación del artículo.", "",
        f"Tasa global de confirmación: **{tasa} %** de lo recuperado.", "",
        "### Por fuente", "",
        "| Fuente | Recuperados | Confirmados |", "|---|---|---|",
    ]
    for r in por_fuente.itertuples():
        lineas.append(f"| {r.fuente} | {r.recuperados} | **{r.confirmados}** |")
    lineas += [
        "",
        "Crossref se mantiene como red de seguridad, no como fuente de "
        "descubrimiento: no ofrece búsqueda de frase y no devuelve resumen en la "
        "mayoría de sus registros, de modo que la verificación solo puede leer el "
        "título. Su aporte al corpus se reporta tal como sale.", "",
        "## Control de recuperación", "",
        "Se comprobó si la estrategia alcanza trabajos que ya se sabía que eran "
        "los vecinos más cercanos. **«No recuperado» señala una cadena "
        "insuficiente; «recuperado y descartado» señalaría un filtro mal "
        "calibrado**, que es el problema grave.", "",
        f"Resultado: **{n_control} de {len(control)}** en el corpus.", "",
        "| Trabajo | DOI | Estado |", "|---|---|---|",
    ]
    for c in control:
        lineas.append(f"| {c['etiqueta']} | `{c['doi']}` | {c['estado']} |")
    lineas += [
        "",
        "> Una búsqueda no demuestra inexistencia. Con este control declarado, lo "
        "que la bitácora sostiene es «no se identificaron trabajos que…», nunca "
        "«no existen».", "",
        "## Resultados por consulta", "",
        "| Bloque | Consulta | Fuente | Declarados | Recuperados | Confirmados | Por revisar |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in bit.itertuples():
        lineas.append(f"| {r.bloque} | `{r.consulta}` | {r.fuente} | "
                      f"{r.declarados} | {r.recuperados} | **{r.confirmados}** | "
                      f"{r.por_revisar} |")
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

    print(f"\n  confirmados {antes} → {len(df)} únicos")
    print(f"  por revisar a mano: {len(laxos)}   ·   descartados: {len(descartadas)}")
    print(f"  tasa de confirmación: {tasa} %")
    print(f"\n  control de recuperación: {n_control} de {len(control)} en el corpus")
    for c in control:
        marca = "ok " if c["estado"] == "en el corpus" else "-- "
        print(f"    {marca}{c['estado']:<24} {c['etiqueta']}")
    print("\n  los 15 más relevantes:")
    print(df.head(15)[["relevancia", "anio", "titulo"]].to_string(index=False))


if __name__ == "__main__":
    main()
