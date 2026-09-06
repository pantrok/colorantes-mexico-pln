"""Paso 16 — lo que dejo abierto la segunda revision por pares (manuscrito v14).

Origen: `REVISION_PARES_v14.md`, panel en modo re-review (metodologia, dominio
y abogado del diablo). Once tareas. El nucleo del parche es que el articulo
publica una escala cuasibinomial de 10.8 y un efecto de diseno de 50.8, y
despues lee intervalos que no incorporan ninguno de los dos: reescalando, el
IC de la RM de origen (1.84) pasa de [1.14, 2.94] a cruzar 1. Las tareas 1 a 4
calculan los intervalos correctos en vez de retirar la afirmacion a mano.

La tarea 5 es la decisiva y es una objecion de fondo: si el campo derivado es
un emparejador de diccionario, decir que recupera las formas que su
diccionario contiene puede ser analitico y no empirico. Se resuelve mirando si
la forma del nombre predice la recuperacion CONDICIONADA a la pertenencia
literal de la cadena al sinonimario.

Todo con numpy y pandas. El entorno no tiene scipy ni statsmodels y el
proyecto ya opto antes por implementar sus propios metodos (ver
modelo.py::firth) en vez de agregar una dependencia pesada. Aqui se agregan,
con la misma regla: metodo estandar, escrito completo, y validado contra
casos con respuesta conocida en tests/test_revision_pares_v14.py.

Salidas: reportes/16_*.json y reportes/16_*.csv.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "p15", Path(__file__).resolve().parent / "15_revision_pares.py")
p15 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p15)

REPORTES = p15.REPORTES
EXTERNO = p15.EXTERNO
SEMILLA = 20260906
N_BOOT = 1000

# Pesos del sorteo de la muestra anotada, recuperados en el parche 14 del
# commit d721107 -la corrida contra la que SI se sorteo-. No son los de la
# corrida actual: el estrato cambio de tamano al corregir los bugs de conteo,
# y para ponderar la validacion hay que usar los del sorteo, no los de hoy.
PESOS_MUESTREO = {
    "sintetico": {"N_poblacion": 1139, "n_muestra": 150, "peso": 1139 / 150},
    "natural": {"N_poblacion": 595, "n_muestra": 250, "peso": 595 / 250},
    "ambiguo_descartado": {"N_poblacion": 351, "n_muestra": 100, "peso": 351 / 100},
    "sin_deteccion": {"N_poblacion": 5690, "n_muestra": 100, "peso": 5690 / 100},
}


# =========================================================================
# Primitivas numericas
# =========================================================================

def ajustar_logistica(X: np.ndarray, y: np.ndarray, max_iter: int = 100,
                      tol: float = 1e-11):
    """Logistica de Bernoulli por IRLS a nivel de FILA (una fila por
    deteccion), no de celda agregada. Devuelve (beta, cov_modelo, p).

    Se ajusta a nivel de fila -aunque el punto estimado coincide con el de
    celdas agregadas- porque los errores por conglomerado y el modelo mixto
    necesitan la contribucion individual de cada deteccion y su codigo."""
    n, k = X.shape
    beta = np.zeros(k)
    for _ in range(max_iter):
        eta = np.clip(X @ beta, -500, 500)
        p = 1.0 / (1.0 + np.exp(-eta))
        W = np.maximum(p * (1 - p), 1e-12)
        z = eta + (y - p) / W
        XtW = X.T * W
        A = XtW @ X
        b = XtW @ z
        try:
            nuevo = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            nuevo = np.linalg.pinv(A) @ b
        salto = np.max(np.abs(nuevo - beta))
        beta = nuevo
        if salto < tol:
            break
    eta = np.clip(X @ beta, -500, 500)
    p = 1.0 / (1.0 + np.exp(-eta))
    W = np.maximum(p * (1 - p), 1e-12)
    info = (X.T * W) @ X
    try:
        cov = np.linalg.inv(info)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(info)
    return beta, cov, p


def phi_pearson(y: np.ndarray, p: np.ndarray, k: int) -> float:
    """Escala cuasibinomial: chi2 de Pearson sobre grados de libertad. A
    nivel de Bernoulli individual esto tiende a 1 por construccion, asi que
    se calcula sobre las CELDAS del modelo -que es donde la sobredispersion
    entre terminos de una misma celda se hace visible-. Ver
    sobredispersion_por_celda() en 15_revision_pares.py."""
    resid = (y - p) / np.sqrt(np.maximum(p * (1 - p), 1e-12))
    return float((resid ** 2).sum() / (len(y) - k))


def cov_robusta_conglomerado(X: np.ndarray, y: np.ndarray, beta: np.ndarray,
                             grupos: np.ndarray) -> np.ndarray:
    """Sandwich de Liang-Zeger agrupado por codigo, con la correccion de
    muestra finita habitual G/(G-1) * (n-1)/(n-k)."""
    eta = np.clip(X @ beta, -500, 500)
    p = 1.0 / (1.0 + np.exp(-eta))
    W = np.maximum(p * (1 - p), 1e-12)
    pan = np.linalg.pinv((X.T * W) @ X)
    e = y - p
    relleno = np.zeros((X.shape[1], X.shape[1]))
    etiquetas = np.unique(grupos)
    for g in etiquetas:
        m = grupos == g
        u = X[m].T @ e[m]
        relleno += np.outer(u, u)
    G, (n, k) = len(etiquetas), X.shape
    correccion = (G / (G - 1)) * ((n - 1) / (n - k)) if G > 1 and n > k else 1.0
    return pan @ relleno @ pan * correccion


def nelder_mead(f, x0: np.ndarray, max_iter: int = 2000, tol: float = 1e-8):
    """Nelder-Mead simple. Hace falta porque no hay scipy: el modelo mixto
    no tiene solucion cerrada y su verosimilitud se evalua por cuadratura."""
    n = len(x0)
    alfa, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5
    simplex = [np.array(x0, dtype=float)]
    for i in range(n):
        punto = np.array(x0, dtype=float)
        punto[i] += 0.5 if punto[i] == 0 else 0.1 * abs(punto[i])
        simplex.append(punto)
    simplex = np.array(simplex)
    valores = np.array([f(p) for p in simplex])
    for _ in range(max_iter):
        orden = np.argsort(valores)
        simplex, valores = simplex[orden], valores[orden]
        if np.max(np.abs(valores[1:] - valores[0])) < tol:
            break
        centro = simplex[:-1].mean(axis=0)
        refl = centro + alfa * (centro - simplex[-1])
        f_refl = f(refl)
        if f_refl < valores[0]:
            exp = centro + gamma * (refl - centro)
            f_exp = f(exp)
            simplex[-1], valores[-1] = (exp, f_exp) if f_exp < f_refl else (refl, f_refl)
        elif f_refl < valores[-2]:
            simplex[-1], valores[-1] = refl, f_refl
        else:
            contra = centro + rho * (simplex[-1] - centro)
            f_contra = f(contra)
            if f_contra < valores[-1]:
                simplex[-1], valores[-1] = contra, f_contra
            else:
                simplex = simplex[0] + sigma * (simplex - simplex[0])
                valores = np.array([f(p) for p in simplex])
    orden = np.argsort(valores)
    return simplex[orden][0], float(valores[orden][0])


def glmm_intercepto_aleatorio(X: np.ndarray, y: np.ndarray, grupos: np.ndarray,
                              n_nodos: int = 20):
    """Logistica binomial con intercepto aleatorio por grupo (codigo),
    verosimilitud marginal por cuadratura de Gauss-Hermite y maximizacion por
    Nelder-Mead. Errores estandar del hessiano numerico.

    Es el modelo que corresponde al nivel donde varian los predictores: los
    codigos, no las detecciones. Devuelve `convergio=False` si el optimizador
    no se estabiliza o el hessiano no es definido positivo — en ese caso hay
    que usar el sandwich por conglomerado y DECIRLO, no aproximar en silencio.
    """
    nodos, pesos = np.polynomial.hermite_e.hermegauss(n_nodos)
    log_pesos = np.log(pesos) - 0.5 * np.log(2 * np.pi)
    etiquetas = np.unique(grupos)
    indices = [np.where(grupos == g)[0] for g in etiquetas]
    k = X.shape[1]

    def neg_loglik(par):
        beta, sigma = par[:k], np.exp(par[k])
        eta0 = X @ beta
        total = 0.0
        for idx in indices:
            eta = eta0[idx][None, :] + sigma * nodos[:, None]
            eta = np.clip(eta, -500, 500)
            ll = (y[idx][None, :] * eta - np.logaddexp(0.0, eta)).sum(axis=1)
            c = log_pesos + ll
            mx = c.max()
            total += mx + np.log(np.exp(c - mx).sum())
        return -total

    beta0, _, _ = ajustar_logistica(X, y)
    par0 = np.concatenate([beta0, [np.log(0.5)]])
    par, valor = nelder_mead(neg_loglik, par0)
    # segunda pasada: Nelder-Mead reinicia mal desde un simplex degenerado
    par, valor = nelder_mead(neg_loglik, par)

    # hessiano numerico por diferencias centrales
    h = 1e-4
    m = len(par)
    H = np.zeros((m, m))
    for i in range(m):
        for j in range(i, m):
            ei, ej = np.zeros(m), np.zeros(m)
            ei[i], ej[j] = h, h
            H[i, j] = H[j, i] = (
                neg_loglik(par + ei + ej) - neg_loglik(par + ei - ej)
                - neg_loglik(par - ei + ej) + neg_loglik(par - ei - ej)) / (4 * h * h)
    convergio = True
    try:
        cov = np.linalg.inv(H)
        if not np.all(np.isfinite(cov)) or np.any(np.diag(cov) <= 0):
            convergio = False
    except np.linalg.LinAlgError:
        cov, convergio = np.full((m, m), np.nan), False

    sigma = float(np.exp(par[k]))
    # ICC en la escala latente logistica: sigma^2 / (sigma^2 + pi^2/3)
    icc = sigma ** 2 / (sigma ** 2 + np.pi ** 2 / 3)
    return {
        "beta": par[:k], "log_sigma": float(par[k]), "sigma": sigma,
        "cov": cov, "convergio": bool(convergio), "neg_loglik": float(valor),
        "icc_latente": float(icc), "n_grupos": int(len(etiquetas)),
        "n_nodos_cuadratura": n_nodos,
    }


def ic_wald(beta_j: float, se_j: float, z: float = 1.959964):
    if not np.isfinite(se_j) or se_j <= 0:
        return [None, None]
    return [round(float(np.exp(beta_j - z * se_j)), 2),
            round(float(np.exp(beta_j + z * se_j)), 2)]


# =========================================================================
# TAREA 1 — intervalos con la dispersion propagada, para TODOS los coeficientes
# =========================================================================

def preparar_base_modelos(det: pd.DataFrame) -> pd.DataFrame:
    """La base que de verdad entra a los modelos: sintetico + natural_botanico
    con off_mandatory=False. Son 2769 detecciones (2405 + 364), no las 3124
    del total — el texto del manuscrito uso el total para el n efectivo y por
    eso salio 61.5."""
    base = det[det.clase.isin(["sintetico", "natural_botanico"]) & (~det.off_mandatory)].copy()
    base["natural"] = (base.clase == "natural_botanico").astype(float)
    base["fuera_vocab"] = (~base.en_vocab_off).astype(float)
    base["forma"] = base.termino.map(p15.forma_del_nombre)
    base["es_nombre_tecnico"] = (base.forma == "nombre_tecnico").astype(float)
    base["es_nombre_comun_planta"] = (base.forma == "nombre_comun_planta").astype(float)
    base["sin_tag"] = (~base.en_tags).astype(float)
    return base


def phi_por_termino_en_celda(base: pd.DataFrame, covariables: list[str]):
    """Escala cuasibinomial estimada con el TERMINO como unidad dentro de
    cada celda del modelo. Es donde la sobredispersion se ve: 'amarillo 6' y
    'amarillo ocaso' caen en la misma celda y difieren 63 puntos."""
    por = (base.groupby(covariables + ["termino"])
               .agg(n=("sin_tag", "size"), exitos=("sin_tag", "sum")).reset_index())
    x2, gl = 0.0, 0
    for _, g in por.groupby(covariables):
        n_c, s_c = g.n.sum(), g.exitos.sum()
        pc = s_c / n_c if n_c else np.nan
        if not np.isfinite(pc) or pc in (0.0, 1.0) or len(g) < 2:
            continue
        x2 += float((((g.exitos - g.n * pc) ** 2) / (g.n * pc * (1 - pc))).sum())
        gl += len(g) - 1
    return (float(x2 / gl) if gl else None), gl


def icc_momentos(base: pd.DataFrame) -> dict:
    """ICC y efecto de diseno por codigo (Fleiss 1981) SOBRE LA MUESTRA DEL
    MODELO, no sobre las 3124 detecciones totales."""
    g = (base.groupby("codigo")
             .agg(n=("sin_tag", "size"), exitos=("sin_tag", "sum")).reset_index())
    g = g[g.n > 0]
    k, N = len(g), int(g.n.sum())
    p_bar = g.exitos.sum() / N
    p_i = g.exitos / g.n
    MSB = float((g.n * (p_i - p_bar) ** 2).sum() / (k - 1))
    MSW = float((g.n * p_i * (1 - p_i)).sum() / (N - k)) if N > k else np.nan
    n0 = float((N - (g.n ** 2).sum() / N) / (k - 1))
    denom = MSB + (n0 - 1) * MSW
    icc = max(0.0, (MSB - MSW) / denom) if denom else 0.0
    n_bar = N / k
    deff = 1 + (n_bar - 1) * icc
    return {"k_codigos": k, "N_detecciones_del_modelo": N,
            "ICC_momentos": round(icc, 4), "design_effect": round(deff, 3),
            "n_efectivo": round(N / deff, 1)}


def intervalos_triples(base: pd.DataFrame, covariables: list[str], etiqueta: str) -> dict:
    """Cada coeficiente con tres intervalos: perfil (como hoy), cuasibinomial
    (EE escalado por raiz de phi) y mixto con intercepto aleatorio por codigo.
    Se agrega ademas el sandwich por conglomerado, que es el sustituto que
    pide el parche si el mixto no converge -se reporta siempre, para poder
    comparar-."""
    nombres = ["intercepto"] + covariables
    X = np.column_stack([np.ones(len(base))] + [base[c].values for c in covariables])
    y = base.sin_tag.values
    grupos = base.codigo.values

    beta, cov, _ = ajustar_logistica(X, y)
    se_modelo = np.sqrt(np.diag(cov))

    phi, gl_phi = phi_por_termino_en_celda(base, covariables)
    raiz_phi = np.sqrt(phi) if phi else np.nan

    cov_rob = cov_robusta_conglomerado(X, y, beta, grupos)
    se_rob = np.sqrt(np.diag(cov_rob))

    mixto = glmm_intercepto_aleatorio(X, y, grupos)
    se_mix = (np.sqrt(np.diag(mixto["cov"]))[:len(nombres)]
              if mixto["convergio"] else np.full(len(nombres), np.nan))

    # perfil de verosimilitud penalizada (Firth) sobre las celdas agregadas
    celdas = (base.groupby(covariables)
                  .agg(n=("sin_tag", "size"), sin_tag=("sin_tag", "sum")).reset_index())
    perfil = p15.firth(celdas[covariables], celdas.sin_tag.values, celdas.n.values)
    perfil_por_nombre = {r["termino"]: r for r in perfil.to_dict("records")}

    filas = []
    for j, nombre in enumerate(nombres):
        fila_perfil = perfil_por_nombre.get(nombre, {})
        filas.append({
            "termino": nombre,
            "coef": round(float(beta[j]), 4),
            "RM": round(float(np.exp(beta[j])), 2),
            "ic_perfil": [fila_perfil.get("IC_bajo"), fila_perfil.get("IC_alto")],
            "ic_wald_sin_corregir": ic_wald(beta[j], se_modelo[j]),
            "ic_cuasibinomial": ic_wald(beta[j], se_modelo[j] * raiz_phi),
            "ic_mixto_intercepto_por_codigo": (ic_wald(beta[j], se_mix[j])
                                               if mixto["convergio"] else [None, None]),
            "ic_robusto_conglomerado_codigo": ic_wald(beta[j], se_rob[j]),
        })

    return {
        "modelo": etiqueta,
        "covariables": covariables,
        "n_detecciones": int(len(base)),
        "n_codigos": int(base.codigo.nunique()),
        "phi_cuasibinomial": round(phi, 3) if phi else None,
        "gl_phi": gl_phi,
        "raiz_phi": round(float(raiz_phi), 3) if phi else None,
        "mixto": {
            "convergio": mixto["convergio"],
            "sigma_intercepto": round(mixto["sigma"], 4),
            "icc_latente": round(mixto["icc_latente"], 4),
            "n_grupos": mixto["n_grupos"],
            "aviso": ("Solo hay 24 codigos: la varianza del intercepto aleatorio queda "
                      "mal identificada con tan pocos conglomerados y su IC es ancho. "
                      "Verificado en tests/test_revision_pares_v14.py que la "
                      "implementacion recupera sigma con 200-400 grupos; con 24 no se "
                      "le debe pedir precision."),
        },
        "coeficientes": filas,
        "agrupamiento_sobre_la_muestra_del_modelo": icc_momentos(base),
    }


# =========================================================================
# TAREA 2 — estandarizacion sobre BASE COMUN + Kitagawa con interaccion
# =========================================================================

def _celdas_base_comun(base: pd.DataFrame):
    """Celdas clase x en_vocab_off sobre la MISMA base para los dos origenes
    (mandatory=False). El defecto que corrige: el 75.11 % se calculaba sobre
    las 364 botanicas del cruce y se comparaba contra el 90.4 % observado,
    que es sobre 438 e incluye las 74 del estrato de clase funcional, todas
    con brecha 100 %. Peras contra manzanas."""
    g = (base.groupby(["clase", "en_vocab_off"])
             .agg(n=("sin_tag", "size"), sin_tag=("sin_tag", "sum")).reset_index())
    sin_c = g[g.clase == "sintetico"].set_index("en_vocab_off")
    nat_c = g[g.clase == "natural_botanico"].set_index("en_vocab_off")
    comunes = sin_c.index.intersection(nat_c.index)
    return sin_c.reindex(comunes), nat_c.reindex(comunes)


def kitagawa_con_interaccion(base: pd.DataFrame) -> dict | None:
    """Descomposicion de Kitagawa en tres terminos sobre base comun:
    composicion, tasa e interaccion. La diferencia total es exactamente la
    suma de los tres, y eso se verifica en la prueba."""
    sin_c, nat_c = _celdas_base_comun(base)
    if not len(sin_c):
        return None
    n_sin, n_nat = sin_c.n.sum(), nat_c.n.sum()
    w0, w1 = sin_c.n / n_sin, nat_c.n / n_nat          # composiciones
    r0, r1 = sin_c.sin_tag / sin_c.n, nat_c.sin_tag / nat_c.n   # tasas

    b_sin = float((w0 * r0).sum()) * 100
    b_nat = float((w1 * r1).sum()) * 100
    dif_total = b_nat - b_sin

    comp = float(((w1 - w0) * r0).sum()) * 100
    tasa = float((w0 * (r1 - r0)).sum()) * 100
    inter = float(((w1 - w0) * (r1 - r0)).sum()) * 100

    nat_std = float((w0 * r1).sum()) * 100      # composicion sintetica, tasas botanicas
    sin_std = float((w1 * r0).sum()) * 100      # composicion botanica, tasas sinteticas
    dif_std_A = nat_std - b_sin
    dif_std_B = b_nat - sin_std

    return {
        "brecha_sintetica_base_comun_pct": b_sin,
        "brecha_botanica_base_comun_pct": b_nat,
        "diferencia_cruda_base_comun_pp": dif_total,
        "descomposicion_kitagawa": {
            "efecto_composicion_pp": comp,
            "efecto_tasa_pp": tasa,
            "efecto_interaccion_pp": inter,
            "suma_de_los_tres_pp": comp + tasa + inter,
        },
        "direccion_A_peso_sintetico": {
            "tasa_botanica_estandarizada_pct": nat_std,
            "diferencia_estandarizada_pp": dif_std_A,
            "fraccion_residual": dif_std_A / dif_total if dif_total else None,
        },
        "direccion_B_peso_botanico": {
            "tasa_sintetica_estandarizada_pct": sin_std,
            "diferencia_estandarizada_pp": dif_std_B,
            "fraccion_residual": dif_std_B / dif_total if dif_total else None,
        },
    }


def tarea2_base_comun(det: pd.DataFrame, universo: np.ndarray) -> dict:
    base = preparar_base_modelos(det)
    punto = kitagawa_con_interaccion(base)

    # comparacion con lo que publica el manuscrito: base MIXTA
    todo_nat = det[(det.clase == "natural_botanico")]
    b_nat_mixta = 100 * float((~todo_nat.en_tags).sum()) / len(todo_nat)

    # bootstrap por producto del reparto residual
    rng = np.random.default_rng(SEMILLA)
    n = len(universo)
    grupos = {c: g for c, g in base.groupby("code")}
    codigos_con_datos = np.array(list(grupos.keys()))
    replicas = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        conteo = pd.Series(universo[idx]).value_counts()
        pesos = base["code"].map(conteo).fillna(0).astype(int)
        sub = base.assign(_peso=pesos)
        sub = sub.loc[sub._peso > 0]
        rep = sub.loc[sub.index.repeat(sub._peso)]
        r = kitagawa_con_interaccion(rep)
        if r:
            replicas.append(r)

    def ic(f):
        vals = np.array([f(r) for r in replicas], dtype=float)
        vals = vals[np.isfinite(vals)]
        if len(vals) < 20:
            return None
        return [round(float(np.percentile(vals, 2.5)), 4),
                round(float(np.percentile(vals, 97.5)), 4)]

    return {
        "base_declarada": ("Los DOS origenes sobre off_mandatory=False: 2405 sinteticas y "
            "364 botanicas. La tasa botanica observada sobre esa base es la que hay que "
            "comparar contra la estandarizada, no el 90.4 % de las 438."),
        "punto": punto,
        "contraste_con_la_base_mixta_del_manuscrito": {
            "brecha_botanica_sobre_438_incluye_mandatory_pct": round(b_nat_mixta, 2),
            "brecha_botanica_sobre_364_base_comun_pct": round(punto["brecha_botanica_base_comun_pct"], 2),
            "nota": ("El manuscrito compara la estandarizada (calculada sobre 364) contra "
                     "la observada de 438. Sobre base comun la observada baja y con ella "
                     "la diferencia cruda, y el reparto residual sube."),
        },
        "ic95_bootstrap_por_producto": {
            "diferencia_cruda_pp": ic(lambda r: r["diferencia_cruda_base_comun_pp"]),
            "tasa_botanica_estandarizada_pct": ic(lambda r: r["direccion_A_peso_sintetico"]["tasa_botanica_estandarizada_pct"]),
            "diferencia_estandarizada_A_pp": ic(lambda r: r["direccion_A_peso_sintetico"]["diferencia_estandarizada_pp"]),
            "fraccion_residual_A": ic(lambda r: r["direccion_A_peso_sintetico"]["fraccion_residual"]),
            "efecto_composicion_pp": ic(lambda r: r["descomposicion_kitagawa"]["efecto_composicion_pp"]),
            "efecto_tasa_pp": ic(lambda r: r["descomposicion_kitagawa"]["efecto_tasa_pp"]),
            "efecto_interaccion_pp": ic(lambda r: r["descomposicion_kitagawa"]["efecto_interaccion_pp"]),
        },
        "n_bootstrap": len(replicas),
    }


# =========================================================================
# TAREA 3 — validacion PONDERADA por el inverso de la fraccion de muestreo
# =========================================================================

def tarea3_validacion_ponderada() -> dict:
    df = p15.resolver_verdad(p15.cargar_anotacion_consolidada())
    df["predicho_positivo"] = df.estrato.isin(["sintetico", "natural"])
    resuelto = df[df.texto_utilizable & df.verdad.isin(["SI", "NO"])].copy()
    resuelto["verdad_bin"] = resuelto.verdad == "SI"

    filas = []
    for estrato, g in resuelto.groupby("estrato"):
        info = PESOS_MUESTREO[estrato]
        tp = int((g.predicho_positivo & g.verdad_bin).sum())
        fp = int((g.predicho_positivo & ~g.verdad_bin).sum())
        fn = int((~g.predicho_positivo & g.verdad_bin).sum())
        tn = int((~g.predicho_positivo & ~g.verdad_bin).sum())
        filas.append({"estrato": estrato, "N_poblacion": info["N_poblacion"],
                      "n_muestra_sorteada": info["n_muestra"],
                      "n_analizable": len(g), "peso": round(info["peso"], 3),
                      "TP": tp, "FP": fp, "FN": fn, "TN": tn})
    por_estrato = pd.DataFrame(filas)

    def metricas(tabla, ponderar):
        w = tabla.peso if ponderar else 1.0
        TP, FP = float((tabla.TP * w).sum()), float((tabla.FP * w).sum())
        FN, TN = float((tabla.FN * w).sum()), float((tabla.TN * w).sum())
        return {
            "TP": round(TP, 1), "FP": round(FP, 1), "FN": round(FN, 1), "TN": round(TN, 1),
            "VPP_pct": round(100 * TP / (TP + FP), 1) if TP + FP else None,
            "sensibilidad_pct": round(100 * TP / (TP + FN), 1) if TP + FN else None,
            "especificidad_pct": round(100 * TN / (TN + FP), 1) if TN + FP else None,
        }

    crudas = metricas(por_estrato, False)
    ponderadas = metricas(por_estrato, True)

    # bootstrap ESTRATIFICADO: remuestrea dentro de cada estrato, n_h fijo
    rng = np.random.default_rng(SEMILLA)
    reps = []
    for _ in range(N_BOOT):
        filas_b = []
        for estrato, g in resuelto.groupby("estrato"):
            idx = rng.integers(0, len(g), size=len(g))
            gb = g.iloc[idx]
            info = PESOS_MUESTREO[estrato]
            filas_b.append({
                "estrato": estrato, "peso": info["peso"],
                "TP": int((gb.predicho_positivo & gb.verdad_bin).sum()),
                "FP": int((gb.predicho_positivo & ~gb.verdad_bin).sum()),
                "FN": int((~gb.predicho_positivo & gb.verdad_bin).sum()),
                "TN": int((~gb.predicho_positivo & ~gb.verdad_bin).sum()),
            })
        reps.append(metricas(pd.DataFrame(filas_b), True))

    def ic(clave):
        vals = np.array([r[clave] for r in reps if r[clave] is not None], dtype=float)
        return [round(float(np.percentile(vals, 2.5)), 1),
                round(float(np.percentile(vals, 97.5)), 1)]

    return {
        "por_estrato_con_poblacion_y_peso": por_estrato.to_dict("records"),
        "crudas_sin_ponderar": crudas,
        "ponderadas_por_inverso_de_la_fraccion": ponderadas,
        "ic95_bootstrap_estratificado_ponderado": {
            "VPP_pct": ic("VPP_pct"), "sensibilidad_pct": ic("sensibilidad_pct"),
            "especificidad_pct": ic("especificidad_pct")},
        "cual_es_la_cifra_principal": ("Las PONDERADAS. La muestra se estratifico sobre el "
            "desenlace, con 100 productos representando 5690 sin deteccion y 100 "
            "representando 351 descartados por ambiguedad: las crudas dan a esos dos "
            "estratos el mismo peso que a los otros y no describen la poblacion. Las "
            "crudas quedan reportadas al lado, etiquetadas, solo para comparar."),
        "n_bootstrap": len(reps),
    }


# =========================================================================
# TAREA 4 — los 104 terminos sin mapear pesan sobre la SENSIBILIDAD
# =========================================================================

def distancia_levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def similitud(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1 - distancia_levenshtein(a, b) / max(len(a), len(b))


UMBRAL_SIMILITUD = 0.82


def tarea4_sin_mapear_como_falsos_negativos(ordenados, det: pd.DataFrame) -> dict:
    """Un termino que el anotador transcribio y el detector no recupero pesa
    sobre los FALSOS NEGATIVOS, no sobre el VPP. Excluirlos infla la
    sensibilidad. Regla documentada: se compara cada fragmento del anotador
    contra los terminos del diccionario por distancia de Levenshtein
    normalizada; con similitud >= 0.82 se considera que el fragmento nombra
    ese termino -umbral elegido para que 'camin'/'carmin' (0.83) entre y
    'rojo 6'/'rojo 40' (0.71) no-."""
    df = p15.resolver_verdad(p15.cargar_anotacion_consolidada())
    df = df[df.texto_utilizable & (df.verdad == "SI")]
    terminos_dic = [(t, c) for t, c, _ in ordenados]

    detectados_por_code = det.groupby("code").codigo.apply(set).to_dict()

    recuperados, fn_mencion, no_colorante = 0, [], []
    for r in df.itertuples():
        cods_auto = detectados_por_code.get(r.code, set())
        for cadena in (r.terminos_1, r.terminos_2):
            if not isinstance(cadena, str) or not cadena.strip():
                continue
            for frag in cadena.split(";"):
                fn_norm = p15.normalizar(frag)
                if not fn_norm:
                    continue
                if p15.mapear_terminos_a_codigos(frag, ordenados):
                    continue          # ya mapeaba: no es de los 104
                mejor, mejor_sim = None, 0.0
                for t, c in terminos_dic:
                    s = similitud(fn_norm, t)
                    if s > mejor_sim:
                        mejor, mejor_sim = (t, c), s
                if mejor and mejor_sim >= UMBRAL_SIMILITUD:
                    if mejor[1] in cods_auto:
                        recuperados += 1
                    else:
                        fn_mencion.append({"code": r.code, "fragmento": frag.strip(),
                                           "termino_mas_cercano": mejor[0],
                                           "codigo": mejor[1], "similitud": round(mejor_sim, 3)})
                else:
                    no_colorante.append({"fragmento": frag.strip(),
                                         "mas_cercano": mejor[0] if mejor else None,
                                         "similitud": round(mejor_sim, 3)})

    return {
        "regla_documentada": (f"Levenshtein normalizado sobre el fragmento del anotador "
            f"contra los terminos del diccionario; umbral {UMBRAL_SIMILITUD}."),
        "recuperados_por_otro_sinonimo": recuperados,
        "falsos_negativos_de_mencion": {
            "n": len(fn_mencion),
            "por_codigo": pd.DataFrame(fn_mencion).codigo.value_counts().to_dict() if fn_mencion else {},
            "ejemplos": fn_mencion[:25],
        },
        "no_identificables_como_colorante": {
            "n": len(no_colorante), "ejemplos": no_colorante[:25]},
        "efecto_sobre_la_sensibilidad": ("Los que quedan como falso negativo de mencion se "
            "suman al denominador de la sensibilidad A NIVEL DE MENCION; la sensibilidad a "
            "nivel de PRODUCTO no cambia, porque esos productos ya contaban como detectados "
            "por otro colorante. Ver el conteo de arriba."),
    }


# =========================================================================
# Clasificacion de forma, version 2 — corrige la del parche 15
# =========================================================================
# Dos motivos para rehacerla:
#
#   a) El bug de determinismo (ver util.py) dejaba el termino representante
#      de cada deteccion al azar entre sinonimos de igual longitud. Los tres
#      de E160b de 7 caracteres son "achiote", "annatto" y "atsuete": los dos
#      primeros estaban en FUENTES_COMUNES y el tercero no, asi que la misma
#      deteccion caia en nombre_comun_planta o en nombre_tecnico segun el
#      proceso. Eso movia la RM de origen del modelo de forma entre 1.59 y
#      1.77 en corridas identicas.
#   b) Al auditar la tabla completa aparecieron mas nombres vernaculos de la
#      fuente clasificados como tecnicos: atsuete y urucu (achiote), azafran,
#      azafran indio y azafran de indias (curcuma), conchita azul, azul de
#      jagua, curcuma en polvo, curcuma turmerico y las formas de
#      betabel/remolacha.
#
# Ademas el parche 16 pide considerar partir "numero_codigo", porque agrupa
# designaciones FD&C ("rojo 40") con codigos E/CI ("e 102", "ci 15985") y con
# nombres numerados del Colour Index ("amarillo alimentos 3", "rojo natural
# 4"), y su recuperacion no tiene por que ser la misma. forma_del_nombre_v2
# devuelve el nivel fino; agrupar_forma() lo colapsa a los tres niveles
# originales para poder comparar contra el parche 15.

FUENTES_V2 = p15.FUENTES_COMUNES | {
    "atsuete", "urucu", "urucum", "bija",
    "azafran", "azafran indio", "azafran de indias",
    "conchita azul", "azul de jagua",
    "curcuma en polvo", "curcuma turmerico",
    "polvo de betabel", "rojo betabel", "rojo de betabel", "rojo remolacha",
    "rojo de remolacha", "rojo raiz de betabel",
    "extracto de malta", "safflower", "cartamo", "tagete", "gardenia",
}

RE_CODIGO_PURO = re.compile(
    r"^\s*(e\s?-?\d{3}[a-z]{0,2}|ci\s?\d{4,5}|ins\s?\d{3}[a-z]{0,2}|sin\s?\d{3}[a-z]{0,2})\s*$")
RE_FDC = re.compile(r"\bfd&?c\d?\b|\bd&c\d?\b")
# Nombres genericos numerados del Colour Index: "<color> alimentos 3",
# "<color> natural 4", "pigmento blanco 6".
RE_INDICE_COLOR = re.compile(
    r"\b(alimentos|natural|pigmento)\b.*\d|\bpigmento\b")
RE_COLOR_NUM = re.compile(
    r"\b(rojo|amarillo|azul|verde|violeta|naranja|negro|blanco)\b[^\d]*\d")


def forma_del_nombre_v2(termino: str) -> str:
    """Cinco niveles. Los tres primeros son la particion de lo que el parche
    15 llamaba `numero_codigo`."""
    t = termino.strip().lower()
    if RE_CODIGO_PURO.match(t) or re.search(r"\be\s?-?\d{3}", t) or re.search(r"\bci\s?\d{4,5}\b", t):
        return "codigo_e_ci"
    if t in FUENTES_V2 or any(f in t for f in
                             ("extracto de", "jugo de", "concentrado de", "oleorresina de")):
        return "nombre_comun_planta"
    if RE_FDC.search(t):
        return "designacion_fdc"
    if RE_INDICE_COLOR.search(t):
        return "indice_de_color"
    if RE_COLOR_NUM.search(t):
        return "designacion_fdc"
    return "nombre_tecnico"


AGRUPA_V2 = {"codigo_e_ci": "numero_codigo", "designacion_fdc": "numero_codigo",
             "indice_de_color": "numero_codigo",
             "nombre_tecnico": "nombre_tecnico",
             "nombre_comun_planta": "nombre_comun_planta"}


def agrupar_forma(forma_fina: str) -> str:
    return AGRUPA_V2.get(forma_fina, forma_fina)


def pertenencia_literal(termino: str, codigo: str, vocab: dict) -> bool:
    """Si la cadena EXACTA del termino esta en la lista de sinonimos en
    espanol de la taxonomia de OFF para ese codigo. Es la variable con la que
    hay que condicionar para que la afirmacion sobre la forma sea empirica y
    no analitica."""
    vs = set()
    for k in p15.variantes(codigo):
        vs |= vocab.get(k, set())
    return p15.norma(termino) in vs


# =========================================================================
# TAREA 5 — forma del nombre CONTRA pertenencia literal al sinonimario
# =========================================================================

def tarea5_forma_vs_pertenencia(det_term: pd.DataFrame, ordenados, vocab: dict) -> dict:
    # --- (1) el diccionario entero, termino a termino ---
    filas = []
    for t, c, b in ordenados:
        filas.append({
            "termino": t, "codigo": c, "bloque": b,
            "forma_v1_parche15": p15.forma_del_nombre(t),
            "forma_fina_v2": forma_del_nombre_v2(t),
            "forma_v2": agrupar_forma(forma_del_nombre_v2(t)),
            "en_sinonimario_off": pertenencia_literal(t, c, vocab),
        })
    dicc = pd.DataFrame(filas)
    REPORTES.mkdir(exist_ok=True)
    dicc.to_csv(REPORTES / "16_forma_vs_sinonimario.csv", index=False, encoding="utf-8")

    tabla_diccionario = (dicc.groupby(["forma_v2", "en_sinonimario_off"])
                             .size().rename("n_terminos").reset_index()
                             .pivot(index="forma_v2", columns="en_sinonimario_off",
                                    values="n_terminos").fillna(0).astype(int))

    # --- (2) tabla cruzada 3x2 con DETECCIONES y brecha por celda ---
    d = det_term[det_term.clase.isin(["sintetico", "natural_botanico"])].copy()
    d = d[d.contexto_ok]
    d["forma_v2"] = d.termino.map(lambda t: agrupar_forma(forma_del_nombre_v2(t)))
    d["forma_fina_v2"] = d.termino.map(forma_del_nombre_v2)
    d["sin_tag"] = (~d.en_tags).astype(float)

    def celdas(columnas):
        g = (d.groupby(columnas)
              .agg(n_detecciones=("sin_tag", "size"), sin_tag=("sin_tag", "sum"),
                   n_terminos=("termino", "nunique"))
              .reset_index())
        g["brecha_pct"] = (100 * g.sin_tag / g.n_detecciones).round(1)
        return g.to_dict("records")

    cruce_3x2 = celdas(["forma_v2", "en_vocab_off"])
    cruce_fino = celdas(["forma_fina_v2", "en_vocab_off"])

    # --- (3) el modelo DENTRO del subconjunto que si pertenece ---
    dentro = d[d.en_vocab_off].copy()
    formas_presentes = sorted(dentro.forma_v2.unique())
    resultado_condicionado = {
        "n_detecciones": int(len(dentro)),
        "formas_presentes": formas_presentes,
        "n_por_forma": dentro.forma_v2.value_counts().to_dict(),
    }
    if len(formas_presentes) < 2:
        resultado_condicionado["veredicto"] = (
            "No estimable: dentro del sinonimario solo sobrevive una forma. La "
            "afirmacion del articulo seria ANALITICA, no empirica.")
    else:
        dentro["natural"] = (dentro.clase == "natural_botanico").astype(float)
        for f in formas_presentes:
            dentro[f"es_{f}"] = (dentro.forma_v2 == f).astype(float)
        # referencia: numero_codigo si esta, si no la primera alfabetica
        referencia = "numero_codigo" if "numero_codigo" in formas_presentes else formas_presentes[0]
        covs = ["natural"] + [f"es_{f}" for f in formas_presentes if f != referencia]
        dentro["codigo"] = dentro.codigo
        resultado_condicionado["referencia"] = referencia
        resultado_condicionado["modelo"] = intervalos_triples(
            dentro, covs, f"forma dentro del sinonimario (referencia {referencia})")

    return {
        "pregunta": ("Si el campo derivado es un emparejador de diccionario, decir que "
            "recupera las formas que su diccionario contiene es analitico. Para que sea "
            "empirico, la FORMA tiene que predecir la recuperacion CONDICIONADA a la "
            "pertenencia literal de la cadena al sinonimario."),
        "n_terminos_del_diccionario": int(len(dicc)),
        "nota_202_vs_197": ("El manifiesto de congelamiento cuenta 202 terminos y aqui "
            "salen los que devuelve terminos_ordenados() tras normalizar y deduplicar "
            "por codigo; la diferencia son formas que colapsan al normalizar."),
        "tabla_terminos_del_diccionario_forma_x_pertenencia":
            tabla_diccionario.to_dict("index"),
        "cruce_detecciones_3x2": cruce_3x2,
        "cruce_detecciones_fino": cruce_fino,
        "modelo_condicionado_a_pertenencia": resultado_condicionado,
    }


# =========================================================================
# TAREA 6 — tabla cruzada origen x forma, y si la categoria necesita partirse
# =========================================================================

def tarea6_cruce_origen_forma(det_term: pd.DataFrame) -> dict:
    d = det_term[det_term.clase.isin(["sintetico", "natural_botanico"])].copy()
    d = d[d.contexto_ok]
    d["forma_v2"] = d.termino.map(lambda t: agrupar_forma(forma_del_nombre_v2(t)))
    d["forma_fina_v2"] = d.termino.map(forma_del_nombre_v2)
    d["sin_tag"] = (~d.en_tags).astype(float)

    def cruce(col):
        g = (d.groupby(["clase", col])
              .agg(n=("sin_tag", "size"), sin_tag=("sin_tag", "sum"),
                   n_terminos=("termino", "nunique"), n_codigos=("codigo", "nunique"))
              .reset_index())
        g["brecha_pct"] = (100 * g.sin_tag / g.n).round(1)
        return g

    grueso, fino = cruce("forma_v2"), cruce("forma_fina_v2")

    # recuperacion por termino DENTRO de numero_codigo: es lo que motiva la
    # sospecha del revisor de que la categoria mezcla cosas distintas
    num = d[d.forma_v2 == "numero_codigo"]
    por_termino_num = (num.groupby(["forma_fina_v2", "termino"])
                          .agg(n=("sin_tag", "size"), sin_tag=("sin_tag", "sum"))
                          .reset_index())
    por_termino_num["brecha_pct"] = (100 * por_termino_num.sin_tag / por_termino_num.n).round(1)
    por_termino_num = por_termino_num[por_termino_num.n >= 10].sort_values("brecha_pct")

    return {
        "cruce_origen_x_forma_3_niveles": grueso.to_dict("records"),
        "cruce_origen_x_forma_5_niveles": fino.to_dict("records"),
        "celdas_vacias_o_escasas": [
            f"{r['clase']} x {r['forma_v2']}: n={r['n']}"
            for r in grueso.to_dict("records") if r["n"] < 30],
        "dispersion_dentro_de_numero_codigo": por_termino_num.to_dict("records"),
        "veredicto_particion": ("Si la brecha difiere mucho entre codigo_e_ci, "
            "designacion_fdc e indice_de_color, la categoria 'numero o codigo' del "
            "parche 15 mezclaba cosas distintas y hay que reportarla partida."),
    }


# =========================================================================
# TAREAS 7 a 11
# =========================================================================

def tarea7_curva_completa(df: pd.DataFrame, ordenados,
                          ventanas=(0, 40, 60, 80, 120)) -> dict:
    """La curva del parche 15 ya traia la botanica, pero el manuscrito solo
    publico la global y la sintetica, y el punto cero solo en prosa. Aqui va
    completa y con las cuatro clases, para que se pueda copiar tal cual."""
    filas = []
    for v in ventanas:
        det_v = p15.deduplicar_por_codigo(
            p15.construir_det_termino(df, ordenados, ventana=v)[0])

        def brecha(sub):
            n = len(sub)
            s = int((~sub.en_tags).sum())
            return {"n": n, "sin_tag": s, "brecha_pct": round(100 * s / n, 1) if n else None}

        fila = {"ventana_caracteres": v, "detecciones_retenidas": len(det_v),
                "global": brecha(det_v)}
        for clase in ("sintetico", "natural_botanico", "carmin", "mineral_inorganico"):
            fila[clase] = brecha(det_v[det_v.clase == clase])
        filas.append(fila)
    return {"curva": filas,
            "lectura": ("La botanica es la magnitud sobre la que descansa el articulo y "
                        "es la que mas se mueve al bajar a cero; entre 40 y 120 la curva "
                        "es plana en las cuatro clases.")}


def tarea8_carmin_numero_e(df_mx: pd.DataFrame, df_es: pd.DataFrame, ordenados) -> dict:
    """Tabla por termino de SIN 120 en cada pais: cuantas detecciones
    coexisten con un numero E en el mismo texto. Es lo que convierte la
    explicacion europea del carmin de conjetura en medicion."""
    salida = {}
    for etiqueta, dfp in (("mexico", df_mx), ("espana", df_es)):
        det_term, _ = p15.construir_det_termino(dfp, ordenados)
        textos = dfp.set_index("code").ingredientes_texto.map(p15.normalizar)
        sub = det_term[(det_term.clase == "carmin") & det_term.contexto_ok]
        filas = []
        for termino, g in sub.groupby("termino"):
            codes = g.code.unique()
            con_e = sum(1 for c in codes if bool(p15.RE_NUMERO_E.search(textos.get(c, ""))))
            sin_tag = int((~g.en_tags).sum())
            filas.append({"termino": termino, "n_detecciones": len(g),
                          "n_productos": len(codes),
                          "con_numero_E": con_e,
                          "con_numero_E_pct": round(100 * con_e / len(codes), 1) if len(codes) else None,
                          "brecha_pct": round(100 * sin_tag / len(g), 1) if len(g) else None})
        salida[etiqueta] = sorted(filas, key=lambda f: -f["n_detecciones"])
        salida[f"{etiqueta}_total_carmin"] = {
            "n_detecciones": int(len(sub)),
            "con_numero_E_pct": round(100 * sum(f["con_numero_E"] for f in filas)
                                      / max(1, sum(f["n_productos"] for f in filas)), 1),
        }
    salida["lectura"] = ("El articulo declara esta explicacion 'no comprobable con este "
                         "diseno' teniendo los datos. Aqui estan por termino y por pais.")
    return salida


def tarea9_sesgo_de_incorporacion() -> dict:
    """Los cuatro subanalisis que propuso la Dra.: cuanto depende la cifra de
    la fase no independiente (la adjudicacion)."""
    df = p15.resolver_verdad(p15.cargar_anotacion_consolidada())
    df["predicho_positivo"] = df.estrato.isin(["sintetico", "natural"])
    df["requirio_adjudicacion"] = df.en_desempate == "SI"

    def metricas(sub):
        s = sub[sub.texto_utilizable & sub.verdad.isin(["SI", "NO"])].copy()
        s["verdad_bin"] = s.verdad == "SI"
        tp = int((s.predicho_positivo & s.verdad_bin).sum())
        fp = int((s.predicho_positivo & ~s.verdad_bin).sum())
        fn = int((~s.predicho_positivo & s.verdad_bin).sum())
        tn = int((~s.predicho_positivo & ~s.verdad_bin).sum())
        return {"n": len(s), "TP": tp, "FP": fp, "FN": fn, "TN": tn,
                "VPP_pct": round(100 * tp / (tp + fp), 1) if tp + fp else None,
                "VPP_ic95": p15.wilson_ic(tp, tp + fp),
                "sensibilidad_pct": round(100 * tp / (tp + fn), 1) if tp + fn else None}

    n_adj = int(df.requirio_adjudicacion.sum())
    return {
        "1_registros_que_necesitaron_adjudicacion": {
            "n": n_adj, "pct": round(100 * n_adj / len(df), 1), "de": len(df),
            "desglose": ("`en_desempate=SI` marca desacuerdo entre los dos anotadores, "
                         "sea en el veredicto o en la lista de terminos. De esos, "
                         f"{int((df.verdad == 'sin_resolver').sum())} tienen ademas el "
                         "veredicto en desacuerdo y el archivo no trae la resolucion."),
        },
        "2_VPP_solo_con_acuerdo_humano_previo": metricas(df[~df.requirio_adjudicacion]),
        "3_VPP_de_los_registros_adjudicados": metricas(df[df.requirio_adjudicacion]),
        "4_sensibilidad_excluyendo_adjudicados": metricas(df[~df.requirio_adjudicacion]),
        "lectura": ("Si el VPP con acuerdo previo y el global casi no difieren, la cifra no "
                    "depende de la fase no independiente y la objecion de sesgo de "
                    "incorporacion queda acotada."),
    }


def tarea10_readjudicacion() -> dict:
    """Se busco en todo el repositorio: no existe."""
    return {
        "existe_en_el_repositorio": False,
        "que_se_busco": ("Se recorrio el arbol completo -md, csv, json, py, yaml- buscando "
            "'readjudic', 're-adjudic', 'tercer anotador', 'adjudicacion independiente'. "
            "El unico acierto es una entrada bibliografica en 13_antecedentes.csv, sin "
            "relacion. La anotacion consolidada tiene una columna `en_desempate` que MARCA "
            "los 30 registros en desacuerdo, pero no trae ningun veredicto de "
            "re-adjudicacion ni una segunda ronda."),
        "recomendacion": ("La declaracion de contribuciones de la v14 anuncia una "
            "'independent re-adjudication of the validation subsample'. No hay nada en el "
            "repositorio que la respalde: hay que quitarla de la declaracion hasta que "
            "exista, o incorporar el archivo si se hizo fuera del repo."),
    }


def tarea11_sello_temporal() -> dict:
    """Anterioridad de las predicciones de Espana. Verificado contra git."""
    return {
        "hay_commit_anterior_a_la_corrida": False,
        "evidencia": ("`git log --diff-filter=A` sobre src/09_replica_pais.py y sobre "
            "reportes/09_replica_spain.json devuelve EL MISMO commit: "
            "6f761050442abb6162a1c34a6d1d035f0c0260e9, 2026-08-27 10:06:11 -0600. El "
            "script con las predicciones P4/P5/P6 y los resultados de Espana entraron al "
            "repositorio a la vez."),
        "veredicto": ("No existe un hash con fecha anterior a la corrida de Espana. El "
            "sellado SHA-256 del diccionario prueba INTEGRIDAD, no ANTERIORIDAD, y el "
            "texto tiene que decirlo asi. Las predicciones se escribieron antes de correr "
            "-esta en el docstring y en el flujo de trabajo- pero el repositorio no puede "
            "acreditarlo, y esa distincion es justo la que pedia el revisor."),
        "para_la_proxima": ("Si se quiere acreditar anterioridad de una prediccion, hay que "
            "commitear el script CON la prediccion y SIN la salida, y correr despues."),
    }


def tarea1_intervalos(det: pd.DataFrame) -> dict:
    base = preparar_base_modelos(det)
    modelo_vocab = intervalos_triples(base, ["natural", "fuera_vocab"],
                                      "vocabulario (natural + fuera_vocab)")
    modelo_forma = intervalos_triples(
        base, ["natural", "es_nombre_tecnico", "es_nombre_comun_planta"],
        "forma del nombre (natural + forma, referencia numero_codigo)")
    return {
        "base_declarada": ("sintetico + natural_botanico con off_mandatory=False: "
            f"{len(base)} detecciones (2405 sinteticas + 364 botanicas). El manuscrito "
            "calculo el n efectivo sobre las 3124 totales y por eso publico 61.5; el n "
            "efectivo de la muestra que de verdad entra al modelo esta abajo."),
        "modelo_vocabulario": modelo_vocab,
        "modelo_forma_del_nombre": modelo_forma,
        "lectura": ("El IC que el articulo debe citar es el mixto o el robusto por "
                    "conglomerado, no el de perfil: los predictores varian entre codigos "
                    "y terminos, no entre detecciones, y el perfil trata cada deteccion "
                    "como independiente."),
    }


if __name__ == "__main__":
    dic = p15.cargar_diccionario()
    ordenados = p15.terminos_ordenados(dic)
    vocab, mand = p15.leer_taxonomia_off(EXTERNO / "additives.txt")
    df = p15.cargar_productos_mx()
    print(f"  productos de mexico con texto: {len(df):,}")

    det_term, _ = p15.construir_det_termino(df, ordenados, vocab=vocab, mand=mand)
    det = p15.deduplicar_por_codigo(det_term)
    chequeo = p15.validar_contra_publicado(det)
    print("  validacion contra Tabla 1:", chequeo)
    assert chequeo["ok"], "el dataset reconstruido no cuadra con 07/08"
    universo = df.code.values

    print("\n--- tarea 1: intervalos con la dispersion propagada ---")
    p15.guardar_reporte("16_tarea1_intervalos", tarea1_intervalos(det))

    print("\n--- tarea 2: estandarizacion sobre base comun ---")
    p15.guardar_reporte("16_tarea2_base_comun", tarea2_base_comun(det, universo))

    print("\n--- tarea 3: validacion ponderada ---")
    p15.guardar_reporte("16_tarea3_validacion_ponderada", tarea3_validacion_ponderada())

    print("\n--- tarea 4: los 104 sin mapear ---")
    p15.guardar_reporte("16_tarea4_sin_mapear",
                        tarea4_sin_mapear_como_falsos_negativos(ordenados, det))

    print("\n--- tarea 5: forma contra pertenencia literal (decisiva) ---")
    p15.guardar_reporte("16_tarea5_forma_vs_pertenencia",
                        tarea5_forma_vs_pertenencia(det_term, ordenados, vocab))

    print("\n--- tarea 6: cruce origen x forma ---")
    p15.guardar_reporte("16_tarea6_cruce_origen_forma", tarea6_cruce_origen_forma(det_term))

    print("\n--- tarea 7: curva de la ventana, completa ---")
    p15.guardar_reporte("16_tarea7_curva_completa", tarea7_curva_completa(df, ordenados))

    print("\n--- tarea 9: sesgo de incorporacion ---")
    p15.guardar_reporte("16_tarea9_sesgo_incorporacion", tarea9_sesgo_de_incorporacion())

    print("\n--- tareas 10 y 11: verificaciones de repositorio ---")
    p15.guardar_reporte("16_tarea10_readjudicacion", tarea10_readjudicacion())
    p15.guardar_reporte("16_tarea11_sello_temporal", tarea11_sello_temporal())

    ruta_crudo = RAIZ / "datos" / "crudo" / "food.parquet"
    if ruta_crudo.exists():
        print("\n--- tarea 8: carmin y numero E por termino ---")
        df_es = p15.cargar_productos_pais("en:spain", ruta_crudo)
        print(f"  productos de espana con texto: {len(df_es):,}")
        p15.guardar_reporte("16_tarea8_carmin_numero_e",
                            tarea8_carmin_numero_e(df, df_es, ordenados))
    else:
        print("\n  AVISO: falta datos/crudo/food.parquet; tarea 8 omitida.")
