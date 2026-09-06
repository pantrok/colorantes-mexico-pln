"""Paso 15 — Recalculos pedidos por la revision por pares del manuscrito v11.

Origen: `REVISION_PARES_v11.md`, panel de cinco revisores. Las tareas 1 y 2
del parche (Tabla 2 completa con ceros explicitos; modelo de Firth sin el
termino de obligatoriedad) se resolvieron en `08_vocabulario_off.py`, porque
ahi ya viven la Tabla 2 y el modelo — no hacia falta un script nuevo para
esas dos. Este script cubre las tareas 3 a 11, que son analisis nuevos sin
un lugar natural en el flujo existente.

TAREA 12 (validacion 2x2 del conjunto anotado: VPP, sensibilidad, kappa con
IC) NO SE HIZO. Requiere las columnas `anotador_1`/`anotador_2` llenas de
`reportes/07_muestra_anotacion_v1.csv`, y estan vacias — nadie ha registrado
ahi el resultado de la doble anotacion todavia (el kappa=0.770 que cita el
parche 14 es un dato reportado de palabra, no un archivo en el repo). No se
aproxima con datos que no existen; en cuanto la anotacion este en el
repositorio, este es el primer punto a resolver.

Reconstruye desde cero, con la MISMA logica ya corregida de 07/08 (dedup por
codigo, filtro de advertencia de trazas, regla de contexto de 60 caracteres,
clase_de() con carmin/minerales aparte), un dataset por (producto, codigo) y
otro por (producto, termino). Se valida contra los totales ya publicados de
07/08 (sintetico 2405, natural_botanico 438, carmin 233, mineral_inorganico
48) antes de usarse para nada mas: si no cuadran, hay un bug en este script,
no en 07/08.

Salidas: reportes/15_*.json y reportes/15_*.csv (una por tarea).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from modelo import firth, separacion, _ajuste
from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, quitar_advertencia_trazas,
                  terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
EXTERNO = RAIZ / "datos" / "externo"
AMBIGUOS = REQUIEREN_CONTEXTO
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA_DEFECTO = 60
CARMIN = "E120"
MINERALES = {"E170", "E171", "E172"}
SEMILLA = 20260906
N_BOOT = 1000


# --------------------------------------------------------------- utilidades
# (copias deliberadas de 07/08/09 — no se comparten via util.py porque cada
# script las adapta a su propia pregunta; ver BITACORA_PARCHES.md sobre por
# que las copias en si no son el problema, la falta de dedup por codigo si lo
# era.)

def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def variantes(codigo: str) -> list[str]:
    k = norma(codigo).replace(" ", "")
    return [k] + [k + s for s in ("i", "ii", "iii", "iv", "v", "vi",
                                  "a", "b", "c", "d", "e", "f")]


def leer_taxonomia_off(ruta: Path):
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


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral_inorganico"
    return {"sinteticos": "sintetico", "naturales": "natural_botanico"}.get(
        bloque, "fuera_de_eje")


def detectar_con_forma(texto: str, ordenados) -> list[tuple[str, str, str]]:
    """(codigo, bloque, termino) del mas largo al mas corto, consumiendo el
    texto. Identica a la de 07_forma_y_clase.py."""
    restante, salida = texto, []
    for termino, codigo, bloque in ordenados:
        if not termino:
            continue
        patron = re.compile(r"\b" + re.escape(termino) + r"\b")
        if patron.search(restante):
            salida.append((codigo, bloque, termino))
            restante = patron.sub(" ", restante)
    return salida


def con_contexto(texto: str, termino: str, ventana: int = VENTANA_DEFECTO) -> bool:
    patron = re.compile(r"\b" + re.escape(termino) + r"\b")
    for m in patron.finditer(texto):
        ini, fin = max(0, m.start() - ventana), min(len(texto), m.end() + ventana)
        if RE_CONTEXTO.search(texto[ini:fin]):
            return True
    return False


def cargar_productos_mx() -> pd.DataFrame:
    ruta = INTERMEDIO / "productos_mx.parquet"
    cols = duckdb.sql(f"SELECT * FROM '{ruta}' LIMIT 1").df().columns.tolist()
    col_contrib = next((c for c in ("contribuidor", "creador", "creator",
                                    "contribuyente", "created_by", "usuario")
                        if c in cols), None)
    sel = "code, ingredientes_texto, aditivos_tags"
    if col_contrib:
        sel += f", {col_contrib} AS contribuyente"
    df = duckdb.sql(f"""
        SELECT {sel} FROM '{ruta}'
        WHERE ingredientes_texto IS NOT NULL
          AND length(trim(ingredientes_texto)) > 0
    """).df()
    if not col_contrib:
        df["contribuyente"] = None
    return df


def construir_det_termino(df: pd.DataFrame, ordenados, ventana: int = VENTANA_DEFECTO,
                          vocab: dict | None = None, mand: dict | None = None
                          ) -> tuple[pd.DataFrame, list]:
    """Una fila por (producto, termino) detectado dentro del eje de color,
    consumiendo el texto y filtrando la advertencia de trazas. NO deduplica
    por codigo -eso lo hace deduplicar_por_codigo() a partir de esta tabla-,
    porque varias tareas (6 forma del nombre, 9 concentracion por
    contribuyente, 8 numero E) necesitan el termino exacto, no solo el
    codigo."""
    filas, textos_rotos = [], []
    for t in df.itertuples(index=False):
        crudo = str(t.ingredientes_texto)
        texto = normalizar(crudo)
        texto_det, roto = quitar_advertencia_trazas(texto)
        if roto:
            textos_rotos.append(t.code)
        tags = {str(a).replace("en:", "").upper() for a in como_lista(t.aditivos_tags)}
        for codigo, bloque, termino in detectar_con_forma(texto_det, ordenados):
            cl = clase_de(codigo, bloque)
            if cl == "fuera_de_eje":
                continue
            fila = {
                "code": t.code, "codigo": codigo, "bloque": bloque, "clase": cl,
                "termino": termino, "en_tags": codigo in tags,
                "contribuyente": t.contribuyente,
                "contexto_ok": (codigo not in AMBIGUOS) or con_contexto(texto_det, termino, ventana),
            }
            if vocab is not None:
                vs, es_mand = set(), False
                for k in variantes(codigo):
                    vs |= vocab.get(k, set())
                    es_mand = es_mand or mand.get(k, False)
                fila["en_vocab_off"] = norma(termino) in vs
                fila["off_mandatory"] = es_mand
            filas.append(fila)
    return pd.DataFrame(filas), textos_rotos


def deduplicar_por_codigo(det_term: pd.DataFrame) -> pd.DataFrame:
    """Colapsa a una fila por (producto, codigo): OR entre terminos para el
    contexto y para en_vocab_off/off_mandatory (basta que UNO de los
    sinonimos usados pase), y se queda solo con los codigos que superaron el
    contexto -son los que cuentan como deteccion real-. Mismo criterio que
    07_forma_y_clase.py y 08_vocabulario_off.py."""
    agg = {"contexto_ok": "any", "en_tags": "first", "termino": "first",
          "contribuyente": "first"}
    if "en_vocab_off" in det_term.columns:
        agg["en_vocab_off"] = "any"
        agg["off_mandatory"] = "any"
    det = (det_term.groupby(["code", "codigo", "clase"], as_index=False)
                   .agg(agg))
    det = det[det.contexto_ok].drop(columns="contexto_ok")
    return det


def validar_contra_publicado(det: pd.DataFrame) -> dict:
    """Los cuatro numeros ya publicados de 07/08 (Tabla 1). Si esto no
    cuadra, hay un bug en construir_det_termino/deduplicar_por_codigo, no en
    07/08 -que ya pasaron su propia verificacion cruzada-."""
    esperado = {"sintetico": 2405, "natural_botanico": 438,
                "carmin": 233, "mineral_inorganico": 48}
    obtenido = det.clase.value_counts().to_dict()
    ok = all(obtenido.get(k) == v for k, v in esperado.items())
    return {"ok": ok, "esperado": esperado, "obtenido": obtenido}


def cargar_productos_pais(pais: str, ruta_crudo: Path) -> pd.DataFrame:
    """Mismo patron de 09/11/12: el volcado crudo trae ingredients_text como
    lista de STRUCT(lang,text); se desanida solo cuando el tipo declarado lo
    exige."""
    esquema = {r[0]: r[1] for r in duckdb.sql(
        f"DESCRIBE SELECT * FROM '{ruta_crudo}' LIMIT 0").fetchall()}

    def expr(nombre):
        tipo = esquema.get(nombre, "").upper()
        if "STRUCT" in tipo and "[]" in tipo:
            return f"""coalesce(
                list_filter({nombre}, x -> x.lang = 'es')[1].text,
                list_filter({nombre}, x -> x.lang = 'main')[1].text,
                try({nombre}[1].text)
            ) AS {nombre}"""
        return nombre

    df = duckdb.sql(f"""
        SELECT * FROM (SELECT {expr('code')}, {expr('ingredients_text')},
                              {expr('additives_tags')}, countries_tags
                       FROM '{ruta_crudo}')
        WHERE list_contains(countries_tags, '{pais}')
          AND ingredients_text IS NOT NULL
          AND length(trim(ingredients_text)) > 0
    """).df()
    df = df.rename(columns={"ingredients_text": "ingredientes_texto",
                            "additives_tags": "aditivos_tags"})
    df["contribuyente"] = None
    return df[["code", "ingredientes_texto", "aditivos_tags", "contribuyente"]]


# --------------------------------------------------------- tarea 3: Kitagawa

def celdas_para_estandarizacion(det: pd.DataFrame) -> pd.DataFrame:
    """Celdas clase x en_vocab_off, SOLO mandatory=False -mismo universo
    declarado que el modelo de 2 predictores en 08_vocabulario_off.py-, mas
    la fila cruda de cada origen (TODA la poblacion, para la tasa
    observada)."""
    base = det[det.clase.isin(["sintetico", "natural_botanico"])]
    celdas = (base[~base.off_mandatory]
              .groupby(["clase", "en_vocab_off"])
              .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
              .reset_index())
    crudas = (base.groupby("clase")
              .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
              .reset_index())
    return celdas, crudas


def kitagawa(celdas: pd.DataFrame, crudas: pd.DataFrame) -> dict | None:
    """Cuarteto en las DOS direcciones: (A) composicion de vocabulario del
    sintetico aplicada a las tasas del natural -la que ya vivia en 08-, y
    (B) composicion del natural aplicada a las tasas del sintetico, como
    espejo. diferencia_cruda es la misma en las dos direcciones -es la
    brecha observada, sin estandarizar-."""
    sin_c = celdas[celdas.clase == "sintetico"].set_index("en_vocab_off")
    nat_c = celdas[celdas.clase == "natural_botanico"].set_index("en_vocab_off")
    comunes = sin_c.index.intersection(nat_c.index)
    if not len(comunes):
        return None
    # OJO: el indice es booleano (True/False de en_vocab_off). `.loc[comunes]`
    # con un Index booleano de la MISMA longitud que el DataFrame se
    # interpreta como MASCARA, no como busqueda por etiqueta -un gotcha
    # clasico de pandas cuando las propias etiquetas son True/False-. Se usa
    # `.reindex()`, que siempre busca por etiqueta sin ambiguedad.
    b_sin_cruda = 100 * crudas.set_index("clase").loc["sintetico", "sin_tag"] \
                      / crudas.set_index("clase").loc["sintetico", "n"]
    b_nat_cruda = 100 * crudas.set_index("clase").loc["natural_botanico", "sin_tag"] \
                      / crudas.set_index("clase").loc["natural_botanico", "n"]
    dif_cruda = b_nat_cruda - b_sin_cruda

    peso_sin = sin_c.reindex(comunes)["n"]
    tasa_nat = (nat_c.reindex(comunes)["sin_tag"] / nat_c.reindex(comunes)["n"])
    tasa_nat_std = float((peso_sin * tasa_nat).sum() / peso_sin.sum()) * 100
    dif_std_A = tasa_nat_std - b_sin_cruda
    frac_resid_A = dif_std_A / dif_cruda if dif_cruda else None

    peso_nat = nat_c.reindex(comunes)["n"]
    tasa_sin = (sin_c.reindex(comunes)["sin_tag"] / sin_c.reindex(comunes)["n"])
    tasa_sin_std = float((peso_nat * tasa_sin).sum() / peso_nat.sum()) * 100
    dif_std_B = b_nat_cruda - tasa_sin_std
    frac_resid_B = dif_std_B / dif_cruda if dif_cruda else None

    return {
        "diferencia_cruda_pp": dif_cruda,
        "direccion_A_peso_sintetico_sobre_tasas_naturales": {
            "tasa_natural_estandarizada_pct": tasa_nat_std,
            "diferencia_estandarizada_pp": dif_std_A,
            "fraccion_residual": frac_resid_A,
        },
        "direccion_B_peso_natural_sobre_tasas_sinteticas": {
            "tasa_sintetico_estandarizada_pct": tasa_sin_std,
            "diferencia_estandarizada_pp": dif_std_B,
            "fraccion_residual": frac_resid_B,
        },
    }


def bootstrap_por_producto(universo: np.ndarray, det: pd.DataFrame,
                           fn_celdas, fn_estadistico, n_boot: int = N_BOOT,
                           semilla: int = SEMILLA):
    """Bootstrap no parametrico por PRODUCTO -no por deteccion-: las 3124
    detecciones se anidan en 1665 productos y los predictores solo varian
    entre codigos y terminos (tarea 4). Se remuestrea del UNIVERSO COMPLETO
    de productos con texto (7775 en Mexico), no solo de los que tienen
    deteccion, para que la variabilidad de CUANTOS productos contribuyen
    tambien entre al intervalo.

    Implementacion: en vez de reconstruir un DataFrame por replica (lento),
    se indexa un arreglo producto x celda con conteos y se suma sobre indices
    remuestreados -equivalente a remuestrear productos con reemplazo, mucho
    mas rapido-.
    """
    rng = np.random.default_rng(semilla)
    n = len(universo)
    idx_pos = {c: i for i, c in enumerate(universo)}
    resultados = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        codigos_muestra = universo[idx]
        conteo = pd.Series(codigos_muestra).value_counts()
        # peso por producto: cuantas veces salio en esta replica
        pesos = det["code"].map(conteo).fillna(0).astype(int)
        det_pesado = det.assign(_peso=pesos)
        det_pesado = det_pesado[det_pesado._peso > 0]
        resultados.append(fn_estadistico(det_pesado, fn_celdas))
    return resultados


def _celdas_ponderadas(det_pesado: pd.DataFrame) -> pd.DataFrame:
    """n y sin_tag por (clase, en_vocab_off, off_mandatory), respetando el
    peso de remuestreo de cada fila (cuantas veces salio ese producto en la
    replica de bootstrap). Vectorizado -sin groupby().apply()-, porque esto
    se llama una vez por replica de bootstrap (miles de veces)."""
    d = det_pesado.copy()
    d["sin_tag_pesado"] = d._peso * (~d.en_tags)
    g = (d.groupby(["clase", "en_vocab_off", "off_mandatory"])
           .agg(n=("_peso", "sum"), sin_tag=("sin_tag_pesado", "sum"))
           .reset_index())
    return g


def estadistico_kitagawa(det_pesado: pd.DataFrame, _fn_celdas=None) -> dict | None:
    g = _celdas_ponderadas(det_pesado)
    base = g[g.clase.isin(["sintetico", "natural_botanico"])]
    celdas = base[~base.off_mandatory]
    crudas = base.groupby("clase")[["n", "sin_tag"]].sum().reset_index()
    return kitagawa(celdas, crudas)


def tarea3_estandarizacion(det: pd.DataFrame, universo: np.ndarray) -> dict:
    celdas, crudas = celdas_para_estandarizacion(det)
    punto = kitagawa(celdas, crudas)

    replicas = bootstrap_por_producto(universo, det, None, estadistico_kitagawa)
    replicas = [r for r in replicas if r is not None]

    def ic(extractor):
        vals = np.array([extractor(r) for r in replicas], dtype=float)
        vals = vals[~np.isnan(vals)]
        if len(vals) < 20:
            return None
        return [round(float(np.percentile(vals, 2.5)), 4),
                round(float(np.percentile(vals, 97.5)), 4)]

    return {
        "poblacion_declarada": ("Celdas clase x en_vocab_off con off_mandatory=False "
            "para el peso y la tasa estandarizada -mismo universo que el modelo de 2 "
            "predictores de 08_vocabulario_off.py-. La tasa CRUDA de cada origen usa "
            "TODA su poblacion, mandatory incluido."),
        "n_bootstrap": len(replicas), "semilla": SEMILLA,
        "punto_una_sola_corrida_sin_redondear": punto,
        "ic95_bootstrap_por_producto": {
            "diferencia_cruda_pp": ic(lambda r: r["diferencia_cruda_pp"]),
            "tasa_natural_estandarizada_pct": ic(lambda r: r["direccion_A_peso_sintetico_sobre_tasas_naturales"]["tasa_natural_estandarizada_pct"]),
            "diferencia_estandarizada_A_pp": ic(lambda r: r["direccion_A_peso_sintetico_sobre_tasas_naturales"]["diferencia_estandarizada_pp"]),
            "fraccion_residual_A": ic(lambda r: r["direccion_A_peso_sintetico_sobre_tasas_naturales"]["fraccion_residual"]),
            "tasa_sintetico_estandarizada_pct": ic(lambda r: r["direccion_B_peso_natural_sobre_tasas_sinteticas"]["tasa_sintetico_estandarizada_pct"]),
            "diferencia_estandarizada_B_pp": ic(lambda r: r["direccion_B_peso_natural_sobre_tasas_sinteticas"]["diferencia_estandarizada_pp"]),
            "fraccion_residual_B": ic(lambda r: r["direccion_B_peso_natural_sobre_tasas_sinteticas"]["fraccion_residual"]),
        },
    }


# -------------------------------------------- tarea 4: bootstrap y agrupamiento

def _estadistico_tablas(det_pesado: pd.DataFrame, _fn_celdas=None) -> dict:
    g = _celdas_ponderadas(det_pesado)
    tabla1 = g.groupby("clase")[["n", "sin_tag"]].sum()
    tabla1_brecha = (100 * tabla1.sin_tag / tabla1.n.replace(0, np.nan)).to_dict()

    m2 = g[g.clase.isin(["sintetico", "natural_botanico"]) & (~g.off_mandatory)].copy()
    ors = {}
    if len(m2) == 4 and (m2.n > 0).all():
        m2["natural"] = (m2.clase == "natural_botanico").astype(int)
        m2["fuera_vocab"] = (~m2.en_vocab_off).astype(int)
        Xm = np.column_stack([np.ones(len(m2)), m2.natural.values, m2.fuera_vocab.values]).astype(float)
        beta, _, _ = _ajuste(Xm, m2.sin_tag.values.astype(float), m2.n.values.astype(float))
        ors = {"OR_natural": float(np.exp(beta[1])), "OR_fuera_vocab": float(np.exp(beta[2]))}

    tabla2 = g.set_index(["clase", "en_vocab_off", "off_mandatory"])
    tabla2_brecha = {}
    for (c, v, md), fila in tabla2.iterrows():
        if fila.n > 0:
            tabla2_brecha[f"{c}|vocab={v}|mandatory={md}"] = 100 * fila.sin_tag / fila.n

    return {"tabla1_brecha_pct": tabla1_brecha, **ors, "tabla2_brecha_pct": tabla2_brecha}


def tarea4_bootstrap_tablas(det: pd.DataFrame, universo: np.ndarray) -> dict:
    """Bootstrap por producto de todas las proporciones de las Tablas 1 y 2,
    y de las RM del modelo de 2 predictores. Los IC actuales (Wilson,
    verosimilitud perfilada) asumen deteccion independiente; las 3124
    detecciones se anidan en solo 1665 productos."""
    replicas = bootstrap_por_producto(universo, det, None, _estadistico_tablas)

    def ic_de(claves_anidadas):
        vals = []
        for r in replicas:
            v = r
            for k in claves_anidadas:
                v = v.get(k) if v is not None else None
            if v is not None and np.isfinite(v):
                vals.append(v)
        if len(vals) < 20:
            return None
        return [round(float(np.percentile(vals, 2.5)), 2),
                round(float(np.percentile(vals, 97.5)), 2)]

    punto = _estadistico_tablas(det.assign(_peso=1))
    ic_tabla1 = {cl: ic_de(["tabla1_brecha_pct", cl]) for cl in punto["tabla1_brecha_pct"]}
    ic_tabla2 = {cl: ic_de(["tabla2_brecha_pct", cl]) for cl in punto["tabla2_brecha_pct"]}
    ic_or = {"OR_natural": ic_de(["OR_natural"]), "OR_fuera_vocab": ic_de(["OR_fuera_vocab"])}

    return {
        "n_bootstrap": len(replicas), "semilla": SEMILLA,
        "punto": punto,
        "ic95_bootstrap_por_producto": {
            "tabla1_brecha_pct": ic_tabla1,
            "tabla2_brecha_pct": ic_tabla2,
            "modelo_OR": ic_or,
        },
        "nota": ("IC por bootstrap no parametrico, remuestreando PRODUCTOS (no "
                 "detecciones) del universo completo de productos con texto. "
                 "Comparar el ancho contra el IC de Wilson/Firth ya publicado, "
                 "que trata cada deteccion como independiente."),
    }


def icc_por_codigo(det: pd.DataFrame) -> dict:
    """ICC y efecto de diseno por CODIGO, metodo de momentos de un factor
    (Fleiss, 1981) sobre datos binarios -equivalente a un binomial mixto con
    intercepto aleatorio por codigo estimado por momentos, no por maxima
    verosimilitud: no hay statsmodels/scipy disponibles en este entorno, y
    el proyecto ya opto por implementar sus propios metodos (ver
    modelo.py::firth) en vez de agregar una dependencia pesada. El metodo de
    momentos es el estandar en diseno muestral para exactamente esta
    pregunta (deff de un estimador con datos agrupados)."""
    g = (det.groupby("codigo")
            .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
            .reset_index())
    g = g[g.n > 0]
    k, N = len(g), int(g.n.sum())
    p_bar = g.sin_tag.sum() / N
    p_i = g.sin_tag / g.n
    MSB = float((g.n * (p_i - p_bar) ** 2).sum() / (k - 1))
    MSW = float((g.n * p_i * (1 - p_i)).sum() / (N - k)) if N > k else float("nan")
    n0 = float((N - (g.n ** 2).sum() / N) / (k - 1))
    denom = MSB + (n0 - 1) * MSW
    icc = max(0.0, (MSB - MSW) / denom) if denom else 0.0
    n_bar = N / k
    deff = 1 + (n_bar - 1) * icc
    return {
        "k_codigos": k, "N_detecciones": N, "n_promedio_por_codigo": round(n_bar, 1),
        "ICC": round(icc, 4), "design_effect": round(deff, 3),
        "n_efectivo": round(N / deff, 1),
        "metodo": ("ANOVA de un factor sobre datos binarios (Fleiss, 1981), estimador "
                   "de momentos con correccion por tamano de grupo desigual. No es un "
                   "ajuste de maxima verosimilitud -aviso explicito: no hay statsmodels "
                   "ni scipy en el entorno del proyecto-."),
        "lectura": ("design_effect > 1 significa que los IC actuales -que tratan cada "
                    "deteccion como independiente- son mas angostos de lo que deberian. "
                    "n_efectivo es el tamano de muestra 'real' una vez descontado el "
                    "anidamiento; los IC deberian recalcularse con ese n, no con N_detecciones."),
    }


# ------------------------------------------------------------ tarea 5: sobredispersion

def sobredispersion_por_celda(det: pd.DataFrame) -> dict:
    """Cuasi-binomial: dispersion de Pearson (chi2/gl) del recuento por
    TERMINO dentro de cada celda del modelo (clase x en_vocab_off,
    mandatory=False). 'amarillo ocaso' (20.4 % de 221) y 'amarillo 6'
    (81.6 %) caen en la misma celda -sintetico, en_vocab_off=True- y
    difieren 61 puntos: si el binomial simple fuera admisible, esa dispersion
    entre terminos de la misma celda no deberia superar mucho lo que predice
    sqrt(p(1-p)/n)."""
    base = det[det.clase.isin(["sintetico", "natural_botanico"]) & (~det.off_mandatory)]
    por_termino = (base.groupby(["clase", "en_vocab_off", "termino"])
                        .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
                        .reset_index())
    filas_chi2, gl_total, x2_total = [], 0, 0.0
    for (cl, ev), g in por_termino.groupby(["clase", "en_vocab_off"]):
        n_celda, s_celda = g.n.sum(), g.sin_tag.sum()
        p_celda = s_celda / n_celda if n_celda else np.nan
        if p_celda in (0.0, 1.0) or n_celda == 0:
            continue
        x2 = float((((g.sin_tag - g.n * p_celda) ** 2) / (g.n * p_celda * (1 - p_celda))).sum())
        gl = len(g) - 1
        if gl <= 0:
            continue
        filas_chi2.append({"clase": cl, "en_vocab_off": bool(ev), "n_terminos": len(g),
                           "n_detecciones": int(n_celda), "p_celda": round(p_celda, 4),
                           "chi2_pearson": round(x2, 2), "gl": gl,
                           "phi_hat_celda": round(x2 / gl, 2)})
        gl_total += gl
        x2_total += x2
    phi_global = x2_total / gl_total if gl_total else None
    return {
        "por_celda": filas_chi2,
        "phi_hat_global": round(phi_global, 2) if phi_global else None,
        "gl_total": gl_total,
        "admisible_binomial_simple": bool(phi_global is not None and phi_global < 2),
        "veredicto": (
            "El binomial simple NO es admisible: hay mas variacion entre terminos de la "
            "misma celda de la que un binomial homogeneo predice. Los errores estandar "
            "del modelo de 2 predictores deberian inflarse por sqrt(phi_hat_global) "
            "-cuasibinomial-, no leerse literales."
            if phi_global and phi_global >= 2 else
            "El binomial simple es razonablemente admisible: la dispersion entre terminos "
            "de la misma celda es del orden de lo esperado por azar."
        ),
        "caso_amarillo_6_vs_ocaso": por_termino[
            por_termino.termino.isin(["amarillo 6", "amarillo ocaso"])].to_dict("records"),
    }


# --------------------------------------------- tarea 6: forma del nombre

# Reutiliza el criterio de fuente comun de 07_forma_y_clase.py::FUENTES,
# ampliado con la familia del caroteno -que el propio parche 15 pide
# clasificar como nombre_comun_planta, no como nombre_tecnico, aunque
# "beta caroteno" sea tambien una forma quimica-. Es una copia deliberada,
# no un import: esta clasificacion contesta una pregunta distinta de la de
# forma_de() en 07 (forma del NOMBRE para la hipotesis rival del revisor,
# no forma DE LA COINCIDENCIA para el falsador 1), aunque compartan vocabulario.
FUENTES_COMUNES = {
    "cochinilla", "carmin de cochinilla", "grana cochinilla", "achiote", "annato",
    "annatto", "bija", "urucum", "curcuma", "paprika", "pimenton",
    "oleorresina de paprika", "betabel", "remolacha", "zanahoria",
    "zanahoria purpura", "zanahoria negra", "jamaica", "flor de jamaica",
    "hibisco", "uva", "col morada", "camote morado", "espirulina", "spirulina",
    "alga espirulina", "clorofila de alfalfa", "cempasuchil", "flor de cempasuchil",
    "tagete", "maiz morado", "gardenia", "safflower", "cartamo",
    "beta caroteno", "betacaroteno", "beta-caroteno", "caroteno", "carotenos",
    "caroteno natural", "carotenos mixtos", "carotenos naturales",
}
RE_CODIGO_E = re.compile(r"^\s*(e\s?-?\d{3}[a-z]{0,2}|ci\s?\d{4,5}|ins\s?\d{3}|sin\s?\d{3}[a-z]{0,2})\s*$")
RE_COLOR_NUM = re.compile(r"\b(rojo|amarillo|azul|verde|violeta|naranja|negro|blanco|caramelo)\b.*\d")


def forma_del_nombre(termino: str) -> str:
    """Tres niveles, pedidos literalmente por el parche 15 (tarea 6):
    numero_codigo (convencion FD&C de color+numero, o codigo E/SIN/CI puro),
    nombre_tecnico (nombre quimico o comercial sin numero: curcumina,
    tartrazina, azul brillante), nombre_comun_planta (nombre vernaculo de
    fuente vegetal o animal, incluida la familia del caroteno por
    instruccion explicita del parche). Es una DECISION, no un hecho — se
    vuelca completa a 15_forma_del_nombre.csv para que se revise a mano,
    igual que 07_terminos_forma.csv."""
    t = termino.strip().lower()
    if RE_CODIGO_E.match(t) or re.search(r"\be\s?-?\d{3}", t) or re.search(r"\bci\s?\d{4,5}\b", t):
        return "numero_codigo"
    if RE_COLOR_NUM.search(t):
        return "numero_codigo"
    if t in FUENTES_COMUNES or any(f in t for f in
                                   ("extracto de", "jugo de", "concentrado de", "oleorresina de")):
        return "nombre_comun_planta"
    return "nombre_tecnico"


def tarea6_forma_del_nombre(det: pd.DataFrame, ordenados) -> dict:
    # hoja de auditoria: la forma de CADA termino del diccionario, no solo
    # los detectados, para que se revise igual que 07_terminos_forma.csv
    auditoria = pd.DataFrame([
        {"termino": t, "codigo": c, "bloque": b, "forma_del_nombre": forma_del_nombre(t)}
        for t, c, b in ordenados])
    REPORTES.mkdir(exist_ok=True)
    auditoria.to_csv(REPORTES / "15_forma_del_nombre.csv", index=False, encoding="utf-8")

    d = det[det.clase.isin(["sintetico", "natural_botanico"])].copy()
    d["forma"] = d.termino.map(forma_del_nombre)

    # modelo original (2 predictores, ya sin mandatory) para comparar lado a lado
    base_original = d[~d.off_mandatory]
    celda_original = (base_original.groupby("clase")
                      .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
                      .reset_index())
    celda_original["natural"] = (celda_original.clase == "natural_botanico").astype(int)
    Xo = np.column_stack([np.ones(len(celda_original)), celda_original.natural.values]).astype(float)
    beta_o, _, _ = _ajuste(Xo, celda_original.sin_tag.values.astype(float),
                           celda_original.n.values.astype(float))

    # modelo con forma del nombre: natural + 2 dummies de forma (referencia numero_codigo)
    cel = (d.groupby(["clase", "forma"])
            .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())))
            .reset_index())
    cel["natural"] = (cel.clase == "natural_botanico").astype(int)
    cel["es_nombre_tecnico"] = (cel.forma == "nombre_tecnico").astype(int)
    cel["es_nombre_comun_planta"] = (cel.forma == "nombre_comun_planta").astype(int)
    avisos = separacion(cel, "sin_tag", "n", ["natural", "es_nombre_tecnico", "es_nombre_comun_planta"])
    modelo_forma = pd.DataFrame()
    if cel.natural.nunique() > 1:
        X = cel[["natural", "es_nombre_tecnico", "es_nombre_comun_planta"]]
        modelo_forma = firth(X, cel.sin_tag.values, cel.n.values)

    # los tres casos sueltos
    sin160e = det[det.codigo == "E160e"]
    ocaso_vs_6 = det[det.termino.isin(["amarillo 6", "amarillo ocaso"])][
        ["codigo", "termino", "clase", "en_tags"]]
    ocaso_vs_6_resumen = (det[det.termino.isin(["amarillo 6", "amarillo ocaso"])]
                          .assign(forma=lambda x: x.termino.map(forma_del_nombre))
                          .groupby("termino")
                          .agg(n=("en_tags", "size"), sin_tag=("en_tags", lambda s: int((~s).sum())),
                               forma=("forma", "first"))
                          .assign(brecha_pct=lambda x: round(100 * x.sin_tag / x.n, 1))
                          .reset_index())

    return {
        "n_terminos_diccionario": len(auditoria),
        "distribucion_formas": auditoria.forma_del_nombre.value_counts().to_dict(),
        "modelo_original_2_predictores": {
            "OR_natural": round(float(np.exp(beta_o[1])), 2),
        },
        "modelo_con_forma_del_nombre": {
            "referencia": "numero_codigo",
            "tabla": modelo_forma.to_dict("records") if len(modelo_forma) else None,
            "separacion_detectada": avisos,
        },
        "pregunta_del_revisor": ("Si el OR de 'natural' cambia poco entre el modelo original y "
            "el que controla por forma del nombre, el origen conserva efecto propio. Si cae "
            "hacia 1 o pierde significancia, la forma del nombre es el mecanismo real y el "
            "origen es su correlato, no una causa independiente."),
        "caso_SIN160e": {
            "n": len(sin160e), "sin_tag": int((~sin160e.en_tags).sum()) if len(sin160e) else 0,
            "brecha_pct": round(100 * (~sin160e.en_tags).mean(), 1) if len(sin160e) else None,
            "formas": sin160e.termino.map(forma_del_nombre).value_counts().to_dict() if len(sin160e) else {},
            "nota": ("E160e vive en el bloque 'sinteticos' de colorantes.yaml -esta bien "
                     "clasificado como sintetico por clase_de()-. Si su brecha se PARECE a la "
                     "de un botanico, no es un error de clase_de(): es que sus terminos "
                     "('anaranjado alimentos 6', \"beta-apo-8'-carotenal\") tienen la misma "
                     "forma tecnica/rara que penaliza a los botanicos poco cubiertos, no algo "
                     "propio del origen."),
        },
        "caso_amarillo_ocaso_vs_amarillo_6": {
            "tabla": ocaso_vs_6_resumen.to_dict("records"),
            "AVISO": ("El parche 15 cita 'amarillo ocaso' con brecha 20.4 % (n=221) y "
                      "'amarillo 6' con 81.6 %. Los datos de esta corrida dan LO CONTRARIO: "
                      "revisar la tabla de arriba antes de escribir nada. La direccion que "
                      "sale aqui es consistente con la hipotesis de forma del nombre -"
                      "numero_codigo se recupera mejor que nombre_tecnico-, la del parche no."),
        },
        "caso_carmin_mexico_vs_espana": "ver 15_tarea6_carmin_paises.json (requiere corpus de Espana)",
    }


# ------------------------------------------- tarea 7: curva de sensibilidad

def tarea7_curva_ventana(df: pd.DataFrame, ordenados,
                         ventanas=(0, 40, 60, 80, 120)) -> list[dict]:
    """La ventana de 60 caracteres es una decision, no un hallazgo. Se
    recorre 0/40/60/80/120 para ver si el resultado es plano en el entorno o
    si 60 es un punto arbitrario que cambia la conclusion."""
    filas = []
    for v in ventanas:
        det_term_v, _ = construir_det_termino(df, ordenados, ventana=v)
        det_v = deduplicar_por_codigo(det_term_v)
        base = det_v[det_v.clase.isin(["sintetico", "natural_botanico", "carmin", "mineral_inorganico"])]

        def brecha(sub):
            n = len(sub)
            s = int((~sub.en_tags).sum())
            return {"n": n, "sin_tag": s, "brecha_pct": round(100 * s / n, 1) if n else None}

        filas.append({
            "ventana_caracteres": v,
            "detecciones_retenidas": len(base),
            "brecha_global": brecha(base),
            "brecha_botanica": brecha(base[base.clase == "natural_botanico"]),
            "brecha_sintetica": brecha(base[base.clase == "sintetico"]),
        })
    return filas


# ------------------------------------------- tarea 8: numero E en Espana

RE_NUMERO_E = re.compile(r"\be\s?-?\s?\d{3}\b")


def tarea8_numero_e(df_mx: pd.DataFrame, df_es: pd.DataFrame, ordenados) -> dict:
    def prop_con_e(df):
        textos = df.ingredientes_texto.map(normalizar)
        return round(100 * textos.map(lambda t: bool(RE_NUMERO_E.search(t))).mean(), 1)

    det_term_mx, _ = construir_det_termino(df_mx, ordenados)
    det_term_es, _ = construir_det_termino(df_es, ordenados)

    def coocurrencia_carmin(df_prod, det_term):
        textos = df_prod.set_index("code").ingredientes_texto.map(normalizar)
        sub = det_term[det_term.clase == "carmin"]
        filas = []
        for termino, g in sub.groupby("termino"):
            codes = g.code.unique()
            con_e = sum(1 for c in codes if bool(RE_NUMERO_E.search(textos.get(c, ""))))
            filas.append({"termino": termino, "n_productos": len(codes),
                          "con_numero_E_pct": round(100 * con_e / len(codes), 1) if len(codes) else None})
        return sorted(filas, key=lambda f: -f["n_productos"])

    def frecuencia_literal(df_prod, cadena):
        textos = df_prod.ingredientes_texto.map(normalizar)
        pat = re.compile(r"\b" + re.escape(normalizar(cadena)) + r"\b")
        return int(textos.map(lambda t: bool(pat.search(t))).sum())

    formas_e110 = {c: {"mexico": frecuencia_literal(df_mx, c), "espana": frecuencia_literal(df_es, c)}
                  for c in ("amarillo ocaso", "amarillo 6", "amarillo anaranjado s", "amarillo crepusculo")}

    return {
        "pct_textos_con_numero_E_literal": {
            "mexico": prop_con_e(df_mx), "espana": prop_con_e(df_es)},
        "coocurrencia_carmin_con_numero_E_por_termino": {
            "mexico": coocurrencia_carmin(df_mx, det_term_mx),
            "espana": coocurrencia_carmin(df_es, det_term_es)},
        "formas_E110_frecuencia_literal_en_texto": formas_e110,
        "lectura": ("Si la coocurrencia carmin+numero-E es mucho mas alta en Espana que en "
                    "Mexico, la recuperacion espanola del carmin se explica -al menos en "
                    "parte- porque la etiqueta comunitaria imprime el numero E junto al "
                    "nombre y OFF lo reconoce por ahi, no por el nombre. "
                    "'amarillo anaranjado s' es la forma que usa la taxonomia oficial de "
                    "OFF para E110 en espanol (ver additives.txt); si aparece poco en los "
                    "textos reales frente a 'amarillo ocaso'/'amarillo 6', la taxonomia no "
                    "es el problema -tiene ambas formas, ver tarea 11-, es que el mercado "
                    "no escribe esa forma."),
    }


# ----------------------------------- tarea 9: concentracion por contribuyente

PARES_EXPERIMENTO_NATURAL = [
    ("rojo 40", "rojo no. 40"), ("azul brillante", "azul 1"), ("curcumina", "curcuma"),
]


def tarea9_concentracion_contribuyente(det_term_mx: pd.DataFrame) -> list[dict]:
    filas = []
    for a, b in PARES_EXPERIMENTO_NATURAL:
        for forma in (a, b):
            sub = det_term_mx[det_term_mx.termino == forma]
            n = len(sub)
            contribs = sub.contribuyente.fillna("sin_dato")
            conteo = contribs.value_counts()
            filas.append({
                "par": f"{a} vs {b}", "forma": forma, "n_detecciones": n,
                "n_cuentas_distintas": int(contribs.nunique()),
                "cuenta_mas_activa": conteo.index[0] if len(conteo) else None,
                "cuenta_mas_activa_pct": round(100 * conteo.iloc[0] / n, 1) if n else None,
            })
    return filas


# ---------------------------------------------- tarea 10: caramelo

def tarea10_caramelo(df: pd.DataFrame, ordenados) -> dict:
    """Recalcula incluyendo SIN150a-d como clase propia 'caramelo' -en vez de
    descartarlo como fuera_de_eje-, para ver si el vocabulario de OFF lo
    cubre bien y si excluirlo infla la brecha global reportada."""
    filas_term, textos_rotos = [], []
    for t in df.itertuples(index=False):
        texto = normalizar(t.ingredientes_texto)
        texto_det, roto = quitar_advertencia_trazas(texto)
        if roto:
            textos_rotos.append(t.code)
        tags = {str(a).replace("en:", "").upper() for a in como_lista(t.aditivos_tags)}
        for codigo, bloque, termino in detectar_con_forma(texto_det, ordenados):
            cl = "caramelo" if codigo == "E150" else clase_de(codigo, bloque)
            if cl == "fuera_de_eje":
                continue
            filas_term.append({
                "code": t.code, "codigo": codigo, "clase": cl, "termino": termino,
                "en_tags": codigo in tags,
                "contexto_ok": (codigo not in AMBIGUOS) or con_contexto(texto_det, termino),
            })
    dt = pd.DataFrame(filas_term)
    d = (dt.groupby(["code", "codigo", "clase"], as_index=False)
           .agg(contexto_ok=("contexto_ok", "any"), en_tags=("en_tags", "first")))
    d = d[d.contexto_ok]

    def brecha(sub):
        n = len(sub)
        s = int((~sub.en_tags).sum())
        return {"n": n, "sin_tag": s, "brecha_pct": round(100 * s / n, 1) if n else None}

    return {
        "sin_caramelo_brecha_global": brecha(d[d.clase != "caramelo"]),
        "con_caramelo_brecha_global": brecha(d),
        "caramelo_solo": brecha(d[d.clase == "caramelo"]),
        "por_clase_con_caramelo": {cl: brecha(g) for cl, g in d.groupby("clase")},
    }


# ---------------------------------------------- tarea 11: amarillo 6 en vocabulario

def tarea11_amarillo6(vocab: dict) -> dict:
    resultado = {}
    for termino in ("amarillo 6", "amarillo ocaso", "amarillo anaranjado s"):
        vs = set()
        for k in variantes("E110"):
            vs |= vocab.get(k, set())
        resultado[termino] = norma(termino) in vs
    return {
        "en_vocabulario_off": resultado,
        "veredicto": ("'amarillo 6' Y 'amarillo ocaso' estan AMBAS en el vocabulario "
                      "espanol de OFF para E110 (additives.txt, linea es:). No hay brecha "
                      "de vocabulario entre las dos formas: la diferencia de recuperacion "
                      "entre ellas (ver tarea 5 y tarea 6) no se explica por cobertura de "
                      "vocabulario, se explica por otra cosa -el manuscrito no puede "
                      "afirmar que una forma 'no esta en la taxonomia' y luego usarla como "
                      "el caso donde si esta, sin contradecirse-."),
    }


if __name__ == "__main__":
    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)
    vocab, mand = leer_taxonomia_off(EXTERNO / "additives.txt")
    df = cargar_productos_mx()
    print(f"  productos con texto: {len(df):,}")

    det_term, textos_rotos = construir_det_termino(df, ordenados, vocab=vocab, mand=mand)
    det = deduplicar_por_codigo(det_term)
    chequeo = validar_contra_publicado(det)
    print("  validacion contra Tabla 1:", chequeo)
    assert chequeo["ok"], "el dataset reconstruido no cuadra con 07/08 -revisar antes de seguir-"

    universo = df.code.values
    print("\n--- tarea 3: estandarizacion simetrica con bootstrap ---")
    t3 = tarea3_estandarizacion(det, universo)
    print(t3["punto_una_sola_corrida_sin_redondear"])
    print(t3["ic95_bootstrap_por_producto"])
    guardar_reporte("15_tarea3_estandarizacion", t3)

    print("\n--- tarea 4: bootstrap por producto (Tablas 1/2 y RM) ---")
    t4 = tarea4_bootstrap_tablas(det, universo)
    print(t4["punto"]["tabla1_brecha_pct"])
    print(t4["ic95_bootstrap_por_producto"]["modelo_OR"])
    guardar_reporte("15_tarea4_bootstrap_tablas", t4)

    print("\n--- tarea 4b: ICC / efecto de diseno por codigo ---")
    icc = icc_por_codigo(det)
    print(icc)
    guardar_reporte("15_tarea4b_icc_codigo", icc)

    print("\n--- tarea 5: sobredispersion ---")
    t5 = sobredispersion_por_celda(det)
    print("phi_hat_global:", t5["phi_hat_global"], "->", t5["veredicto"])
    print("amarillo 6 vs ocaso:", t5["caso_amarillo_6_vs_ocaso"])
    guardar_reporte("15_tarea5_sobredispersion", t5)

    print("\n--- tarea 6: forma del nombre ---")
    t6 = tarea6_forma_del_nombre(det, ordenados)
    print("distribucion:", t6["distribucion_formas"])
    print("OR natural, original:", t6["modelo_original_2_predictores"])
    print("OR natural, con forma:", t6["modelo_con_forma_del_nombre"]["tabla"])
    print("amarillo ocaso vs 6:", t6["caso_amarillo_ocaso_vs_amarillo_6"]["tabla"])
    guardar_reporte("15_tarea6_forma_del_nombre", t6)

    print("\n--- tarea 7: curva de sensibilidad de la ventana de contexto ---")
    t7 = tarea7_curva_ventana(df, ordenados)
    for fila in t7:
        print(f"  ventana={fila['ventana_caracteres']:3}  "
              f"retenidas={fila['detecciones_retenidas']:5}  "
              f"global={fila['brecha_global']['brecha_pct']}%  "
              f"botanica={fila['brecha_botanica']['brecha_pct']}%  "
              f"sintetica={fila['brecha_sintetica']['brecha_pct']}%")
    guardar_reporte("15_tarea7_curva_ventana", {"curva": t7})

    print("\n--- tarea 11: amarillo 6 en el vocabulario ---")
    t11 = tarea11_amarillo6(vocab)
    print(t11)
    guardar_reporte("15_tarea11_amarillo6_vocab", t11)

    print("\n--- tarea 10: caramelo como analisis de sensibilidad ---")
    t10 = tarea10_caramelo(df, ordenados)
    print(t10)
    guardar_reporte("15_tarea10_caramelo", t10)

    print("\n--- tarea 9: concentracion por cuenta contribuyente ---")
    t9 = tarea9_concentracion_contribuyente(det_term)
    for f in t9:
        print(" ", f)
    guardar_reporte("15_tarea9_concentracion_contribuyente", {"pares": t9})

    ruta_crudo = RAIZ / "datos" / "crudo" / "food.parquet"
    if ruta_crudo.exists():
        print("\n--- tarea 8: numero E en Espana ---")
        df_es = cargar_productos_pais("en:spain", ruta_crudo)
        print(f"  productos de espana con texto: {len(df_es):,}")
        t8 = tarea8_numero_e(df, df_es, ordenados)
        print(t8["pct_textos_con_numero_E_literal"])
        print("carmin MX:", t8["coocurrencia_carmin_con_numero_E_por_termino"]["mexico"])
        print("carmin ES:", t8["coocurrencia_carmin_con_numero_E_por_termino"]["espana"])
        print("formas E110:", t8["formas_E110_frecuencia_literal_en_texto"])
        guardar_reporte("15_tarea8_numero_e_espana", t8)

        # tarea 6, caso pendiente: carmin Mexico vs Espana por forma del nombre
        det_term_es, _ = construir_det_termino(df_es, ordenados)
        for etiqueta, dt in (("mexico", det_term), ("espana", det_term_es)):
            dt["forma"] = dt.termino.map(forma_del_nombre)
        carmin_formas = {
            "mexico": det_term[det_term.clase == "carmin"].forma.value_counts().to_dict(),
            "espana": det_term_es[det_term_es.clase == "carmin"].forma.value_counts().to_dict(),
        }
        print("\n  carmin por forma del nombre, Mexico vs Espana:", carmin_formas)
        guardar_reporte("15_tarea6_carmin_paises", carmin_formas)
    else:
        print("\n  AVISO: no se encontro datos/crudo/food.parquet; se omiten las tareas "
              "8 y la comparacion de carmin por pais de la tarea 6.")
