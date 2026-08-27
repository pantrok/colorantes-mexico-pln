"""Paso 10 — EL VOCABULARIO OFICIAL CONTRA EL DE OPEN FOOD FACTS.

Es la version del hallazgo que ya no depende de nosotros.

Hasta el paso 8, la comparacion era: NUESTRO diccionario contra la taxonomia de
Open Food Facts. La objecion evidente es que los terminos los pusimos nosotros y
podriamos haber inventado formas que nadie imprime. Ese reproche mata el
resultado y no habia como contestarlo.

Con `config/acuerdo_colorantes.yaml` la comparacion pasa a ser: el vocabulario
LEGALMENTE OBLIGATORIO en Mexico contra la taxonomia de Open Food Facts. El
articulo DECIMOSEGUNDO del Acuerdo obliga a declarar cada aditivo «con el nombre
comun o, en su defecto, con alguno de los sinonimos enumerados en el presente
Acuerdo». Cualquiera de esas formas es una declaracion valida en etiqueta. No
las elegimos nosotros.

Tres bloques:

  A. COBERTURA. De las formas oficiales mexicanas, cuantas existen en el
     vocabulario espanol de Open Food Facts. Por clase de origen.

  B. NUESTRO DICCIONARIO CONTRA LA LEY. Que formas oficiales nos faltan (falsos
     negativos garantizados) y que terminos nuestros no estan en la ley (que no
     los invalida —la ley da nombres, el mercado usa variantes— pero hay que
     saber cuales son y justificarlos).

  C. RECUENTO SOBRE LOS DATOS. Cuantos productos del subconjunto mexicano
     contienen alguna forma oficial que nuestro diccionario NO tiene. Es la
     medida directa de lo que estamos perdiendo hoy.

El hallazgo que sostiene el articulo esta en el bloque A, y en particular en el
beta caroteno: la ley mexicana SEPARA 160a(i) sintetico de 160a(ii) natural, con
codigos y numeros CI distintos y nombres distintos. El Codex los agrupa, el
agrupamiento de Zancheta et al. (2025) los fusiona, la regulacion de Hong Kong
define el sintetico como natural, y Open Food Facts tiene una sola entrada.
Mexico es la unica jurisdiccion del cotejo que conserva el eje de origen, y la
base internacional no puede representarlo.

Salidas: reportes/10_acuerdo_vs_off.json
         10_cobertura_oficial.csv     forma oficial x presencia en OFF y en el nuestro
         10_faltantes_diccionario.csv formas legales que no reconocemos
         10_hallazgos_en_datos.csv    productos que las contienen
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from util import (INTERMEDIO, REPORTES, cargar_diccionario, como_lista,
                  normalizar, terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
EXTERNO = RAIZ / "datos" / "externo"
ACUERDO = RAIZ / "config" / "acuerdo_colorantes.yaml"


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip(" .,;:")


def variantes(codigo: str) -> list[str]:
    k = norma(codigo).replace(" ", "")
    return [k] + [k + s for s in ("i", "ii", "iii", "iv", "v", "vi",
                                  "a", "b", "c", "d", "e", "f")]


CARMIN = "E120"
MINERALES = {"E170", "E171", "E172"}


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral_inorganico"
    return {"sinteticos": "sintetico", "naturales": "natural_botanico"}.get(
        bloque, "fuera_de_eje")


def ya_cubierta(forma_norm: str, nuestros: set[str]) -> str | None:
    """Devuelve el termino nuestro que ya captura esa forma, si existe.

    El emparejador reconoce por subcadena, asi que un termino nuestro
    contenido en la forma oficial ya la captura y no es falso negativo.
    """
    candidatos = [t for t in nuestros if t in forma_norm and len(t) >= 4]
    return max(candidatos, key=len) if candidatos else None


def leer_taxonomia_off(ruta: Path):
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}. Ver datos/externo/LEEME.md")
    vocab, todos = {}, set()
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        m_en = re.search(r"^en:\s*(.+)$", bloque, re.M)
        if not m_en:
            continue
        cod = norma(m_en.group(1).split(",")[0]).replace(" ", "") \
               .replace("(", "").replace(")", "")
        m_es = re.search(r"^es:\s*(.+)$", bloque, re.M)
        if m_es:
            vocab[cod] = {norma(x) for x in m_es.group(1).split(",")}
            todos |= vocab[cod]
    return vocab, todos


def main() -> None:
    if not ACUERDO.exists():
        raise SystemExit(f"Falta {ACUERDO}. Viene en este mismo parche.")
    ac = yaml.safe_load(ACUERDO.read_text(encoding="utf-8"))
    oficial = ac["colorantes"]
    vocab_off, todos_off = leer_taxonomia_off(EXTERNO / "additives.txt")

    dic = cargar_diccionario()
    ordenados_propios = terminos_ordenados(dic)
    nuestros = {norma(t) for t, _, _ in ordenados_propios}
    # A que clase pertenece cada termino nuestro, para poder distinguir
    # "ya cubierta" (el termino que la captura es de la misma clase legal)
    # de "mal clasificada" (la captura, pero bajo la clase equivocada -el
    # caso del beta caroteno sintetico contandose como natural-).
    nuestros_clase = {norma(t): clase_de(cod, bloque) for t, cod, bloque in ordenados_propios}

    # ------------------------------------------------------------- bloque A y B
    filas = []
    for sin, info in oficial.items():
        e = info.get("e")
        vs = set()
        if e:
            for k in variantes(e):
                vs |= vocab_off.get(k, set())
        for termino in info["terminos"]:
            t = norma(termino)
            filas.append({
                "sin": sin, "codigo_e": e, "clase": info["clase"],
                "forma_oficial": termino,
                "en_off_bajo_su_codigo": t in vs,
                "en_off_en_cualquier_entrada": t in todos_off,
                "en_nuestro_diccionario": t in nuestros,
                "n_formas_off_para_ese_codigo": len(vs),
                "nota": info.get("nota", "") or info.get("CLAVE", "")
                        or info.get("TRAMPA", "") or info.get("AMBIGUO", ""),
            })
    cob = pd.DataFrame(filas)

    def resumen(sub):
        n = len(sub)
        return {"formas": n,
                "en_off": int(sub.en_off_bajo_su_codigo.sum()),
                "pct_en_off": round(100 * sub.en_off_bajo_su_codigo.mean(), 1) if n else None,
                "en_nuestro": int(sub.en_nuestro_diccionario.sum()),
                "pct_en_nuestro": round(100 * sub.en_nuestro_diccionario.mean(), 1) if n else None}

    por_clase = {cl: resumen(g) for cl, g in cob.groupby("clase")}
    global_ = resumen(cob)

    faltan = cob[~cob.en_nuestro_diccionario].copy()

    # Clasificacion de cada forma legal que NO esta literal en nuestro
    # diccionario, en tres categorias -no una sola, que es el defecto de
    # diseno que este parche corrige-:
    #   ya_cubierta        un termino nuestro mas corto ya la reconoce, y
    #                      con la misma clase que le da la ley: no es una
    #                      brecha real, es coincidencia de subcadena.
    #   mal_clasificada    un termino nuestro mas corto ya la reconoce, pero
    #                      bajo una clase distinta a la legal -aqui vive el
    #                      beta caroteno sintetico contandose como natural-.
    #   falso_negativo_real  ningun termino nuestro la cubre: brecha real.
    def clasificar(row) -> tuple[str, str]:
        cobertura = ya_cubierta(norma(row.forma_oficial), nuestros)
        if cobertura is None:
            return "falso_negativo_real", ""
        clase_cobertura = nuestros_clase.get(cobertura, "?")
        cat = "ya_cubierta" if clase_cobertura == row.clase else "mal_clasificada"
        return cat, cobertura

    faltan[["categoria", "cubierta_por"]] = faltan.apply(
        lambda r: pd.Series(clasificar(r)), axis=1)

    # ------------------------------------------------------ bloque C: los datos
    ruta = INTERMEDIO / "productos_mx.parquet"
    hallazgos = pd.DataFrame()
    conteo = {}
    if ruta.exists():
        df = duckdb.sql(f"""
            SELECT code, nombre_producto, ingredientes_texto, aditivos_tags
            FROM '{ruta}'
            WHERE ingredientes_texto IS NOT NULL
              AND length(trim(ingredientes_texto)) > 0
        """).df()
        # Solo se busca en el texto lo que de verdad hace falta buscar:
        # falso_negativo_real (no lo capturamos de ningun modo) y
        # mal_clasificada (lo capturamos, pero con la clase equivocada).
        # ya_cubierta ya la encuentra el termino corto bajo la clase
        # correcta; volver a buscarla duplicaria la cuenta.
        objetivo = faltan[faltan.categoria != "ya_cubierta"]
        buscar = [(r.forma_oficial, norma(r.forma_oficial), r.sin, r.codigo_e,
                   r.clase, r.categoria)
                  for r in objetivo.itertuples() if len(norma(r.forma_oficial)) >= 5]
        pat = {t: re.compile(r"\b" + re.escape(t) + r"\b") for _, t, _, _, _, _ in buscar}
        enc = []
        for row in df.itertuples(index=False):
            texto = normalizar(row.ingredientes_texto)
            tags = {str(a).replace("en:", "").upper()
                    for a in como_lista(row.aditivos_tags)}
            for orig, t, sin, e, cl, cat in buscar:
                if pat[t].search(texto):
                    enc.append({"code": row.code, "producto": row.nombre_producto,
                                "forma_oficial": orig, "sin": sin, "codigo_e": e,
                                "clase": cl, "categoria": cat,
                                "ya_en_tags": bool(e and e in tags)})
        hallazgos = pd.DataFrame(enc)
        resumen_categorias = faltan.categoria.value_counts().to_dict()
        if len(hallazgos):
            conteo = {
                "formas_por_categoria": resumen_categorias,
                "productos_afectados": int(hallazgos.code.nunique()),
                "detecciones_nuevas": int(len(hallazgos)),
                "pct_del_subconjunto": round(100 * hallazgos.code.nunique() / len(df), 2),
                "por_categoria": {
                    cat: {"productos": int(g.code.nunique()), "detecciones": int(len(g))}
                    for cat, g in hallazgos.groupby("categoria")
                },
                "por_forma": hallazgos.groupby("forma_oficial").size()
                                      .sort_values(ascending=False).head(25).to_dict(),
                "por_clase": hallazgos.groupby("clase").code.nunique().to_dict(),
                "ya_estaban_en_tags": int(hallazgos.ya_en_tags.sum()),
            }
        else:
            conteo = {"formas_por_categoria": resumen_categorias}

    # ------------------------------------------------------------------ salidas
    REPORTES.mkdir(exist_ok=True)
    cob.to_csv(REPORTES / "10_cobertura_oficial.csv", index=False, encoding="utf-8")
    faltan.to_csv(REPORTES / "10_faltantes_diccionario.csv", index=False, encoding="utf-8")
    if len(hallazgos):
        hallazgos.to_csv(REPORTES / "10_hallazgos_en_datos.csv", index=False, encoding="utf-8")

    caroteno = cob[cob.sin.str.startswith("SIN160a")][
        ["sin", "clase", "forma_oficial", "en_off_bajo_su_codigo", "en_nuestro_diccionario"]]

    guardar_reporte("10_acuerdo_vs_off", {
        "fuente_oficial": ac["meta"],
        "n_codigos_sin": len(oficial),
        "n_formas_oficiales": len(cob),
        "cobertura_global": global_,
        "cobertura_por_clase": por_clase,
        "formas_legales_que_no_reconocemos": int(len(faltan)),
        "hallazgos_en_datos": conteo,
        "beta_caroteno": caroteno.to_dict("records"),
        "LECTURA": ("El bloque A ya no depende de nuestro criterio: mide la taxonomia de "
                    "Open Food Facts contra el vocabulario que la ley mexicana obliga a "
                    "usar en etiqueta. El bloque B dice cuanto de esa ley no reconocemos "
                    "todavia nosotros, que es una limitacion propia y hay que declararla."),
    })

    print(f"  formas oficiales: {len(cob)} en {len(oficial)} codigos SIN")
    print(f"  en el vocabulario de OFF: {global_['en_off']} ({global_['pct_en_off']} %)")
    print(f"  en nuestro diccionario:   {global_['en_nuestro']} ({global_['pct_en_nuestro']} %)")
    print("\n  por clase:")
    for cl, r in sorted(por_clase.items()):
        print(f"    {cl:20} {r['formas']:3} formas | OFF {r['pct_en_off']:5} % | "
              f"nuestro {r['pct_en_nuestro']:5} %")
    print("\n  beta caroteno, el caso que sostiene el argumento:")
    print(caroteno.to_string(index=False))
    print(f"\n  formas faltantes por categoria: {conteo.get('formas_por_categoria', {})}")
    if "productos_afectados" in conteo:
        print(f"\n  productos con falso_negativo_real o mal_clasificada: "
              f"{conteo['productos_afectados']} ({conteo['pct_del_subconjunto']} %)")
        print(f"  desglose: {conteo['por_categoria']}")
        for k, v in list(conteo["por_forma"].items())[:12]:
            print(f"    {k:45} {v}")


if __name__ == "__main__":
    main()
