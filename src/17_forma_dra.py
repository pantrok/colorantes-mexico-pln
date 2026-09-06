"""Paso 17 — cerrar la variable de forma con la clasificacion de la coautora.

Origen: la Dra. Granados-Balbuena reclasifico los 197 terminos del diccionario
A CIEGAS -sin ver las tasas de recuperacion ni el repositorio- y coincide con
`forma_v2` (parche 16) en 188 de 197. Este paso incorpora su clasificacion,
recalcula los kappas dentro del repositorio, reajusta el modelo de forma con
sus etiquetas y resuelve los dos cabos que dejo el parche 16 (`rojo curry` y
`anaranjado 3`).

Por que importa: `forma_v2` la construimos nosotros mirando el mismo corpus
del que salen las tasas. Que una clasificadora independiente, ciega al
resultado, llegue casi al mismo sitio es lo que convierte la variable de
forma en algo defendible ante un arbitro. Los nueve desacuerdos se resuelven
a favor de ella en ocho casos, y el noveno (`rojo curry`) es una categoria
nueva con una sola deteccion.

Salidas: reportes/17_*.json y reportes/17_forma_tres_clasificadores.csv.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]

_spec16 = importlib.util.spec_from_file_location(
    "p16", Path(__file__).resolve().parent / "16_revision_pares_v14.py")
p16 = importlib.util.module_from_spec(_spec16)
_spec16.loader.exec_module(p16)
p15 = p16.p15
REPORTES = p15.REPORTES
EXTERNO = p15.EXTERNO

# Los nueve terminos donde la Dra. difiere de forma_v2. En los otros 188
# coincide, asi que forma_dra_ciega = forma_v2 salvo por esta tabla.
FORMA_DRA_DIFERENCIAS = {
    # Regla de ella, en sus palabras: el termino nombra la MOLECULA o la
    # clase de pigmento, no el organismo del que se obtiene.
    "caroteno": "nombre_tecnico",
    "carotenos": "nombre_tecnico",
    "carotenos mixtos": "nombre_tecnico",
    "caroteno natural": "nombre_tecnico",
    "beta caroteno": "nombre_tecnico",
    "betacaroteno": "nombre_tecnico",
    "extracto de betalaina": "nombre_tecnico",
    # Designacion de indice de color: forma_v2 ya movio "anaranjado alimentos
    # 6" y "anaranjado alimentos 7" a esa familia y dejo este fuera. Es una
    # inconsistencia nuestra, no de ella (ver tarea 4).
    "anaranjado 3": "numero_codigo",
    # "no es numero, denominacion quimica/tecnica ni nombre de fuente
    # inequivoco" -> categoria D, que aqui se llama "otra".
    "rojo curry": "otra",
}

# Erratas de transcripcion en el archivo que se le mando a la Dra., no del
# repositorio: hay que normalizarlas para que el emparejamiento literal no
# falle. No cambian ninguna respuesta suya.
ALIAS_ERRATAS = {"espiriulina": "espirulina"}


def forma_dra(termino: str, forma_v2: str) -> str:
    t = ALIAS_ERRATAS.get(termino, termino)
    return FORMA_DRA_DIFERENCIAS.get(t, forma_v2)


# =========================================================================
# TAREA 4 — `anaranjado 3` va con sus hermanos en la forma fina
# =========================================================================

def forma_fina_corregida(termino: str) -> str:
    """forma_del_nombre_v2 con `anaranjado 3` movido a indice_de_color, donde
    ya estaban `anaranjado alimentos 6` y `anaranjado alimentos 7`. Es la
    misma correccion que pide la Dra. por su lado: al agrupar, este termino
    pasa de nombre_tecnico a numero_codigo."""
    if termino.strip().lower() == "anaranjado 3":
        return "indice_de_color"
    return p16.forma_del_nombre_v2(termino)


def forma_v2_corregida(termino: str) -> str:
    return p16.agrupar_forma(forma_fina_corregida(termino))


# =========================================================================
# TAREA 1 — los tres clasificadores en una tabla
# =========================================================================

def tabla_tres_clasificadores(ordenados, vocab: dict) -> pd.DataFrame:
    filas = []
    for t, c, b in ordenados:
        v2 = p16.agrupar_forma(p16.forma_del_nombre_v2(t))
        filas.append({
            "termino": t, "codigo": c, "bloque": b,
            "forma_v1_parche15": p15.forma_del_nombre(t),
            "forma_v2_parche16": v2,
            "forma_v2_corregida": forma_v2_corregida(t),
            "forma_fina_corregida": forma_fina_corregida(t),
            "forma_dra_ciega": forma_dra(t, v2),
            "en_sinonimario_off": p16.pertenencia_literal(t, c, vocab),
        })
    tabla = pd.DataFrame(filas)
    tabla["coinciden_v2_y_dra"] = tabla.forma_v2_parche16 == tabla.forma_dra_ciega
    return tabla


# =========================================================================
# TAREA 5 — los kappas, calculados aqui y con IC
# =========================================================================

def tarea5_kappas(tabla: pd.DataFrame) -> dict:
    pares = {
        "v1_parche15_vs_dra": ("forma_v1_parche15", "forma_dra_ciega"),
        "v2_parche16_vs_dra": ("forma_v2_parche16", "forma_dra_ciega"),
        "v1_parche15_vs_v2_parche16": ("forma_v1_parche15", "forma_v2_parche16"),
    }
    salida = {}
    for nombre, (a, b) in pares.items():
        k = p15.cohen_kappa(tabla[a], tabla[b])
        acuerdo = int((tabla[a] == tabla[b]).sum())
        salida[nombre] = {
            "acuerdo_n": acuerdo, "acuerdo_pct": round(100 * acuerdo / len(tabla), 1),
            "kappa": k["kappa"], "ic95": k["ic95"], "se": k["se"],
            "po": k["po"], "pe": k["pe"], "categorias": k["categorias"],
        }
    categorias = sorted(set(tabla.forma_v2_parche16) | set(tabla.forma_dra_ciega))
    matriz = (pd.crosstab(tabla.forma_v2_parche16, tabla.forma_dra_ciega)
                .reindex(index=categorias, columns=categorias, fill_value=0))
    return {
        "n_terminos": int(len(tabla)),
        "kappas": salida,
        "matriz_confusion_v2_contra_dra": matriz.to_dict("index"),
        "marginales": {
            "forma_v1_parche15": tabla.forma_v1_parche15.value_counts().to_dict(),
            "forma_v2_parche16": tabla.forma_v2_parche16.value_counts().to_dict(),
            "forma_dra_ciega": tabla.forma_dra_ciega.value_counts().to_dict(),
        },
        "desacuerdos_v2_vs_dra": (
            tabla[~tabla.coinciden_v2_y_dra]
            [["termino", "codigo", "forma_v2_parche16", "forma_dra_ciega"]]
            .to_dict("records")),
        "nota": ("Kappa de Cohen simple, sin pesos, con IC por la varianza asintotica de "
                 "Fleiss, Cohen y Everitt (1969) -la misma funcion que se uso para el "
                 "kappa entre anotadores en el parche 15-."),
    }


# =========================================================================
# TAREAS 2 y 3 — reajuste con las etiquetas de la Dra.
# =========================================================================

def base_con_forma(det: pd.DataFrame, mapa_forma) -> pd.DataFrame:
    """Misma base que el parche 16 (sintetico + natural_botanico,
    mandatory=False, 2769 detecciones), con la columna de forma que se le
    pase."""
    base = det[det.clase.isin(["sintetico", "natural_botanico"]) & (~det.off_mandatory)].copy()
    base["natural"] = (base.clase == "natural_botanico").astype(float)
    base["fuera_vocab"] = (~base.en_vocab_off).astype(float)
    base["sin_tag"] = (~base.en_tags).astype(float)
    base["forma"] = base.termino.map(mapa_forma)
    return base


def modelo_de_forma(base: pd.DataFrame, etiqueta: str, referencia: str = "numero_codigo") -> dict:
    formas = sorted(base.forma.unique())
    for f in formas:
        base[f"es_{f}"] = (base.forma == f).astype(float)
    covs = ["natural"] + [f"es_{f}" for f in formas if f != referencia]
    r = p16.intervalos_triples(base, covs, etiqueta)
    r["referencia"] = referencia
    r["n_por_forma"] = base.forma.value_counts().to_dict()
    return r


def tarea2_reajuste(det: pd.DataFrame) -> dict:
    base_v2 = base_con_forma(det, lambda t: p16.agrupar_forma(p16.forma_del_nombre_v2(t)))
    base_dra = base_con_forma(
        det, lambda t: forma_dra(t, p16.agrupar_forma(p16.forma_del_nombre_v2(t))))

    # Opcion 1 del cabo `rojo curry`: dejarla donde cae con la regla de ella
    # ("otra"), que con una sola deteccion no se estima bien.
    m_v2 = modelo_de_forma(base_v2, "forma_v2 (parche 16)")
    m_dra_con_otra = modelo_de_forma(base_dra, "forma_dra_ciega, con la categoria 'otra'")

    # El modelo de vocabulario NO lleva termino de forma: es identico con
    # cualquier clasificacion. Se reporta una vez para dejarlo por escrito.
    m_vocab = p16.intervalos_triples(base_v2, ["natural", "fuera_vocab"],
                                     "vocabulario (invariante a la clasificacion de forma)")

    return {
        "aviso_modelo_de_vocabulario": ("El modelo de vocabulario no incluye ningun termino "
            "de forma, asi que es IDENTICO con forma_v2 y con forma_dra_ciega. Solo cambia "
            "el modelo de forma."),
        "modelo_vocabulario": m_vocab,
        "modelo_forma_v2": m_v2,
        "modelo_forma_dra": m_dra_con_otra,
    }


def tarea3_rojo_curry(det: pd.DataFrame) -> dict:
    """Tres opciones para la unica deteccion de categoria D, con el numero al
    lado."""
    def mapa_dra(t):
        return forma_dra(t, p16.agrupar_forma(p16.forma_del_nombre_v2(t)))

    base = base_con_forma(det, mapa_dra)
    n_curry = int((base.termino == "rojo curry").sum())

    # opcion 1: rojo curry se queda en nombre_tecnico
    base1 = base.copy()
    base1.loc[base1.termino == "rojo curry", "forma"] = "nombre_tecnico"
    op1 = modelo_de_forma(base1, "opcion 1: rojo curry en nombre_tecnico")

    # opcion 2: se excluye el termino del modelo
    base2 = base[base.termino != "rojo curry"].copy()
    op2 = modelo_de_forma(base2, "opcion 2: rojo curry excluido")

    # opcion 3: cuarta categoria con n=1
    op3 = modelo_de_forma(base.copy(), "opcion 3: cuarta categoria 'otra' con n=1")

    def coefs(m):
        return {c["termino"]: {"RM": c["RM"], "mixto": c["ic_mixto_intercepto_por_codigo"]}
                for c in m["coeficientes"]}

    return {
        "n_detecciones_de_rojo_curry": n_curry,
        "opcion_1_en_nombre_tecnico": {"n_modelo": op1["n_detecciones"], "coeficientes": coefs(op1)},
        "opcion_2_excluido": {"n_modelo": op2["n_detecciones"], "coeficientes": coefs(op2)},
        "opcion_3_cuarta_categoria": {"n_modelo": op3["n_detecciones"], "coeficientes": coefs(op3)},
    }


# =========================================================================
# TAREA 4 — subfamilias con `anaranjado 3` corregido
# =========================================================================

def tarea4_subfamilias(det_term: pd.DataFrame) -> dict:
    d = det_term[det_term.clase.isin(["sintetico", "natural_botanico"]) & det_term.contexto_ok].copy()
    d["sin_tag"] = (~d.en_tags).astype(float)

    def tabla(col_forma_fina, col_forma):
        d["_fina"] = d.termino.map(col_forma_fina)
        d["_grueso"] = d.termino.map(col_forma)
        sub = d[d._grueso == "numero_codigo"]
        g = (sub.groupby("_fina")
                .agg(n=("sin_tag", "size"), sin_tag=("sin_tag", "sum"),
                     n_terminos=("termino", "nunique")).reset_index())
        g["brecha_pct"] = (100 * g.sin_tag / g.n).round(1)
        return g.rename(columns={"_fina": "subfamilia"}).to_dict("records")

    antes = tabla(p16.forma_del_nombre_v2,
                  lambda t: p16.agrupar_forma(p16.forma_del_nombre_v2(t)))
    despues = tabla(forma_fina_corregida, forma_v2_corregida)
    n_curry_det = int((d.termino == "anaranjado 3").sum())
    return {
        "detecciones_de_anaranjado_3": n_curry_det,
        "subfamilias_antes": antes,
        "subfamilias_despues": despues,
        "nota": ("`anaranjado 3` estaba en nombre_tecnico mientras sus hermanos "
                 "`anaranjado alimentos 6` y `anaranjado alimentos 7` estaban en "
                 "indice_de_color. Corregido, el termino pasa ademas de nombre_tecnico a "
                 "numero_codigo en el nivel grueso, que es justo lo que dijo la Dra. por "
                 "su cuenta."),
    }


# =========================================================================
# TAREA 6 — el dato exacto de la Figura 1 sobre base comun
# =========================================================================

def tarea6_datos_figura1() -> dict:
    """No se puede RENDERIZAR la figura en este repositorio y hay que decirlo:
    no hay ninguna libreria grafica instalada (ni matplotlib, ni PIL, ni
    svgwrite), requirements.txt es deliberadamente minimo, no existe ningun
    script que genere figuras -las tres del manuscrito se hicieron fuera- y
    `GRAPHICAL_ABSTRACT_spec_v2.md` no esta en el repositorio ni en ninguna
    parte a la que este proceso tenga acceso (solo hay una v1, que ademas es
    un brief de diseno para un ilustrador, no una especificacion de ploteo).

    Lo que si se puede entregar, y es lo que hace falta para rehacerla, es el
    dato exacto con sus intervalos. Eso va aqui."""
    t2 = pd.read_json(REPORTES / "16_tarea2_base_comun.json", typ="series")
    punto, ic = t2["punto"], t2["ic95_bootstrap_por_producto"]
    k = punto["descomposicion_kitagawa"]
    return {
        "no_se_renderiza_aqui": ("Sin libreria grafica en el entorno y sin pipeline de "
            "figuras en el repositorio. Se entrega el dato, no el TIFF."),
        "spec_referida_no_encontrada": ("El parche cita GRAPHICAL_ABSTRACT_spec_v2.md; no "
            "existe en el repositorio. La unica version localizable es una v1 fuera del "
            "repo, y es un brief de diseno, no una especificacion de ploteo."),
        "valores_que_hay_que_SUSTITUIR_en_la_figura_vigente": {
            "brecha_botanica_observada_pct": {"antes": 90.41, "ahora": round(punto["brecha_botanica_base_comun_pct"], 2)},
            "diferencia_cruda_pp": {"antes": 53.65, "ahora": round(punto["diferencia_cruda_base_comun_pp"], 2)},
            "denominador_botanico": {"antes": 438, "ahora": 364},
        },
        "valores_de_base_comun": {
            "brecha_sintetica_pct": round(punto["brecha_sintetica_base_comun_pct"], 2),
            "brecha_botanica_pct": round(punto["brecha_botanica_base_comun_pct"], 2),
            "diferencia_cruda_pp": round(punto["diferencia_cruda_base_comun_pp"], 2),
            "diferencia_cruda_ic95": ic["diferencia_cruda_pp"],
            "tasa_botanica_estandarizada_pct": round(
                punto["direccion_A_peso_sintetico"]["tasa_botanica_estandarizada_pct"], 2),
            "tasa_botanica_estandarizada_ic95": ic["tasa_botanica_estandarizada_pct"],
            "reparto_residual_pct": round(
                100 * punto["direccion_A_peso_sintetico"]["fraccion_residual"], 1),
            "reparto_residual_ic95_pct": [round(100 * v, 1) for v in ic["fraccion_residual_A"]],
        },
        "descomposicion_de_kitagawa_para_la_figura": [
            {"termino": "composicion", "pp": round(k["efecto_composicion_pp"], 2),
             "ic95": ic["efecto_composicion_pp"]},
            {"termino": "tasa", "pp": round(k["efecto_tasa_pp"], 2),
             "ic95": ic["efecto_tasa_pp"]},
            {"termino": "interaccion", "pp": round(k["efecto_interaccion_pp"], 2),
             "ic95": ic["efecto_interaccion_pp"]},
            {"termino": "suma (= diferencia cruda)", "pp": round(k["suma_de_los_tres_pp"], 2),
             "ic95": ic["diferencia_cruda_pp"]},
        ],
        "aviso_para_quien_la_dibuje": ("La interaccion es NEGATIVA y grande (-21.76 pp). Una "
            "figura que apile composicion y tasa como si sumaran la diferencia cruda estara "
            "mal: 35.11 + 38.36 = 73.47, no 51.70. El tercer termino tiene que aparecer."),
    }


if __name__ == "__main__":
    dic = p15.cargar_diccionario()
    ordenados = p15.terminos_ordenados(dic)
    vocab, mand = p15.leer_taxonomia_off(EXTERNO / "additives.txt")
    df = p15.cargar_productos_mx()
    det_term, _ = p15.construir_det_termino(df, ordenados, vocab=vocab, mand=mand)
    det = p15.deduplicar_por_codigo(det_term)
    chequeo = p15.validar_contra_publicado(det)
    print("  validacion contra Tabla 1:", chequeo)
    assert chequeo["ok"]

    print("\n--- tarea 1: los tres clasificadores ---")
    tabla = tabla_tres_clasificadores(ordenados, vocab)
    REPORTES.mkdir(exist_ok=True)
    tabla.to_csv(REPORTES / "17_forma_tres_clasificadores.csv", index=False, encoding="utf-8")
    print(f"  -> 17_forma_tres_clasificadores.csv  ({len(tabla)} terminos, "
          f"{int(tabla.coinciden_v2_y_dra.sum())} coincidencias con la Dra.)")

    print("\n--- tarea 5: kappas en el repositorio ---")
    p15.guardar_reporte("17_tarea5_kappas", tarea5_kappas(tabla))

    print("\n--- tarea 4: subfamilias con anaranjado 3 corregido ---")
    p15.guardar_reporte("17_tarea4_subfamilias", tarea4_subfamilias(det_term))

    print("\n--- tarea 2: reajuste con las etiquetas de la Dra. ---")
    p15.guardar_reporte("17_tarea2_reajuste", tarea2_reajuste(det))

    print("\n--- tarea 3: rojo curry, tres opciones ---")
    p15.guardar_reporte("17_tarea3_rojo_curry", tarea3_rojo_curry(det))

    print("\n--- tarea 6: dato de la Figura 1 sobre base comun ---")
    p15.guardar_reporte("17_tarea6_datos_figura1", tarea6_datos_figura1())
