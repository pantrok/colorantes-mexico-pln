"""Paso 7 — LA CORRIDA QUE DECIDE QUE ARTICULO ES ESTE.

Corre DESPUES de 01. No depende de 05 ni de 06: recalcula todo desde el parquet.

Contesta cinco cosas que hoy no sabemos y que bloquean la escritura:

  A. FALSADOR 1 (bloqueante). La brecha, cruzada por FORMA DEL TERMINO que hizo
     la coincidencia (codigo E / nombre de sustancia / nombre de fuente) contra
     CLASE DE ORIGEN. Si la brecha se explica por la forma y el origen no anade
     nada, la tesis del articulo esta mal enunciada y hay que reescribirla como
     mediacion: origen -> convencion de nombrado -> visibilidad -> cifra.
     Prediccion dura: un sintetico declarado SIN codigo E deberia mostrar la
     misma brecha alta que un natural. Si eso pasa, el origen no es la variable.

  B. Agregado de brecha POR CLASE, que nunca se calculo. Bruto y depurado en
     paralelo, a nivel deteccion y a nivel producto, con IC de Wilson. Carmin
     aparte, minerales aparte. Ademas la MEDIANA por codigo, que es el
     estadistico que reporta Tseng (37.9 %) y el unico comparable con el.

  C. Estabilidad por GRUPO DE CONTRIBUYENTE. Si la brecha cambia mucho entre
     importaciones en bloque, aplicaciones de terceros y campana, estamos
     midiendo comportamiento de contribuyente y no del analizador.

  D. Recalculo bajo las definiciones de CHIU (2025) para que la comparacion con
     Hong Kong sea valida: ellos cuentan el caramelo E150 dentro de naturales.

  E. Muestra del CONJUNTO ANOTADO, 600 productos en cuatro estratos, con semilla
     fija y pesos de reponderacion declarados.

Reglas heredadas y no negociables:
  - El caramelo E150 queda FUERA del eje en el analisis principal. Solo entra en
    el bloque D, y marcado.
  - El carmin E120 se reporta APARTE del agregado natural.
  - Los codigos ambiguos solo cuentan si 'colorante' aparece a menos de 60
    caracteres. Mismo criterio que en 05 y 06, sin cambios.

Salidas en reportes/:
  07_forma_y_clase.json        todo el resumen
  07_falsador1_forma.csv       la tabla que decide la tesis
  07_brecha_por_codigo.csv     por codigo, bruto y depurado, con IC (va a Zenodo)
  07_terminos_forma.csv        asignacion termino -> forma, PARA AUDITAR A MANO
  07_muestra_anotacion.csv     los 600 productos a anotar
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
import pandas as pd

from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, terminos_ordenados, guardar_reporte)

AMBIGUOS = REQUIEREN_CONTEXTO
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60
SEMILLA = 20260825

CARMIN = "E120"
MINERALES = {"E170", "E171", "E172"}      # ni botanicos ni azoicos: se reportan aparte
# Historicamente solo traia E170/E171. E172 (oxidos de hierro) faltaba, asi
# que caia por defecto a "natural_botanico" via bloque -exactamente el aviso
# que 14_congelar_diccionario.py hace en cada corrida: la clase analitica la
# asigna este mapa, no el nombre del bloque del YAML, y aqui no se le habia
# hecho caso. E170 ya no tiene termino alguno tras el congelamiento v1.1
# (fuera del eje), asi que dejarlo en el set no cambia nada, pero se deja por
# historial.

# --- Estratos del conjunto anotado ---
ESTRATOS = {"sintetico": 150, "natural": 250, "ambiguo_descartado": 100, "sin_deteccion": 100}


# ---------------------------------------------------------------- utilidades

def wilson(exitos: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """IC95 de Wilson. Se usa este y no el normal porque varias celdas tienen
    proporciones pegadas a 0 o a 1 (E160a/b/c dan 100 %) y ahi el normal miente."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = exitos / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0.0, centro - margen), 1),
            round(100 * min(1.0, centro + margen), 1))


