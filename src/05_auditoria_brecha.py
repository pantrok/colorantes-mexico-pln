"""Paso 5 — Auditoria de la brecha. Corre DESPUES de 02 y antes de creerse el 77.6 %.

La primera corrida dio PCT_BRECHA = 77.6 %, un numero demasiado bueno. Al mirar
su composicion, el codigo mas perdido es E101 (riboflavina, 605 casos, 98.5 % de
brecha) — que en productos mexicanos es casi siempre VITAMINA B2 de fortificacion,
no colorante. Le siguen E170 (carbonato de calcio, mineral/antiaglomerante) y
E100 (curcuma, especia). Cerca del 53 % de las instancias perdidas vienen de
codigos cuyo termino tambien nombra un ingrediente de uso no colorante.

Este script separa dos cifras:
  BRECHA BRUTA      — todos los codigos, comparable con la corrida anterior
  BRECHA DEPURADA   — solo colorantes inequivocos; esta es la que va al resumen

Y mide dos sesgos que afectan al numero:
  - truncamiento: los aditivos van al final de la lista de ingredientes, asi que
    un texto cortado pierde colorantes de forma sistematica
  - contexto: cuantas veces el termino aparece cerca de la palabra 'colorante'

Salidas: reportes/05_auditoria_brecha.json y reportes/05_muestra_ambiguos.csv
"""
from __future__ import annotations
import re
from collections import Counter
import duckdb, pandas as pd
from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, quitar_advertencia_trazas,
                  terminos_ordenados, guardar_reporte)

AMBIGUOS = REQUIEREN_CONTEXTO   # definido en util.py, con su historial

RE_TRUNCADO = re.compile(r"(\.\.\.|…)\s*$|[a-z,]\s*$")
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60   # caracteres a cada lado para buscar la palabra 'colorante'


def detectar_con_termino(texto_norm: str, ordenados):
    """(codigo, bloque, termino) del termino mas largo al mas corto, consumiendo
    el texto. Se necesita el termino real, no solo el codigo: el chequeo de
    contexto de mas abajo tiene que buscar 'colorante' alrededor de la forma
    que de verdad aparecio, no de una forma arbitraria del mismo codigo.

    CORREGIDO 05/09. Antes este script usaba util.py::detectar() -que solo
    devuelve codigo->clase, sin decir que termino coincidio- y luego
    `por_codigo = {c: p for c, _, p in matchers}` para el contexto. Ese dict
    se queda con el PATRON DEL ULTIMO TERMINO PROCESADO por codigo (el mas
    corto, porque matchers esta ordenado de mas largo a mas corto y el dict
    sobreescribe). Para E171 quedaba el patron de "pigmento blanco 6" en vez
    de "dioxido de titanio", que es el que aparece en el 99 % de los casos.
    Afecta a 11 de los 13 codigos que exigen contexto -todos menos E101 y
    E170, que ya no tienen terminos-. La brecha depurada pasaba de citarse en
    67.5 % a la cifra correcta, 69.7 %. Detalle en BITACORA_PARCHES.md."""
    restante, salida = texto_norm, []
    for termino, codigo, bloque in ordenados:
        if not termino:
            continue
        patron = re.compile(r"(?<!\w)" + re.escape(termino) + r"(?!\w)")
        if patron.search(restante):
            salida.append((codigo, bloque, termino))
            restante = patron.sub(" ", restante)
    return salida


def contexto_de_color(texto_norm: str, termino: str) -> bool:
    """True si alguna aparicion del TERMINO que de verdad coincidio tiene
    'colorante' cerca."""
    patron = re.compile(r"(?<!\w)" + re.escape(termino) + r"(?!\w)")
    for m in patron.finditer(texto_norm):
        ini, fin = max(0, m.start() - VENTANA), min(len(texto_norm), m.end() + VENTANA)
        if RE_CONTEXTO.search(texto_norm[ini:fin]):
            return True
    return False


