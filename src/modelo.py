"""Regresion logistica penalizada de Firth, para datos binomiales agrupados.

POR QUE HACE FALTA (27 de agosto de 2026). Al separar los pigmentos inorganicos
de la clase natural, el termino `mandatory` dejo de ser estimable: TODAS las
celdas de natural botanico sujetas a `mandatory_additive_class` tienen brecha de
100 % (n=63 y n=11). Eso es separacion perfecta. La maxima verosimilitud ordinaria
manda el coeficiente a infinito, el error estandar tambien, y el intervalo de
Wald deja de significar nada — que es justo lo que devolvio el modelo: NaN.

La correccion de Firth (1993) penaliza la verosimilitud con el jacobiano de
Jeffreys, l*(b) = l(b) + 0.5 * log det I(b). Da estimaciones finitas bajo
separacion y con sesgo reducido. Es el procedimiento estandar para este caso y
un arbitro con formacion metodologica lo espera; presentar un NaN o, peor, quitar
la variable sin decirlo, no pasa revision.

Los intervalos son de VEROSIMILITUD PERFILADA, no de Wald. Bajo separacion los
de Wald son inservibles aunque el punto sea finito: quedan absurdamente anchos y
simetricos en la escala equivocada.

Referencia: Firth, D. (1993). Bias reduction of maximum likelihood estimates.
Biometrika, 80(1), 27-38. Heinze & Schemper (2002) para el caso de separacion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CHI2_95 = 3.841459


def _ajuste(X: np.ndarray, y: np.ndarray, n: np.ndarray,
            fijo: np.ndarray | None = None, max_iter: int = 200):
    """Newton-Raphson sobre la verosimilitud penalizada de Firth.

    `fijo` permite dejar coeficientes clavados (para el perfil): es un vector de
    NaN salvo en las posiciones fijadas.
    """
    k = X.shape[1]
    beta = np.zeros(k)
    if fijo is not None:
        beta = np.where(np.isnan(fijo), 0.0, fijo)
    libres = np.ones(k, dtype=bool) if fijo is None else np.isnan(fijo)

    for _ in range(max_iter):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(eta, -500, 500)))
        W = n * p * (1 - p)
        W = np.maximum(W, 1e-12)
        raizW = np.sqrt(W)
        Xw = X * raizW[:, None]
        I = Xw.T @ Xw
        try:
            Iinv = np.linalg.inv(I)
        except np.linalg.LinAlgError:
            Iinv = np.linalg.pinv(I)
        # diagonal del sombrero
        h = np.einsum("ij,jk,ik->i", Xw, Iinv, Xw)
        # score modificado de Firth
        U = X.T @ (y - n * p + h * (0.5 - p))
        if not libres.any():
            break
        paso = np.zeros(k)
        try:
            paso[libres] = np.linalg.solve(I[np.ix_(libres, libres)], U[libres])
        except np.linalg.LinAlgError:
            paso[libres] = np.linalg.pinv(I[np.ix_(libres, libres)]) @ U[libres]
        # amortiguamiento: evita divergencia en las primeras iteraciones
        norma = np.max(np.abs(paso))
        if norma > 5:
            paso *= 5 / norma
        beta = beta + paso
        if norma < 1e-10:
            break

    eta = X @ beta
    p = 1.0 / (1.0 + np.exp(-np.clip(eta, -500, 500)))
    W = np.maximum(n * p * (1 - p), 1e-12)
    Xw = X * np.sqrt(W)[:, None]
    I = Xw.T @ Xw
    signo, logdet = np.linalg.slogdet(I)
    with np.errstate(divide="ignore", invalid="ignore"):
        ll = np.nansum(y * np.log(np.clip(p, 1e-300, 1)) +
                       (n - y) * np.log(np.clip(1 - p, 1e-300, 1)))
    ll_pen = ll + 0.5 * (logdet if signo > 0 else -np.inf)
    return beta, ll_pen, I


def _perfil(X, y, n, j, valor, ll_max):
    fijo = np.full(X.shape[1], np.nan)
    fijo[j] = valor
    _, ll, _ = _ajuste(X, y, n, fijo=fijo)
    return 2 * (ll_max - ll) - CHI2_95


def firth(X: pd.DataFrame, exitos, totales, con_intercepto: bool = True):
    """Devuelve una tabla con OR e IC95 de verosimilitud perfilada.

    exitos  = veces que ocurrio el desenlace en cada celda
    totales = tamano de cada celda
    """
    Xm = X.values.astype(float)
    nombres = list(X.columns)
    if con_intercepto:
        Xm = np.column_stack([np.ones(len(X)), Xm])
        nombres = ["intercepto"] + nombres
    y = np.asarray(exitos, dtype=float)
    n = np.asarray(totales, dtype=float)

    beta, ll_max, _ = _ajuste(Xm, y, n)

    filas = []
    for j, nombre in enumerate(nombres):
        lo = hi = np.nan
        # busca hacia abajo y hacia arriba el punto donde cae la verosimilitud
        for signo, destino in ((-1, "lo"), (1, "hi")):
            a = beta[j]
            b = beta[j] + signo * 0.5
            for _ in range(60):
                if _perfil(Xm, y, n, j, b, ll_max) > 0:
                    break
                a, b = b, b + signo * 0.5
                if abs(b - beta[j]) > 40:
                    break
            else:
                continue
            if _perfil(Xm, y, n, j, b, ll_max) <= 0:
                continue                       # no se pudo acotar
            for _ in range(80):                # biseccion
                m = (a + b) / 2
                if _perfil(Xm, y, n, j, m, ll_max) > 0:
                    b = m
                else:
                    a = m
            if destino == "lo":
                lo = b
            else:
                hi = b
        filas.append({
            "termino": nombre,
            "coef": round(float(beta[j]), 4),
            "OR": round(float(np.exp(beta[j])), 2),
            "IC_bajo": round(float(np.exp(lo)), 2) if np.isfinite(lo) else None,
            "IC_alto": round(float(np.exp(hi)), 2) if np.isfinite(hi) else None,
        })
    tabla = pd.DataFrame(filas)
    tabla.attrs["ll_penalizada"] = float(ll_max)
    tabla.attrs["metodo"] = ("Firth penalizada; IC de verosimilitud perfilada al 95 %")
    return tabla


def separacion(celdas: pd.DataFrame, col_exitos: str, col_n: str,
               por: list[str]) -> list[dict]:
    """Detecta separacion: grupos donde el desenlace es 0 % o 100 % en todas sus
    celdas. Sirve para DECLARARLO en el manuscrito, no solo para corregirlo."""
    avisos = []
    for var in por:
        for valor, g in celdas.groupby(var):
            tasa = g[col_exitos].sum() / g[col_n].sum()
            if tasa in (0.0, 1.0):
                avisos.append({"variable": var, "valor": valor,
                               "tasa": tasa, "n": int(g[col_n].sum()),
                               "nota": "separacion perfecta"})
    return avisos