# ---------------------------------------------------- forma del termino (A)
# ADVERTENCIA: esta clasificacion es una DECISION, no un hecho. Se vuelca entera
# a 07_terminos_forma.csv para que la revise la Dra. antes de creerle al
# falsador 1. Si la asignacion esta mal, el resultado del falsador esta mal.

RE_CODIGO = re.compile(r"^\s*(e\s?-?\d{3}[a-z]{0,2}|ci\s?\d{4,5}|ins\s?\d{3})\s*$")

# Terminos que nombran la FUENTE biologica, no el compuesto. Lista explicita:
# si un termino no esta aqui y no es codigo, se clasifica como nombre de
# sustancia. Revisar contra el YAML cada vez que se agreguen terminos.
FUENTES = {
    "cochinilla", "carmin de cochinilla", "grana cochinilla", "achiote", "annato",
    "annatto", "bija", "urucum", "curcuma", "cúrcuma", "paprika", "páprika",
    "pimenton", "pimentón", "oleorresina de paprika", "betabel", "remolacha",
    "jugo de betabel", "jugo de remolacha", "zanahoria", "jugo de zanahoria",
    "zanahoria purpura", "zanahoria negra", "jamaica", "flor de jamaica",
    "hibisco", "uva", "jugo de uva", "col morada", "camote morado", "espirulina",
    "spirulina", "alga espirulina", "clorofila de alfalfa", "cempasuchil",
    "cempasúchil", "flor de cempasuchil", "tagete", "maiz morado", "maíz morado",
    "extracto de malta", "gardenia", "safflower", "cartamo", "cártamo",
}


def forma_de(termino: str) -> str:
    t = termino.strip().lower()
    if RE_CODIGO.match(t):
        return "codigo_e"
    # un termino puede traer el codigo embebido: "rojo allura ac (e129)"
    if re.search(r"\be\s?-?\d{3}", t) or re.search(r"\bci\s?\d{4,5}\b", t):
        return "codigo_e"
    if t in FUENTES or any(f in t for f in ("extracto de", "jugo de", "concentrado de")):
        return "nombre_fuente"
    return "nombre_sustancia"


def detectar_con_forma(texto: str, ordenados) -> list[tuple[str, str, str]]:
    """(codigo, bloque, termino) consumiendo el texto, del termino mas largo al
    mas corto. Replica la logica de construir_matchers/detectar pero conserva
    QUE termino coincidio, que es lo que el falsador 1 necesita."""
    restante = texto
    salida = []
    for termino, codigo, bloque in ordenados:
        if not termino:
            continue
        patron = re.compile(r"\b" + re.escape(termino) + r"\b")
        if patron.search(restante):
            salida.append((codigo, bloque, termino))
            restante = patron.sub(" ", restante)
    return salida


def con_contexto(texto: str, termino: str) -> bool:
    patron = re.compile(r"\b" + re.escape(termino) + r"\b")
    for m in patron.finditer(texto):
        ini, fin = max(0, m.start() - VENTANA), min(len(texto), m.end() + VENTANA)
        if RE_CONTEXTO.search(texto[ini:fin]):
            return True
    return False


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral"
    if bloque == "sinteticos":
        return "sintetico"
    if bloque == "naturales":
        return "natural"
    return "fuera_de_eje"


# ------------------------------------------------------------------- lectura

def columna(df, *candidatas):
    for c in candidatas:
        if c in df.columns:
            return c
    return None


def grupo_contribuyente(nombre: str) -> str:
    n = (nombre or "").lower()
    if not n:
        return "sin_dato"
    if "import" in n or n.startswith("usda"):
        return "importacion_bloque"
    if re.match(r"^openfoodfactsmx\d*$|^mx\d+$", n):
        return "campana_mx"
    if n in {"macrofactor", "foodvisor", "smoothie-app", "xpiry", "kiliweb",
             "yuka", "elcoco", "waistline-app", "inf", "openfoodfacts-contributors"}:
        return "app_terceros"
    return "individual"