def main() -> None:
    ruta = INTERMEDIO / "productos_mx.parquet"
    df = duckdb.sql(f"""
        SELECT code, nombre_producto, ingredientes_texto, aditivos_tags
        FROM '{ruta}'
        WHERE ingredientes_texto IS NOT NULL
          AND length(trim(ingredientes_texto)) > 0
    """).df()

    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)
    validos = set(dic["sinteticos"]) | set(dic["naturales"])

    filas, textos_rotos = [], []
    for t in df.itertuples(index=False):
        crudo = str(t.ingredientes_texto).strip()
        texto = normalizar(crudo)
        # CORREGIDO parche 14 (05/09/2026). Un colorante mencionado solo
        # dentro de una advertencia de trazas ("puede contener... amarillo 5")
        # no cuenta como deteccion: no es que el producto lo lleve, es la
        # declaracion obligatoria de alergenos. Ver
        # util.py::quitar_advertencia_trazas y BITACORA_PARCHES.md.
        texto_det, roto = quitar_advertencia_trazas(texto)
        if roto:
            textos_rotos.append(t.code)
        dets = [(c, b, term) for c, b, term in detectar_con_termino(texto_det, ordenados)
                if b in ("sinteticos", "naturales")]
        det = {c for c, _, _ in dets}
        tags = {a.replace("en:", "").upper() for a in como_lista(t.aditivos_tags)} & validos
        # Un codigo ambiguo solo cuenta si el contexto avala el TERMINO que de
        # verdad coincidio para ese codigo (puede haber mas de uno; basta que
        # alguno tenga "colorante" cerca).
        depurado = {c for c, _, term in dets
                    if c not in AMBIGUOS or contexto_de_color(texto_det, term)}
        filas.append({
            "code": t.code, "texto": crudo,
            "bruto": set(det), "depurado": depurado, "tags": tags,
            "truncado": bool(RE_TRUNCADO.search(crudo)) and len(crudo) > 30,
            "ambiguos_sin_contexto": {c for c in det if c in AMBIGUOS} - depurado,
        })
    r = pd.DataFrame(filas)

    def brecha(col):
        con = r[r[col].map(bool)]
        falta = con.apply(lambda f: bool(f[col] - f["tags"]), axis=1)
        return len(con), int(falta.sum()), (round(100 * falta.sum() / len(con), 1) if len(con) else None)

    n_b, g_b, p_b = brecha("bruto")
    n_d, g_d, p_d = brecha("depurado")

    # Sesgo por truncamiento: si el texto cortado detecta menos colorantes, la
    # cifra real esta subestimada y hay que decirlo en limitaciones.
    tasa_tr = round(100 * r[r.truncado].depurado.map(bool).mean(), 1)
    tasa_co = round(100 * r[~r.truncado].depurado.map(bool).mean(), 1)

    resumen = {
        "n_con_texto": len(r),
        "BRECHA_BRUTA": {"n_con_colorante": n_b, "n_con_brecha": g_b, "pct": p_b},
        "BRECHA_DEPURADA": {"n_con_colorante": n_d, "n_con_brecha": g_d, "pct": p_d,
                            "criterio": f"excluye {sorted(AMBIGUOS)} salvo que "
                                        f"'colorante' aparezca a menos de {VENTANA} caracteres"},
        "n_descartados_por_ambiguedad": int(r.ambiguos_sin_contexto.map(bool).sum()),
        "descartados_por_codigo": Counter(
            c for s in r.ambiguos_sin_contexto for c in s).most_common(),
        "sesgo_truncamiento": {
            "pct_textos_truncados": round(100 * r.truncado.mean(), 1),
            "deteccion_en_truncados_pct": tasa_tr,
            "deteccion_en_completos_pct": tasa_co,
            "diferencia_pp": round(tasa_co - tasa_tr, 1),
            "lectura": ("Si la diferencia es positiva y grande, el truncamiento hace "
                        "perder colorantes y la prevalencia real es mayor. Va en limitaciones."),
        },
        "para_el_resumen": ("Reportar la cifra DEPURADA. La bruta se menciona en metodos "
                            "para mostrar cuanto pesa la ambiguedad de uso, que es "
                            "justamente el argumento a favor del reconocimiento de "
                            "entidades frente al emparejamiento por diccionario."),
        "textos_rotos_advertencia": {
            "n": len(textos_rotos), "codigos": textos_rotos,
            "lectura": ("Productos donde el marcador de advertencia de trazas aparece "
                        "antes del 30 % del texto -normalmente OCR revuelto-. No se "
                        "recortaron; revisar a mano."),
        },
    }
    print(f"  brecha bruta:    {p_b} %  ({g_b}/{n_b})")
    print(f"  brecha depurada: {p_d} %  ({g_d}/{n_d})")
    print(f"  descartados por ambiguedad: {resumen['n_descartados_por_ambiguedad']}")
    print(f"  deteccion truncados {tasa_tr} % vs completos {tasa_co} %")
    guardar_reporte("05_auditoria_brecha", resumen)

    # Muestra de descartados: hay que leerla para saber si el criterio de contexto
    # esta descartando de mas o de menos.
    REPORTES.mkdir(exist_ok=True)
    amb = r[r.ambiguos_sin_contexto.map(bool)].head(300).copy()
    amb["descartados"] = amb.ambiguos_sin_contexto.map(lambda s: ",".join(sorted(s)))
    amb[["code", "descartados", "texto"]].to_csv(
        REPORTES / "05_muestra_ambiguos.csv", index=False, encoding="utf-8")
    print(f"-> {REPORTES / '05_muestra_ambiguos.csv'}")


if __name__ == "__main__":
    main()
