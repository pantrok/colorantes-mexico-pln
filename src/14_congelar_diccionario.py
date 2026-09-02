"""Paso 14 — CONGELAR EL DICCIONARIO.

    python src/14_congelar_diccionario.py --simulacro
    python src/14_congelar_diccionario.py --aplicar
    python src/14_congelar_diccionario.py --verificar

QUE SIGNIFICA CONGELAR, EN CONCRETO. No es una promesa: son cuatro cosas.

  1. Se aplica el veredicto de la Dra. (config/decisiones_dra.yaml) y la fusion
     de las formas oficiales del DOF, en ese orden y una sola vez.

  2. Se verifican SIETE INVARIANTES antes de escribir nada. Son las trampas que
     ya nos costaron una corrida cada una: el orden de termino mas largo primero,
     la inversion de los azules mexicanos respecto de la FD&C, que «beta caroteno
     sintetico» resuelva antes que «beta caroteno», que «anaranjado alimentos 5»
     no este, que ningun termino viva en dos clases, que los terminos que la
     experta marco como no-colorante hayan salido, y que los terminos en
     desacuerdo NO se hayan borrado. Si una falla, no se congela.

  3. Se calcula un HASH CANONICO del contenido y se escribe config/colorantes.lock.json
     junto con un manifiesto legible. El hash no depende del formato del YAML:
     se calcula sobre la estructura normalizada y ordenada.

  4. A partir de ahi, tests/test_congelado.py falla si el diccionario cambia sin
     que suba la version. Eso es lo que convierte el congelamiento en un hecho
     verificable y no en un acuerdo verbal.

POR QUE IMPORTA. La anotacion manual de 600 productos se hace CONTRA este
diccionario. Si despues se le agrega o se le quita un termino, la anotacion
deja de medir lo que se anoto y hay que rehacerla. El hash es lo que permite
escribir en Metodos «se anoto contra la version v1.0, sha256 abc123...» y que
eso sea comprobable.

QUE NO HACE. No toca el vocabulario legal de referencia (config/acuerdo_colorantes.yaml).
Que la ley liste un termino que nadie imprime es parte del argumento del
articulo, no un error que haya que limpiar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
CFG = RAIZ / "config"
DICC = CFG / "colorantes.yaml"
ADIC = CFG / "colorantes_adiciones.yaml"
DEC = CFG / "decisiones_dra.yaml"
LOCK = CFG / "colorantes.lock.json"
MANIF = CFG / "DICCIONARIO_CONGELADO.md"
REPORTES = RAIZ / "reportes"

VERSION = "1.1"
BLOQUES_CLASE = ("sinteticos", "naturales", "minerales", "carmin")


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&' -]+", " ", s)).strip()


# --------------------------------------------------------------- estructura
# El YAML del diccionario admite dos formas por codigo:
#     E102: [termino, termino, ...]
#     E102: {tono: ..., base: ..., terminos: [...], requiere_contexto: true}
# Todo lo de abajo trabaja con las dos sin distinguir.

def terminos_de(val) -> list:
    if isinstance(val, dict):
        return list(val.get("terminos") or [])
    if isinstance(val, list):
        return list(val)
    raise TypeError(f"forma de codigo no reconocida: {type(val)}")


def set_terminos(val, nuevos: list):
    if isinstance(val, dict):
        val["terminos"] = nuevos
        return val
    return nuevos


def es_entrada_de_codigo(val) -> bool:
    """Una entrada de codigo es una lista de terminos, o un dict con `terminos`."""
    if isinstance(val, list):
        return all(isinstance(x, str) for x in val)
    return isinstance(val, dict) and isinstance(val.get("terminos"), list)


def es_mapa_de_codigos(bloque: str, val) -> bool:
    """El YAML tiene bloques que NO son mapas de codigo y la version 1.0
    tropezaba con ellos:

      genericos:        cuelga una lista de terminos DIRECTAMENTE del bloque.
                        Estructuralmente es identico a un mapa de codigos con un
                        solo codigo llamado «terminos», asi que la clave
                        reservada `terminos` a nivel de bloque es el corte.
      sustituibilidad:  trae reglas, candidatos y notas, no terminos.
    """
    if bloque == "meta" or not isinstance(val, dict) or not val:
        return False
    if "terminos" in val:          # el bloque ES una lista de terminos
        return False
    return all(es_entrada_de_codigo(v) for v in val.values())


def recorre(dicc: dict):
    """Devuelve (bloque, codigo, valor) por cada codigo del diccionario."""
    for bloque, codigos in dicc.items():
        if not es_mapa_de_codigos(bloque, codigos):
            continue
        for codigo, val in codigos.items():
            yield bloque, codigo, val


def indice_terminos(dicc: dict) -> dict:
    """termino normalizado -> lista de (bloque, codigo)."""
    idx = {}
    for bloque, codigo, val in recorre(dicc):
        for t in terminos_de(val):
            idx.setdefault(norma(t), []).append((bloque, codigo))
    return idx


# ------------------------------------------------------------------- conteos

def carga_conteos() -> dict:
    """termino normalizado -> detecciones. Busca en los reportes disponibles.
    Si no encuentra ninguno, devuelve {} y el script se niega a podar."""
    candidatos = ["07_terminos_forma.csv", "08_cobertura_terminos.csv",
                  "12_terminos_mexico.csv"]
    import csv
    for nombre in candidatos:
        ruta = REPORTES / nombre
        if not ruta.exists():
            continue
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        if not filas:
            continue
        cols = filas[0].keys()
        col_t = next((c for c in cols if norma(c) in
                      ("termino", "forma", "termino forma", "texto")), None)
        col_n = next((c for c in cols if norma(c) in
                      ("detecciones", "n", "veces", "conteo", "productos")), None)
        if not col_t or not col_n:
            continue
        out = {}
        for r in filas:
            try:
                out[norma(r[col_t])] = int(float(r[col_n] or 0))
            except (TypeError, ValueError):
                continue
        if out:
            print(f"    conteos leidos de {nombre}: {len(out)} terminos")
            return out
    return {}


# -------------------------------------------------------------- invariantes

class Falla(Exception):
    pass


def verifica(dicc: dict, dec: dict, avisos: list) -> None:
    idx = indice_terminos(dicc)
    inv = dec["invariantes"]

    # 1. ningun termino en dos clases distintas
    if inv.get("sin_termino_en_dos_clases"):
        for t, donde in idx.items():
            clases = {b for b, _ in donde}
            if len(clases) > 1:
                raise Falla(f"«{t}» aparece en {sorted(clases)}. Un termino no "
                            f"puede vivir en dos clases: rompe el eje de origen.")

    # 2. pares obligatorios (la inversion de los azules)
    for par in inv.get("pares_obligatorios") or []:
        t, esperado = norma(par["termino"]), par["codigo"]
        donde = idx.get(t)
        if not donde:
            raise Falla(f"falta «{par['termino']}», que debe mapear a {esperado}. "
                        f"{par['porque']}")
        codigos = {c for _, c in donde}
        if codigos != {esperado}:
            raise Falla(f"«{par['termino']}» mapea a {sorted(codigos)} y debe ser "
                        f"{esperado}. {par['porque']}")

    # 3. el largo resuelve antes que el corto
    for regla in inv.get("resuelve_antes") or []:
        largo, corto = norma(regla["largo"]), norma(regla["corto"])
        if largo not in idx:
            raise Falla(f"falta «{regla['largo']}». {regla['porque']}")
        if corto in idx and len(largo) <= len(corto):
            raise Falla(f"«{regla['largo']}» no es mas largo que «{regla['corto']}»; "
                        f"el emparejador por longitud no puede garantizar el orden.")

    # 4. terminos prohibidos
    for pr in inv.get("terminos_prohibidos") or []:
        if norma(pr["termino"]) in idx:
            raise Falla(f"«{pr['termino']}» sigue en el diccionario. {pr['porque']}")

    # 5a. codigos que deben haber desaparecido por completo
    presentes = {c for _, c, _ in recorre(dicc)}
    for g in dec.get("fuera_del_eje") or []:
        if g.get("codigo_completo") and g["codigo"] in presentes:
            raise Falla(f"{g['codigo']} sigue en el diccionario y debia salir "
                        f"completo: {g['motivo']}")

    # 5. lo que la experta saco del eje, salio
    for grupo in dec.get("fuera_del_eje") or []:
        for t in grupo["terminos"]:
            if norma(t) in idx:
                raise Falla(f"«{t}» ({grupo['codigo']}) deberia haber salido del eje "
                            f"de color: {grupo['motivo']}")

    # 6. lo que esta en desacuerdo, NO se borro
    for d in dec["desacuerdo_experta_vs_corpus"]["terminos"]:
        if norma(d["termino"]) not in idx:
            raise Falla(
                f"«{d['termino']}» ya no esta. Tiene {d['detecciones']} detecciones "
                f"en el corpus. La regla es que P1 la decide el corpus, no la "
                f"revisora: borrarlo encoge la clase natural, que es la que "
                f"sostiene el resultado.")

    # 7. orden mas largo primero, dentro de cada codigo
    if inv.get("ordenamiento_mas_largo_primero"):
        for bloque, codigo, val in recorre(dicc):
            ts = [norma(t) for t in terminos_de(val)]
            if ts != sorted(ts, key=len, reverse=True):
                avisos.append(f"{bloque}/{codigo}: terminos reordenados por longitud")

    # aviso, no falla: el nombre del bloque ya no describe la clase analitica
    for bloque, codigo, val in recorre(dicc):
        if isinstance(val, dict) and val.get("base") == "mineral" and bloque != "minerales":
            avisos.append(f"{codigo} vive en el bloque «{bloque}» y declara "
                          f"base: mineral. La clase analitica se asigna en "
                          f"src/util.py, no aqui: confirma que ese mapa lo trata "
                          f"como pigmento inorganico y no como natural.")

    # aviso, no falla: subcadenas entre codigos distintos
    largos = sorted(idx, key=len, reverse=True)
    for i, a in enumerate(largos):
        for b in largos[i + 1:]:
            if len(b) < 4 or b not in a:
                continue
            if {c for _, c in idx[a]} != {c for _, c in idx[b]}:
                avisos.append(f"«{b}» es subcadena de «{a}» y son codigos distintos; "
                              f"depende del orden por longitud")
                break


# ------------------------------------------------------------------ aplicar

def aplica(dicc: dict, dec: dict, conteos: dict, cambios: list) -> dict:
    # a) sacar del eje
    #    `codigo_completo: true` elimina el codigo entero. Hace falta porque la
    #    revisora juzgo SUSTANCIAS y el archivo que reviso solo traia los
    #    terminos con detecciones: los sinonimos sin detecciones nunca se le
    #    mostraron y sobrevivian a una poda termino por termino.
    completos = {g["codigo"] for g in (dec.get("fuera_del_eje") or [])
                 if g.get("codigo_completo")}
    for bloque in list(dicc):
        if not es_mapa_de_codigos(bloque, dicc[bloque]):
            continue
        for codigo in list(dicc[bloque]):
            if codigo in completos:
                ts = terminos_de(dicc[bloque][codigo])
                cambios.append(f"codigo completo {bloque}/{codigo}: se elimina "
                               f"({len(ts)} terminos: {', '.join(ts)})")
                del dicc[bloque][codigo]

    fuera = {norma(t) for g in (dec.get("fuera_del_eje") or []) for t in g["terminos"]}
    for bloque, codigo, val in recorre(dicc):
        ts = terminos_de(val)
        quedan = [t for t in ts if norma(t) not in fuera]
        if len(quedan) != len(ts):
            for t in ts:
                if norma(t) in fuera:
                    cambios.append(f"fuera del eje  {bloque}/{codigo}: «{t}»")
            dicc[bloque][codigo] = set_terminos(val, quedan)

    # quitar codigos que se quedaron sin terminos
    for bloque in list(dicc):
        if not es_mapa_de_codigos(bloque, dicc[bloque]):
            continue
        for codigo in list(dicc[bloque]):
            if not terminos_de(dicc[bloque][codigo]):
                cambios.append(f"codigo vacio    {bloque}/{codigo}: se elimina")
                del dicc[bloque][codigo]

    # b) podar variantes nuestras, solo con cero detecciones confirmadas
    poda = [norma(t) for t in (dec.get("podar_si_cero_detecciones") or [])]
    if not conteos:
        cambios.append("PODA OMITIDA: no se encontro archivo de conteos en reportes/. "
                       "Los terminos de `podar_si_cero_detecciones` se conservan.")
    else:
        for bloque, codigo, val in recorre(dicc):
            ts = terminos_de(val)
            quedan = []
            for t in ts:
                n = norma(t)
                if n in poda:
                    c = conteos.get(n, 0)
                    if c == 0:
                        cambios.append(f"podado         {bloque}/{codigo}: «{t}» (0 detecciones)")
                        continue
                    cambios.append(f"NO podado      {bloque}/{codigo}: «{t}» tiene {c} "
                                   f"detecciones; pasa a desacuerdo declarado")
                quedan.append(t)
            dicc[bloque][codigo] = set_terminos(val, quedan)

    # c) contexto obligatorio, marcado en el propio YAML
    for codigo_obj in dec["requieren_contexto"]["codigos_a_agregar"]:
        for bloque, codigo, val in recorre(dicc):
            if codigo != codigo_obj:
                continue
            if not isinstance(val, dict):
                val = {"terminos": list(val)}
                dicc[bloque][codigo] = val
            if not val.get("requiere_contexto"):
                val["requiere_contexto"] = True
                cambios.append(f"contexto       {bloque}/{codigo}: requiere_contexto = true")

    # d) orden canonico: mas largo primero
    for bloque, codigo, val in recorre(dicc):
        ts = terminos_de(val)
        orden = sorted(ts, key=lambda t: (-len(norma(t)), norma(t)))
        if orden != ts:
            dicc[bloque][codigo] = set_terminos(val, orden)
    return dicc


# --------------------------------------------------------------------- hash

def canonico(dicc: dict) -> str:
    """Estructura normalizada y ordenada. No depende del formato del YAML."""
    out = {}
    for bloque, codigo, val in recorre(dicc):
        d = out.setdefault(bloque, {})
        d[codigo] = {
            "terminos": [norma(t) for t in terminos_de(val)],
            "requiere_contexto": bool(isinstance(val, dict)
                                      and val.get("requiere_contexto")),
        }
    return json.dumps(out, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def huella(dicc: dict) -> str:
    return hashlib.sha256(canonico(dicc).encode("utf-8")).hexdigest()


def cuenta(dicc: dict) -> tuple[int, int]:
    codigos = terminos = 0
    for _, _, val in recorre(dicc):
        codigos += 1
        terminos += len(terminos_de(val))
    return codigos, terminos


# --------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--simulacro", action="store_true",
                   help="muestra que cambiaria y verifica invariantes; no escribe")
    g.add_argument("--aplicar", action="store_true", help="congela")
    g.add_argument("--verificar", action="store_true",
                   help="comprueba que el diccionario en disco coincide con el lock")
    ap.add_argument("--rehacer", action="store_true",
                    help="permite volver a congelar sobre un lock existente")
    args = ap.parse_args()

    if not DICC.exists():
        raise SystemExit(f"No encuentro {DICC}")
    dicc = yaml.safe_load(DICC.read_text(encoding="utf-8"))
    dec = yaml.safe_load(DEC.read_text(encoding="utf-8"))

    # ---- verificar
    if args.verificar:
        if not LOCK.exists():
            raise SystemExit("No hay config/colorantes.lock.json: no esta congelado.")
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        h = huella(dicc)
        ok = h == lock["sha256"]
        print(f"  esperado : {lock['sha256']}")
        print(f"  en disco : {h}")
        print("\n  COINCIDE" if ok else
              "\n  NO COINCIDE. El diccionario cambio despues de congelar.\n"
              "  Si el cambio es deliberado, sube la version y vuelve a congelar\n"
              "  con --aplicar --rehacer. Si no, restaura desde el respaldo.")
        sys.exit(0 if ok else 1)

    if args.aplicar and LOCK.exists() and not args.rehacer:
        raise SystemExit("Ya esta congelado. Para rehacerlo: --aplicar --rehacer")

    codigos0, terminos0 = cuenta(dicc)
    print(f"\n  ANTES: {codigos0} codigos, {terminos0} terminos")

    if ADIC.exists():
        ad = yaml.safe_load(ADIC.read_text(encoding="utf-8"))
        # Una forma de colorantes_adiciones.yaml puede faltar en el diccionario
        # por dos razones muy distintas: (a) nunca se fusiono, o (b) se
        # fusiono y una corrida anterior de ESTE script ya la podo por cero
        # detecciones confirmadas (poda legitima, ver `podar_si_cero_detecciones`
        # en decisiones_dra.yaml). Sin distinguirlas, el aviso trata la version
        # ya congelada y correctamente depurada como si la fusion siguiera
        # pendiente, y --aplicar se niega a congelar sobre datos que en
        # realidad ya estan al dia.
        podadas = {norma(t) for t in (dec.get("podar_si_cero_detecciones") or [])}
        pendientes = []
        idx = indice_terminos(dicc)
        for bloque, codigos in ad.items():
            if bloque in ("meta", "excluidas") or not isinstance(codigos, dict):
                continue
            for _, val in codigos.items():
                for t in terminos_de(val):
                    if norma(t) not in idx and norma(t) not in podadas:
                        pendientes.append(t)
        if pendientes:
            print(f"\n  AVISO: {len(pendientes)} formas oficiales de "
                  f"colorantes_adiciones.yaml todavia NO estan en el diccionario.")
            print("  Corre antes `python src/fusionar_diccionario.py --aplicar`.")
            print("  Ejemplos:", ", ".join(pendientes[:5]))
            if args.aplicar:
                raise SystemExit("  No se congela con la fusion pendiente.")
        else:
            print("  fusion del DOF: ya aplicada (o podada a proposito)")

    print("\n  conteos para la poda:")
    conteos = carga_conteos()
    if not conteos:
        print("    ninguno encontrado en reportes/")

    cambios, avisos = [], []
    dicc = aplica(dicc, dec, conteos, cambios)

    print(f"\n  CAMBIOS ({len(cambios)})")
    for c in cambios:
        print("   ", c)

    print("\n  INVARIANTES")
    try:
        verifica(dicc, dec, avisos)
    except Falla as e:
        print(f"\n  FALLA: {e}\n\n  No se congela.")
        sys.exit(1)
    print("    las siete pasan")
    for a in dict.fromkeys(avisos):
        print("    aviso:", a)

    codigos1, terminos1 = cuenta(dicc)
    h = huella(dicc)
    print(f"\n  DESPUES: {codigos1} codigos, {terminos1} terminos")
    print(f"  sha256: {h}")

    if args.simulacro:
        print("\n  Simulacro: no se escribio nada.")
        return

    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    respaldo = CFG / f"colorantes.previo-{sello}.yaml"
    shutil.copy2(DICC, respaldo)

    dicc.setdefault("meta", {})
    dicc["meta"].update({
        "version": VERSION,
        "congelado": True,
        "fecha_congelamiento": sello,
        "sha256": h,
        "veredicto": dec["meta"]["fecha_veredicto"],
    })
    DICC.write_text(
        yaml.safe_dump(dicc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")

    LOCK.write_text(json.dumps({
        "version": VERSION,
        "sha256": h,
        "fecha": sello,
        "codigos": codigos1,
        "terminos": terminos1,
        "veredicto_dra": dec["meta"]["fecha_veredicto"],
        "respaldo": respaldo.name,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    escribe_manifiesto(dicc, dec, h, sello, codigos1, terminos1,
                       codigos0, terminos0, cambios)

    print(f"\n  CONGELADO v{VERSION}")
    print(f"  respaldo: {respaldo.name}")
    print(f"  lock:     {LOCK.name}")
    print(f"  manifiesto: {MANIF.name}")
    print("\n  A partir de aqui, `pytest tests/test_congelado.py` falla si el")
    print("  diccionario cambia sin subir la version.")


def escribe_manifiesto(dicc, dec, h, sello, cod1, ter1, cod0, ter0, cambios):
    L = [
        f"# Diccionario de colorantes, versión {VERSION} — CONGELADO", "",
        f"**Fecha:** {sello}  ",
        f"**sha256:** `{h}`  ",
        f"**Códigos:** {cod1} (antes {cod0}) · **Términos:** {ter1} (antes {ter0})  ",
        f"**Veredicto de la revisora:** {dec['meta']['fecha_veredicto']}, "
        f"{dec['meta']['revisora']}", "",
        "## Qué quiere decir que esté congelado", "",
        "La anotación manual de 600 productos se hace **contra esta versión**. Si el "
        "diccionario cambia después, la anotación deja de medir lo que se anotó y hay "
        "que rehacerla. Por eso el hash: permite escribir en Métodos «se anotó contra "
        f"la versión {VERSION}, sha256 `{h[:16]}…`» y que eso sea comprobable.", "",
        "`tests/test_congelado.py` falla si el contenido cambia sin subir la versión.", "",
        "## Regla de decisión aplicada", "",
        "**P2, la función** — «cuando aparece así, ¿está para dar color?» — la decide "
        "la revisora. Es lo que el corpus no puede contestar y por eso se preguntó.", "",
        "**P1, la atestiguación** — «¿se escribe así en una etiqueta mexicana?» — la "
        "decide el corpus. Una forma con detecciones no se borra porque la revisora no "
        "la haya visto. Podar por P1 solo cuando el término tiene cero detecciones.", "",
        "## Cambios aplicados", "",
    ]
    L += [f"- {c}" for c in cambios] or ["- ninguno"]
    L += ["", "## Desacuerdo declarado", "",
          "Términos que la revisora marcó como no habituales en etiqueta mexicana y que "
          "el corpus sin embargo contiene. **No se borraron.** Borrar formas atestiguadas "
          "porque no son habituales encogería la clase natural, que es justo la que "
          "sostiene el resultado del artículo.", "",
          "| Término | Código | Detecciones |", "|---|---|---|"]
    for d in dec["desacuerdo_experta_vs_corpus"]["terminos"]:
        L.append(f"| {d['termino']} | {d['codigo']} | {d['detecciones']} |")
    L += ["", "## Fuera del eje de color", "",
          "Términos con P2 = no: no son colorantes cuando aparecen así en una etiqueta "
          "mexicana. Salen del conteo. **Siguen existiendo en el vocabulario legal de "
          "referencia** (`acuerdo_colorantes.yaml`), que no se toca: que la ley los "
          "liste es parte del argumento del artículo.", ""]
    for g in dec.get("fuera_del_eje") or []:
        marca = " *(discrepa del Acuerdo)*" if g.get("discrepa_de_la_ley") else ""
        L.append(f"- **{g['codigo']}** — {', '.join(g['terminos'])}: "
                 f"{g['motivo'].strip()}{marca}")
    L += ["", "## Lo que NO se congeló", "",
          "`config/acuerdo_colorantes.yaml`, el vocabulario legal de referencia. Que "
          "una forma legal no se imprima nunca es un hallazgo, no un error que limpiar.",
          "", "## Para descongelar", "",
          "Editar `config/decisiones_dra.yaml`, subir `VERSION` en el script y correr "
          "`--aplicar --rehacer`. **Si ya empezó la anotación, descongelar la invalida.**"]
    MANIF.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