def main() -> None:
    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)
    validos = set(dic["sinteticos"]) | set(dic["naturales"])
    caramelo = set(dic.get("fuera_de_eje", {}))

    ruta = INTERMEDIO / "productos_mx.parquet"
    cols = duckdb.sql(f"SELECT * FROM '{ruta}' LIMIT 1").df().columns.tolist()
    col_contrib = None
    for c in ("contribuidor", "creador", "creator", "contribuyente", "created_by", "usuario"):
        if c in cols:
            col_contrib = c
            break
    print(f"  columnas del parquet: {len(cols)}; contribuyente -> {col_contrib or 'NO DISPONIBLE'}")

    sel = "code, nombre_producto, ingredientes_texto, aditivos_tags, categorias, marcas"
    if col_contrib:
        sel += f", {col_contrib} AS contribuyente"
    df = duckdb.sql(f"""
        SELECT {sel} FROM '{ruta}'
        WHERE ingredientes_texto IS NOT NULL
          AND length(trim(ingredientes_texto)) > 0
    """).df()
    print(f"  productos con texto: {len(df):,}")

    # ------------------------------------------------ construccion de filas
    filas, pares = [], []          # pares = una fila por (producto, codigo)
    for t in df.itertuples(index=False):
        texto = normalizar(t.ingredientes_texto)
        tags = {str(a).replace("en:", "").upper() for a in como_lista(t.aditivos_tags)}
        dets = detectar_con_forma(texto, ordenados)
        # Agrupar por codigo, conservando TODOS los terminos que coincidieron
        # para ese codigo. CORREGIDO 05/09: un producto puede declarar el
        # mismo colorante con dos sinonimos (p.ej. "achiote" y "annatto",
        # ambos E160b); detectar_con_forma() los trae como dos entradas, y
        # antes cada una generaba su propia fila en `pares` -n y sin_tag
        # salian inflados-. Es una sola deteccion de ese codigo, no dos. El
        # contexto se evalua con OR entre todos sus terminos -mismo criterio
        # que 05_auditoria_brecha.py y 08_vocabulario_off.py-: basta que UNO
        # tenga "colorante" cerca. Se usa el primer termino (el mas largo,
        # porque `ordenados` va de mas largo a mas corto) para forma_de() y
        # como termino representativo. Ver BITACORA_PARCHES.md.
        terminos_por_codigo, orden_codigos = {}, []
        for codigo, bloque, termino in dets:
            if codigo not in terminos_por_codigo:
                orden_codigos.append(codigo)
                terminos_por_codigo[codigo] = (bloque, [])
            terminos_por_codigo[codigo][1].append(termino)
        contrib = getattr(t, "contribuyente", None) if col_contrib else None

        bruto_eje, depurado_eje, descartados = set(), set(), set()
        for codigo in orden_codigos:
            bloque, terminos = terminos_por_codigo[codigo]
            if bloque not in ("sinteticos", "naturales"):
                continue
            bruto_eje.add(codigo)
            termino = terminos[0]
            ok = codigo not in AMBIGUOS or any(con_contexto(texto, tm) for tm in terminos)
            if ok:
                depurado_eje.add(codigo)
            else:
                descartados.add(codigo)
            pares.append({
                "code": t.code, "codigo": codigo,
                "clase": clase_de(codigo, bloque),
                "forma": forma_de(termino), "termino": termino,
                "depurado": ok, "en_tags": codigo in tags,
                "grupo_contrib": grupo_contribuyente(contrib),
            })

        filas.append({
            "code": t.code, "texto": t.ingredientes_texto,
            "bruto": bruto_eje, "depurado": depurado_eje,
            "descartados": descartados,
            "caramelo": bool({c for c, b, _ in dets if c in caramelo}),
            "tags": tags & validos,
            "grupo_contrib": grupo_contribuyente(contrib),
        })

    r = pd.DataFrame(filas)
    p = pd.DataFrame(pares)
    if p.empty:
        raise SystemExit("Cero detecciones. Revisa el diccionario antes de seguir.")

    # ------------------------------------------------------------ FALSADOR 1
    # La tabla que decide la tesis. Brecha a nivel deteccion, cruzando forma
    # del termino contra clase de origen, sobre el conjunto DEPURADO.
    pd_dep = p[p.depurado]
    f1 = (pd_dep.groupby(["clase", "forma"])
          .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
          .reset_index())
    f1["brecha_pct"] = (100 * f1.sin_tag / f1.n).round(1)
    f1[["ic_bajo", "ic_alto"]] = f1.apply(
        lambda x: pd.Series(wilson(x.sin_tag, x.n)), axis=1)

    # La prediccion dura, aislada: sinteticos declarados SIN codigo E.
    sin_sin_codigo = pd_dep[(pd_dep.clase == "sintetico") & (pd_dep.forma != "codigo_e")]
    sin_con_codigo = pd_dep[(pd_dep.clase == "sintetico") & (pd_dep.forma == "codigo_e")]
    nat_todos = pd_dep[pd_dep.clase == "natural"]

    def tasa(sub):
        n = len(sub)
        s = int((~sub.en_tags).sum())
        return {"n": n, "sin_tag": s,
                "brecha_pct": round(100 * s / n, 1) if n else None,
                "ic95": wilson(s, n) if n else None}

    veredicto_f1 = {
        "sintetico_con_codigo_E": tasa(sin_con_codigo),
        "sintetico_SIN_codigo_E": tasa(sin_sin_codigo),
        "natural_todos": tasa(nat_todos),
        "lectura": ("Si sintetico_SIN_codigo_E se parece mas a natural_todos que a "
                    "sintetico_con_codigo_E, la variable es la FORMA DE DECLARACION y no "
                    "el origen: la tesis se reescribe como mediacion. Si se parece mas a "
                    "sintetico_con_codigo_E, el origen se sostiene como eje directo."),
    }

    # -------------------------------------------------- B. agregados por clase
    def agregado(sub_pares, sub_r, etiqueta_clase, col):
        """Nivel deteccion y nivel producto para una clase."""
        dets = sub_pares
        n_d = len(dets)
        s_d = int((~dets.en_tags).sum())
        codigos = set(dets.codigo)
        con = sub_r[sub_r[col].map(lambda s: bool(s & codigos))]
        n_p = len(con)
        s_p = int(con.apply(lambda f: bool((f[col] & codigos) - f["tags"]), axis=1).sum()) if n_p else 0
        return {
            "clase": etiqueta_clase,
            "deteccion": {"n": n_d, "sin_tag": s_d,
                          "brecha_pct": round(100 * s_d / n_d, 1) if n_d else None,
                          "ic95": wilson(s_d, n_d)},
            "producto": {"n": n_p, "sin_tag": s_p,
                         "brecha_pct": round(100 * s_p / n_p, 1) if n_p else None,
                         "ic95": wilson(s_p, n_p)},
        }

    agregados = {}
    for etiqueta, univ, col in (("depurado", p[p.depurado], "depurado"),
                                ("bruto", p, "bruto")):
        agregados[etiqueta] = [
            agregado(univ[univ.clase == c], r, c, col)
            for c in ("sintetico", "natural", "carmin", "mineral")
        ]

    # ---------------------------------------- por codigo, y la MEDIANA (Tseng)
    por_codigo = []
    for (codigo, dep), g in p.groupby(["codigo", "depurado"]):
        n = len(g)
        s = int((~g.en_tags).sum())
        lo, hi = wilson(s, n)
        por_codigo.append({"codigo": codigo, "universo": "depurado" if dep else "descartado",
                           "clase": g.clase.iloc[0], "n": n, "sin_tag": s,
                           "brecha_pct": round(100 * s / n, 1), "ic_bajo": lo, "ic_alto": hi})
    tabla_codigo = pd.DataFrame(por_codigo).sort_values(["universo", "brecha_pct"],
                                                        ascending=[True, False])

    # Tseng reporta la MEDIANA del porcentaje por aditivo, no el agregado.
    # Comparar nuestro agregado contra su mediana seria un error de estadistico.
    dep_cod = tabla_codigo[(tabla_codigo.universo == "depurado") & (tabla_codigo.n >= 10)]
    mediana = {
        cl: round(float(dep_cod[dep_cod.clase == cl].brecha_pct.median()), 1)
        for cl in ("sintetico", "natural") if len(dep_cod[dep_cod.clase == cl])
    }
    mediana["nota"] = ("Mediana del porcentaje por codigo, con n>=10. ES el estadistico "
                       "que reporta Tseng et al. (2022) = 37.9 %. El agregado ponderado "
                       "NO es comparable con esa cifra.")

    # --------------------------------------- C. estabilidad por contribuyente
    estabilidad = {}
    if col_contrib:
        for grupo, g in p[p.depurado].groupby("grupo_contrib"):
            fila = {}
            for cl in ("sintetico", "natural"):
                sub = g[g.clase == cl]
                fila[cl] = tasa(sub) if len(sub) else None
            fila["n_detecciones"] = len(g)
            estabilidad[grupo] = fila
        estabilidad["lectura"] = ("Si la brecha varia mucho entre grupos, estamos midiendo "
                                  "comportamiento de contribuyente y no del analizador. "
                                  "Va a limitaciones y debilita la generalizacion.")
    else:
        estabilidad = {"ERROR": "no hay columna de contribuyente en el parquet; "
                                "reextraer desde el volcado incluyendo 'creator'"}

    # ------------------------------------------------- D. definiciones de Chiu
    # Chiu et al. (2025) cuentan el caramelo E150 como colorante natural.
    #
    # CORREGIDO 05/09: antes "es sintetico"/"es natural" se decidian por
    # membresia cruda en dic["sinteticos"]/dic["naturales"] -el bloque del
    # YAML-, no por clase_de(). Como E171/E172 (pigmento inorganico) viven
    # fisicamente en el bloque "naturales", un producto cuyo unico colorante
    # fuera E171/E172 se contaba como natural aqui y tambien en el estrato de
    # la muestra de 600 (bloque E, mas abajo, que reusa estas mismas
    # variables). Verificado que hoy no cambia ningun numero -0 productos en
    # todo el corpus tienen E171/E172 como unico colorante-, pero el bug
    # seguia en el codigo. Ver BITACORA_PARCHES.md.
    clase_por_codigo = {}
    for _, codigo, bloque in ordenados:
        clase_por_codigo.setdefault(codigo, clase_de(codigo, bloque))
    n_tot = len(r)
    tiene_sint = r.depurado.map(lambda s: any(clase_por_codigo.get(c) == "sintetico" for c in s))
    tiene_nat_est = r.depurado.map(lambda s: any(clase_por_codigo.get(c) == "natural" for c in s))
    nat_chiu = tiene_nat_est | r.caramelo
    chiu = {
        "n_base": n_tot,
        "nuestra_definicion": {
            "cualquier_colorante_pct": round(100 * (tiene_sint | tiene_nat_est).mean(), 1),
            "sintetico_pct": round(100 * tiene_sint.mean(), 1),
            "natural_pct": round(100 * tiene_nat_est.mean(), 1),
        },
        "definicion_chiu_con_E150": {
            "cualquier_colorante_pct": round(100 * (tiene_sint | nat_chiu).mean(), 1),
            "sintetico_pct": round(100 * tiene_sint.mean(), 1),
            "natural_pct": round(100 * nat_chiu.mean(), 1),
        },
        "referencia_hong_kong": {"cualquiera": 19.8, "natural": 17.2, "sintetico": 3.9},
        "nota": ("Solo la fila definicion_chiu_con_E150 es comparable con Hong Kong. "
                 "La inversion solo puede afirmarse sobre esa fila."),
    }

    # ------------------------------------------- E. muestra del conjunto anotado
    r["_estrato"] = None
    tiene_dep = r.depurado.map(bool)
    r.loc[tiene_dep & tiene_sint, "_estrato"] = "sintetico"
    r.loc[tiene_dep & (tiene_nat_est | r.depurado.map(lambda s: CARMIN in s)), "_estrato"] = "natural"
    r.loc[~tiene_dep & r.descartados.map(bool), "_estrato"] = "ambiguo_descartado"
    r.loc[~tiene_dep & ~r.descartados.map(bool) & ~r.bruto.map(bool), "_estrato"] = "sin_deteccion"

    partes, pesos = [], {}
    for estrato, objetivo in ESTRATOS.items():
        pool = r[r._estrato == estrato]
        n = min(objetivo, len(pool))
        if n < objetivo:
            print(f"  AVISO: estrato '{estrato}' solo tiene {len(pool)} productos, "
                  f"se piden {objetivo}. Se toman {n}.")
        muestra = pool.sample(n, random_state=SEMILLA) if n else pool
        partes.append(muestra.assign(estrato=estrato))
        pesos[estrato] = {"N_poblacion": len(pool), "n_muestra": n,
                          "peso": round(len(pool) / n, 3) if n else None}
    anotacion = pd.concat(partes) if partes else pd.DataFrame()

    # ------------------------------------------------------------------ salidas
    REPORTES.mkdir(exist_ok=True)
    f1.to_csv(REPORTES / "07_falsador1_forma.csv", index=False, encoding="utf-8")
    tabla_codigo.to_csv(REPORTES / "07_brecha_por_codigo.csv", index=False, encoding="utf-8")
    (pd.DataFrame([{"termino": t, "codigo": c, "bloque": b, "forma": forma_de(t)}
                   for t, c, b in ordenados])
       .to_csv(REPORTES / "07_terminos_forma.csv", index=False, encoding="utf-8"))
    if len(anotacion):
        (anotacion[["code", "estrato", "texto"]]
         .assign(anotador_1="", anotador_2="", notas="")
         .to_csv(REPORTES / "07_muestra_anotacion.csv", index=False, encoding="utf-8"))

    resumen = {
        "n_con_texto": n_tot,
        "n_detecciones_brutas": len(p),
        "n_detecciones_depuradas": int(p.depurado.sum()),
        "A_FALSADOR_1": {"veredicto": veredicto_f1, "tabla": f1.to_dict("records")},
        "B_agregados_por_clase": agregados,
        "B_mediana_por_codigo_comparable_con_Tseng": mediana,
        "C_estabilidad_por_contribuyente": estabilidad,
        "D_definiciones_de_Chiu": chiu,
        "E_muestra_anotacion": {"semilla": SEMILLA, "estratos": pesos,
                                "n_total": int(len(anotacion))},
        "ADVERTENCIA": ("La asignacion termino -> forma en 07_terminos_forma.csv es una "
                        "DECISION, no un hecho observado. Revisarla con la Dra. ANTES de "
                        "interpretar el falsador 1: si la asignacion esta mal, el veredicto "
                        "esta mal."),
    }

    print("\n--- FALSADOR 1 ---")
    for k in ("sintetico_con_codigo_E", "sintetico_SIN_codigo_E", "natural_todos"):
        v = veredicto_f1[k]
        print(f"  {k:26} n={v['n']:5}  brecha={v['brecha_pct']} %  IC{v['ic95']}")
    print("\n--- agregados depurados ---")
    for a in agregados["depurado"]:
        d, q = a["deteccion"], a["producto"]
        print(f"  {a['clase']:10} deteccion {d['brecha_pct']} % (n={d['n']})   "
              f"producto {q['brecha_pct']} % (n={q['n']})")
    print(f"\n--- mediana por codigo (comparable con Tseng 37.9 %) ---\n  {mediana}")
    print(f"\n--- Chiu ---\n  nuestra: {chiu['nuestra_definicion']}"
          f"\n  con E150: {chiu['definicion_chiu_con_E150']}")

    guardar_reporte("07_forma_y_clase", resumen)
    print(f"\n-> {REPORTES}/07_*.csv")


if __name__ == "__main__":
    main()
