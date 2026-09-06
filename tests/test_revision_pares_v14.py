"""Pruebas de las primitivas estadisticas del parche 16.

El parche 16 agrega metodos que el entorno no trae (no hay scipy ni
statsmodels): logistica por IRLS, sandwich por conglomerado, Nelder-Mead,
modelo mixto con intercepto aleatorio por cuadratura de Gauss-Hermite y la
descomposicion de Kitagawa en tres terminos. Todos se verifican aqui contra
casos con respuesta conocida — un metodo escrito a mano sin comprobar no
vale mas que la aproximacion que se quiso evitar.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_spec = importlib.util.spec_from_file_location(
    "p16", Path(__file__).resolve().parents[1] / "src" / "16_revision_pares_v14.py")
p16 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p16)


def _tabla_2x2(a, b, c, d):
    """x=1 con a exitos de a+b; x=0 con c exitos de c+d."""
    filas = []
    for xv, ex, n in ((1, a, a + b), (0, c, c + d)):
        for i in range(n):
            filas.append((xv, 1.0 if i < ex else 0.0))
    X = np.column_stack([np.ones(len(filas)), [f[0] for f in filas]])
    y = np.array([f[1] for f in filas])
    return X, y


# ------------------------------------------------------------- logistica

def test_logistica_reproduce_el_log_odds_ratio_exacto():
    """En una 2x2, la logistica tiene solucion cerrada: beta = log(ad/bc)."""
    X, y = _tabla_2x2(90, 10, 30, 70)
    beta, cov, _ = p16.ajustar_logistica(X, y)
    assert abs(float(np.exp(beta[1])) - 21.0) < 1e-6


def test_logistica_error_estandar_analitico():
    """EE del log-OR en una 2x2 = sqrt(1/a+1/b+1/c+1/d)."""
    X, y = _tabla_2x2(90, 10, 30, 70)
    _, cov, _ = p16.ajustar_logistica(X, y)
    esperado = (1 / 90 + 1 / 10 + 1 / 30 + 1 / 70) ** 0.5
    assert abs(float(np.sqrt(np.diag(cov))[1]) - esperado) < 1e-6


# ---------------------------------------------------------- Nelder-Mead

def test_nelder_mead_encuentra_el_minimo_de_una_cuadratica():
    f = lambda v: (v[0] - 3.0) ** 2 + (v[1] + 1.5) ** 2 + 7.0
    x, valor = p16.nelder_mead(f, np.array([0.0, 0.0]))
    assert abs(x[0] - 3.0) < 1e-3 and abs(x[1] + 1.5) < 1e-3
    assert abs(valor - 7.0) < 1e-6


# ---------------------------------------------------- sandwich agrupado

def test_sandwich_agrupado_se_ensancha_con_conglomerados_homogeneos():
    """Si el desenlace es identico dentro de cada conglomerado, la
    informacion real es la de los conglomerados y no la de las filas: el EE
    robusto tiene que ser MAYOR que el del modelo."""
    rng = np.random.default_rng(3)
    X, y, grupos = [], [], []
    for g in range(12):
        valor = float(g % 2)          # todo el conglomerado igual
        x = float(g < 6)
        for _ in range(40):
            X.append([1.0, x]); y.append(valor); grupos.append(g)
    X, y, grupos = np.array(X), np.array(y), np.array(grupos)
    beta, cov, _ = p16.ajustar_logistica(X, y)
    cov_rob = p16.cov_robusta_conglomerado(X, y, beta, grupos)
    assert np.sqrt(cov_rob[1, 1]) > np.sqrt(cov[1, 1])


# ----------------------------------------------------------------- GLMM

def test_glmm_recupera_sigma_con_muchos_conglomerados():
    """Con 250 grupos la varianza del intercepto se identifica bien. Con los
    24 codigos reales no — por eso el reporte lo advierte en vez de leer
    precision que no hay."""
    rng = np.random.default_rng(11)
    sigma_real, b0, b1 = 1.2, -0.5, 0.9
    X, y, grupos = [], [], []
    for g in range(250):
        u = rng.normal(0, sigma_real)
        for _ in range(40):
            x = float(rng.integers(0, 2))
            eta = b0 + b1 * x + u
            y.append(float(rng.random() < 1 / (1 + np.exp(-eta))))
            X.append([1.0, x]); grupos.append(g)
    r = p16.glmm_intercepto_aleatorio(np.array(X), np.array(y), np.array(grupos))
    assert r["convergio"]
    assert abs(r["sigma"] - sigma_real) < 0.25
    assert abs(r["beta"][1] - b1) < 0.15


def test_glmm_sin_agrupamiento_se_parece_a_la_logistica_plana():
    """Si no hay efecto de grupo, el mixto no debe inventar uno grande y sus
    coeficientes tienen que coincidir con los de la logistica ordinaria."""
    rng = np.random.default_rng(5)
    X, y, grupos = [], [], []
    for g in range(40):
        for _ in range(40):
            x = float(rng.integers(0, 2))
            eta = -0.3 + 0.8 * x
            y.append(float(rng.random() < 1 / (1 + np.exp(-eta))))
            X.append([1.0, x]); grupos.append(g)
    X, y, grupos = np.array(X), np.array(y), np.array(grupos)
    r = p16.glmm_intercepto_aleatorio(X, y, grupos)
    plano, _, _ = p16.ajustar_logistica(X, y)
    assert r["sigma"] < 0.25
    assert abs(r["beta"][1] - plano[1]) < 0.1


# ------------------------------------------------------------- Kitagawa

def test_kitagawa_los_tres_terminos_suman_la_diferencia_total():
    """La identidad que hace util la descomposicion: composicion + tasa +
    interaccion = diferencia cruda, exactamente."""
    filas = []
    for clase, ev, n, sin_tag in (("sintetico", True, 300, 60),
                                  ("sintetico", False, 100, 90),
                                  ("natural_botanico", True, 120, 80),
                                  ("natural_botanico", False, 200, 190)):
        for i in range(n):
            filas.append({"clase": clase, "en_vocab_off": ev,
                          "sin_tag": 1.0 if i < sin_tag else 0.0})
    base = pd.DataFrame(filas)
    r = p16.kitagawa_con_interaccion(base)
    d = r["descomposicion_kitagawa"]
    assert abs(d["suma_de_los_tres_pp"] - r["diferencia_cruda_base_comun_pp"]) < 1e-9


def test_kitagawa_sin_diferencia_de_composicion_anula_ese_termino():
    """Con la misma composicion en los dos origenes, el efecto de
    composicion y el de interaccion tienen que ser cero."""
    filas = []
    for clase, ev, n, sin_tag in (("sintetico", True, 200, 40),
                                  ("sintetico", False, 200, 180),
                                  ("natural_botanico", True, 100, 60),
                                  ("natural_botanico", False, 100, 95)):
        for i in range(n):
            filas.append({"clase": clase, "en_vocab_off": ev,
                          "sin_tag": 1.0 if i < sin_tag else 0.0})
    r = p16.kitagawa_con_interaccion(pd.DataFrame(filas))
    d = r["descomposicion_kitagawa"]
    assert abs(d["efecto_composicion_pp"]) < 1e-9
    assert abs(d["efecto_interaccion_pp"]) < 1e-9


# -------------------------------------------------- forma del nombre v2

def test_forma_v2_corrige_los_nombres_vernaculos_mal_clasificados():
    """Los que el parche 15 mandaba a nombre_tecnico y son nombre de la
    fuente. 'atsuete' es el que destapo el bug de determinismo: es sinonimo
    de achiote y de la misma longitud que 'achiote' y 'annatto'."""
    for t in ("atsuete", "urucu", "azafran", "azafran de indias",
              "conchita azul", "azul de jagua", "curcuma en polvo",
              "rojo betabel", "rojo de remolacha"):
        assert p16.agrupar_forma(p16.forma_del_nombre_v2(t)) == "nombre_comun_planta", t


def test_forma_v2_parte_el_numero_en_tres_familias():
    assert p16.forma_del_nombre_v2("e 102") == "codigo_e_ci"
    assert p16.forma_del_nombre_v2("ci 15985") == "codigo_e_ci"
    assert p16.forma_del_nombre_v2("rojo 40") == "designacion_fdc"
    assert p16.forma_del_nombre_v2("fd&c amarillo no. 5") == "designacion_fdc"
    assert p16.forma_del_nombre_v2("amarillo alimentos 3") == "indice_de_color"
    assert p16.forma_del_nombre_v2("pigmento blanco 6") == "indice_de_color"
    # y las tres colapsan al nivel grueso del parche 15
    for t in ("e 102", "rojo 40", "amarillo alimentos 3"):
        assert p16.agrupar_forma(p16.forma_del_nombre_v2(t)) == "numero_codigo"


# ------------------------------------------------------------ Levenshtein

def test_similitud_separa_erratas_de_terminos_distintos():
    """El umbral 0.82 esta elegido para que la errata entre y el termino
    distinto no."""
    assert p16.similitud("camin", "carmin") >= p16.UMBRAL_SIMILITUD
    assert p16.similitud("rojo 6", "rojo 40") < p16.UMBRAL_SIMILITUD
    assert p16.distancia_levenshtein("carmin", "carmin") == 0
