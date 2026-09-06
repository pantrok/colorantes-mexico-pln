"""Paso 8 v2 — mecanismos de la brecha. REEMPLAZA la version anterior.

Cambios respecto a la v1 del 25 de agosto, todos por errores encontrados al
revisar sus propias salidas:

  BUG 1 (grave). La v1 agrupaba por el bloque del YAML, y en `naturales` viven
  E170 carbonato de calcio, E171 dioxido de titanio y E172 oxidos de hierro, que
  son pigmentos inorganicos. La clase "naturales" del modelo incluia al dioxido
  de titanio, cuya brecha es 21.7 % — es decir, contaminaba la clase natural
  hacia abajo. Ahora hay cuatro clases explicitas y separadas:
      sintetico · natural_botanico · carmin · mineral_inorganico

  BUG 2 (grave). M3 nunca se probo. Se comparaba `codigo in vitaminas_tags`,
  pero esas taxonomias guardan NOMBRES (`en:riboflavin`), no codigos E. La
  comparacion no podia dar nunca, y por eso salio 0. Ahora se leen las
  taxonomias de vitaminas y minerales y se construye el mapa codigo -> entrada.
  CORRECCION ADICIONAL (revision de este mismo parche antes de correrlo): el
  codigo E de una entrada de vitamins.txt/minerals.txt casi nunca vive en su
  linea "en:" (que trae el nombre, ej. "riboflavin, vitamin B2") sino en la
  linea "xx:" de sinonimos independientes de idioma. Sin leer tambien "xx:"
  el mapa salia vacio y E101 seguia sin recuperarse -el mismo bug otra vez,
  solo que mas dificil de ver-. Ya corregido en leer_taxonomia().
  E170 (carbonato de calcio) es un caso aparte: su referencia cruzada al
  aditivo esta literalmente COMENTADA en minerals.txt (`#en:E170(i)`), con
  una nota del propio Open Food Facts de que es una entrada duplicada sin
  resolver entre sus dos taxonomias. Ningun parser puede recuperar eso de los
  datos tal como estan: si M3 sigue dando 0 para E170, es un hallazgo sobre
  la fuente, no un bug de este script.

  BUG 3 (menor). `variantes()` probaba sufijos i/ii/iii/iv pero no a/b/c/d, asi
  que E150a-d nunca encontraban su entrada en la taxonomia.

  BUG 4 (conceptual). Un termino puede no estar cubierto por dos razones muy
  distintas: la sustancia SI existe en la taxonomia pero le falta ese sinonimo,
  o la sustancia NO existe en la taxonomia (caso de la espirulina, cero
  entradas). Son cosas distintas y ahora se distinguen: `sin_sinonimo` frente a
  `sin_entrada`. Meterlas juntas confunde "vocabulario incompleto" con
  "sustancia fuera de alcance".

Ademas ajusta el modelo logistico dentro del script, para que la tabla de
razones de momios salga de la tuberia y no de un calculo aparte.

CAMBIO (parche 6, 27/08): el ajuste ya no es el Newton-Raphson propio de este
script. Ese metodo dejo el termino `mandatory` en separacion perfecta (las
celdas de natural_botanico con mandatory=1 tienen brecha exactamente 100 %:
n=63 y n=11) y devolvia un "OR" y un IC de Wald sin sentido bajo esa
condicion. Ahora usa `modelo.firth()` (penalizacion de Firth, IC de
verosimilitud perfilada), compartido con `09_replica_pais.py`, para que las
dos corridas usen el mismo metodo y el termino separado salga finito y
defendible en vez de descartado.

Y genera `08_revision_dra.csv`, la hoja de trabajo para la revision manual.

REQUISITOS
  datos/externo/additives.txt   (ver datos/externo/LEEME.md)
  datos/externo/vitamins.txt
  datos/externo/minerals.txt

Salidas: reportes/08_vocabulario_off.json
         08_cobertura_terminos.csv
         08_mecanismos.csv
         08_modelo.csv
         08_revision_dra.csv    <- para la Dra. Granados-Balbuena
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

from modelo import firth, separacion
from util import (INTERMEDIO, REPORTES, REQUIEREN_CONTEXTO, cargar_diccionario,
                  como_lista, normalizar, quitar_advertencia_trazas,
                  terminos_ordenados, guardar_reporte)

RAIZ = Path(__file__).resolve().parents[1]
EXTERNO = RAIZ / "datos" / "externo"
AMBIGUOS = REQUIEREN_CONTEXTO
RE_CONTEXTO = re.compile(r"colorante|color(?:es)?\b|pigmento")
VENTANA = 60

CARMIN = "E120"
# Pigmentos inorganicos. No son naturales botanicos ni azoicos sinteticos: no
# pertenecen al eje de sustitucion y se reportan como clase propia.
# PENDIENTE DE VEREDICTO de la Dra. Granados-Balbuena.
MINERALES = {"E170", "E171", "E172"}


def norma(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def variantes(codigo: str) -> list[str]:
    k = norma(codigo).replace(" ", "")
    sufijos = ("i", "ii", "iii", "iv", "v", "vi", "a", "b", "c", "d", "e", "f")
    return [k] + [k + s for s in sufijos]


def leer_taxonomia(ruta: Path, obligatoria: bool = True):
    """{codigo: set(terminos es)}, {codigo: bool mandatory}, {codigo: id en:...}"""
    if not ruta.exists():
        if obligatoria:
            raise SystemExit(f"Falta {ruta}. Ver datos/externo/LEEME.md")
        print(f"  AVISO: falta {ruta.name}; el mecanismo que depende de el no se evalua.")
        return {}, {}, {}
    vocab, mand, ident = {}, {}, {}
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        m_en = re.search(r"^en:\s*(.+)$", bloque, re.M)
        if not m_en:
            continue
        primero = m_en.group(1).split(",")[0].strip()
        cod = norma(primero).replace(" ", "").replace("(", "").replace(")", "")
        m_es = re.search(r"^es:\s*(.+)$", bloque, re.M)
        if m_es:
            vocab[cod] = {norma(x) for x in m_es.group(1).split(",")}
        mand[cod] = "mandatory_additive_class" in bloque
        ident[cod] = "EN:" + norma(primero).upper()
        # Sinonimos que sirven para mapear codigo E -> id de vitamina/mineral.
        # OJO: en vitamins.txt/minerals.txt el codigo E casi nunca vive en la
        # linea "en:" (esa trae el nombre, p.ej. "riboflavin, vitamin B2"): vive
        # en la linea "xx:", el bloque de sinonimos independientes de idioma
        # (p.ej. "xx: riboflavin, vitamin B2, B2 vitamin, E101, B2"). Sin leer
        # tambien "xx:" el mapa sale vacio y M3 no recupera nada, que es
        # exactamente el bug que este parche dice corregir. Verificado contra
        # el vitamins.txt real: 0 codigos E encontrados solo con "en:", 1 con
        # "en:"+"xx:" (incluye E101).
        m_xx = re.search(r"^xx:\s*(.+)$", bloque, re.M)
        fuentes = m_en.group(1).split(",")
        if m_xx:
            fuentes += m_xx.group(1).split(",")
        for x in fuentes:
            k = norma(x).replace(" ", "")
            if re.match(r"^e\d{3}", k):
                ident[k] = "EN:" + norma(primero).upper()
    return vocab, mand, ident


def detectar_con_termino(texto: str, ordenados):
    restante, salida = texto, []
    for termino, codigo, bloque in ordenados:
        if not termino:
            continue
        pat = re.compile(r"\b" + re.escape(termino) + r"\b")
        if pat.search(restante):
            salida.append((codigo, bloque, termino))
            restante = pat.sub(" ", restante)
    return salida


def con_contexto(texto: str, termino: str) -> bool:
    pat = re.compile(r"\b" + re.escape(termino) + r"\b")
    for m in pat.finditer(texto):
        ini, fin = max(0, m.start() - VENTANA), min(len(texto), m.end() + VENTANA)
        if RE_CONTEXTO.search(texto[ini:fin]):
            return True
    return False


def clase_de(codigo: str, bloque: str) -> str:
    if codigo == CARMIN:
        return "carmin"
    if codigo in MINERALES:
        return "mineral_inorganico"
    if bloque == "sinteticos":
        return "sintetico"
    if bloque == "naturales":
        return "natural_botanico"
    return "fuera_de_eje"


def main() -> None:
    vocab, mand, _ = leer_taxonomia(EXTERNO / "additives.txt")
    _, _, id_vit = leer_taxonomia(EXTERNO / "vitamins.txt", obligatoria=False)
    _, _, id_min = leer_taxonomia(EXTERNO / "minerals.txt", obligatoria=False)
    id_otros = {**id_vit, **id_min}          # codigo E normalizado -> "EN:NOMBRE"

    dic = cargar_diccionario()
    ordenados = terminos_ordenados(dic)

    # ---------------------------------------------------- M1 a nivel diccionario
    filas = []
    for termino, codigo, bloque in ordenados:
        vs, es_mand, tiene_entrada = set(), False, False
        for k in variantes(codigo):
            if k in vocab:
                tiene_entrada = True
                vs |= vocab[k]
            es_mand = es_mand or mand.get(k, False)
        t = norma(termino)
        cubierto = t in vs
        filas.append({
            "codigo": codigo, "clase": clase_de(codigo, bloque), "termino": termino,
            "en_vocabulario_off": cubierto,
            "motivo_no_cubierto": ("" if cubierto else
                                   ("sin_entrada" if not tiene_entrada else "sin_sinonimo")),
            "off_mandatory_class": es_mand,
            "n_terminos_off_es": len(vs),
        })
    cob = pd.DataFrame(filas)

    # -------------------------------------------------------- lectura de datos
    cols = duckdb.sql(f"SELECT * FROM '{INTERMEDIO/'productos_mx.parquet'}' LIMIT 1").df().columns.tolist()
    extra = [c for c in ("vitaminas_tags", "vitamins_tags",
                         "minerales_tags", "minerals_tags") if c in cols]
    sel = "code, ingredientes_texto, aditivos_tags" + ("," + ",".join(extra) if extra else "")
    df = duckdb.sql(f"""
        SELECT {sel} FROM '{INTERMEDIO/'productos_mx.parquet'}'
        WHERE ingredientes_texto IS NOT NULL AND length(trim(ingredientes_texto)) > 0
    """).df()

    idx = {(r.codigo, norma(r.termino)): r for r in cob.itertuples()}
    pares, textos_rotos = [], []
    for t in df.itertuples(index=False):
        texto = normalizar(t.ingredientes_texto)
        # CORREGIDO parche 14: un colorante mencionado solo dentro de una
        # advertencia de trazas no cuenta como deteccion. Ver
        # util.py::quitar_advertencia_trazas y BITACORA_PARCHES.md.
        texto_det, roto = quitar_advertencia_trazas(texto)
        if roto:
            textos_rotos.append(t.code)
        tags_add = {str(a).replace("en:", "").upper() for a in como_lista(t.aditivos_tags)}
        tags_otro = set()
        for c in extra:
            tags_otro |= {"EN:" + str(a).replace("en:", "").upper()
                          for a in como_lista(getattr(t, c))}
        # Agrupar por codigo ANTES de decidir si cuenta. CORREGIDO 05/09: un
        # producto puede declarar el mismo colorante con mas de un sinonimo
        # (p.ej. "achiote" y "annatto", ambos E160b); eso es UNA deteccion de
        # ese codigo, no dos -antes cada termino generaba su propia fila en
        # `pares` y n/sin_tag salian inflados-. Si aparece por mas de un
        # termino, basta que UNO pase el contexto, y en_vocab_off/
        # off_mandatory se evaluan por cualquiera de los terminos usados
        # (OR): importa si el producto es recuperable por alguna de las
        # formas que declaro, no por una especifica. Ver BITACORA_PARCHES.md.
        por_codigo = {}
        for codigo, bloque, termino in detectar_con_termino(texto_det, ordenados):
            cl = clase_de(codigo, bloque)
            if cl == "fuera_de_eje":
                continue
            entry = por_codigo.setdefault(codigo, {
                "clase": cl, "termino": termino, "contexto_ok": False,
                "en_vocab_off": False, "off_mandatory": False})
            if codigo not in AMBIGUOS or con_contexto(texto_det, termino):
                entry["contexto_ok"] = True
            meta = idx.get((codigo, norma(termino)))
            if meta:
                entry["en_vocab_off"] = entry["en_vocab_off"] or bool(meta.en_vocabulario_off)
                entry["off_mandatory"] = entry["off_mandatory"] or bool(meta.off_mandatory_class)

        for codigo, info in por_codigo.items():
            if not info["contexto_ok"]:
                continue
            # M3: el codigo puede vivir en vitamins/minerals bajo su NOMBRE
            ids = {id_otros.get(k) for k in variantes(codigo)} - {None}
            pares.append({
                "code": t.code, "codigo": codigo, "clase": info["clase"],
                "termino": info["termino"],
                "en_vocab_off": info["en_vocab_off"],
                "off_mandatory": info["off_mandatory"],
                "en_additives_tags": codigo in tags_add,
                "en_otras_taxonomias": bool(ids & tags_otro),
            })
    p = pd.DataFrame(pares)
    if p.empty:
        raise SystemExit("Cero detecciones depuradas.")
    p["visible"] = p.en_additives_tags | p.en_otras_taxonomias

    # ------------------------------------------------------------- mecanismos
    mec = (p.groupby(["clase", "en_vocab_off", "off_mandatory"])
             .agg(n=("visible", "size"),
                  sin_tag=("en_additives_tags", lambda s: int((~s).sum())),
                  sin_ninguna=("visible", lambda s: int((~s).sum())))
             .reset_index())
    mec["brecha_pct"] = (100 * mec.sin_tag / mec.n).round(1)
    mec["brecha_pct_con_otras_taxonomias"] = (100 * mec.sin_ninguna / mec.n).round(1)

    # ---------------------------------------------------------- modelo logistico
    # Solo sintetico y natural_botanico: carmin y minerales van aparte por diseno.
    m = mec[mec.clase.isin(["sintetico", "natural_botanico"])].copy()
    m["natural"] = (m.clase == "natural_botanico").astype(int)
    m["fuera_vocab"] = (~m.en_vocab_off).astype(int)
    m["mandatory"] = m.off_mandatory.astype(int)
    modelo = pd.DataFrame()
    metodo = None
    avisos_separacion = []
    if len(m) >= 4 and m.natural.nunique() > 1 and m.fuera_vocab.nunique() > 1:
        modelo = firth(m[["natural", "fuera_vocab", "mandatory"]],
                       m.sin_tag.values, m.n.values)
        metodo = modelo.attrs.get("metodo")
        avisos_separacion = separacion(m, "sin_tag", "n",
                                       ["natural", "fuera_vocab", "mandatory"])

    # ------------------------------- estandarizacion: cuanto sobrevive al ajuste
    estand = {}
    sin_m = m[m.natural == 0]
    nat_m = m[m.natural == 1]
    if len(sin_m) and len(nat_m):
        peso = sin_m.set_index(["fuera_vocab", "mandatory"]).n
        tasa = nat_m.set_index(["fuera_vocab", "mandatory"]).apply(
            lambda r: r.sin_tag / r.n, axis=1)
        comunes = peso.index.intersection(tasa.index)
        if len(comunes):
            p_std = float((peso[comunes] * tasa[comunes]).sum() / peso[comunes].sum())
            b_sin = 100 * sin_m.sin_tag.sum() / sin_m.n.sum()
            b_nat = 100 * nat_m.sin_tag.sum() / nat_m.n.sum()
            estand = {
                "brecha_sintetico_pct": round(b_sin, 1),
                "brecha_natural_cruda_pct": round(b_nat, 1),
                "brecha_natural_estandarizada_pct": round(100 * p_std, 1),
                "diferencia_cruda_pp": round(b_nat - b_sin, 1),
                "diferencia_atribuible_al_origen_pp": round(100 * p_std - b_sin, 1),
                "pct_de_la_diferencia_que_es_origen":
                    round(100 * (100 * p_std - b_sin) / (b_nat - b_sin), 1) if b_nat != b_sin else None,
            }

    # ------------------------------------------- hoja de revision para la Dra.
    # OJO: agrupar por CODIGO (no por termino) haria que las variantes de un
    # mismo codigo -curcumina, curcuma, extracto de curcuma, oleorresina de
    # curcuma para E100- compartieran el mismo total prestado, y un termino
    # que nunca aparecio por si solo quedaria con un conteo de sus hermanos
    # en vez de 0. Eso justo rompe la pregunta P1, que solo se responde en
    # los renglones con 0 detecciones.
    peso_term = p.groupby(["codigo", "termino"]).size().rename("detecciones")
    rev = cob.merge(peso_term, on=["codigo", "termino"], how="left")
    rev["detecciones"] = rev.detecciones.fillna(0).astype(int)
    rev = rev.sort_values(["detecciones", "codigo"], ascending=[False, True])
    rev["P1_se_usa_en_etiqueta_mx"] = ""     # si / no / duda
    rev["P2_declara_colorante"] = ""         # si / no / a veces
    rev["P3_codigo_correcto"] = ""           # si / no -> cual
    rev["P4_clase_correcta"] = ""            # si / no -> cual
    rev["comentario"] = ""

    # ------------------------------------------------------------------ salidas
    REPORTES.mkdir(exist_ok=True)
    cob.to_csv(REPORTES / "08_cobertura_terminos.csv", index=False, encoding="utf-8")
    mec.to_csv(REPORTES / "08_mecanismos.csv", index=False, encoding="utf-8")
    if len(modelo):
        modelo.to_csv(REPORTES / "08_modelo.csv", index=False, encoding="utf-8")
    rev.to_csv(REPORTES / "08_revision_dra.csv", index=False, encoding="utf-8")

    resumen = {
        "taxonomias": {
            "additives_entradas_es": len(vocab),
            "additives_mandatory": int(sum(mand.values())),
            "vitamins_disponible": bool(id_vit),
            "minerals_disponible": bool(id_min),
        },
        "M1_cobertura": {
            "terminos": len(cob),
            "cubiertos": int(cob.en_vocabulario_off.sum()),
            "sin_sinonimo": int((cob.motivo_no_cubierto == "sin_sinonimo").sum()),
            "sin_entrada": int((cob.motivo_no_cubierto == "sin_entrada").sum()),
            "por_clase": cob.groupby("clase").en_vocabulario_off
                            .agg(["size", "sum"]).to_dict("index"),
        },
        "M2_mandatory": sorted({r.codigo for r in cob.itertuples() if r.off_mandatory_class}),
        "M3_otras_taxonomias": {
            "columnas": extra,
            "recuperadas": int(p.en_otras_taxonomias.sum()),
            "por_codigo": p[p.en_otras_taxonomias].groupby("codigo").size().to_dict(),
        },
        "brecha_global_pct": round(100 * float((~p.en_additives_tags).mean()), 1),
        "brecha_global_con_otras_taxonomias_pct": round(100 * float((~p.visible).mean()), 1),
        "mecanismos": mec.to_dict("records"),
        "modelo_firth": modelo.to_dict("records") if len(modelo) else None,
        "modelo_metodo": metodo,
        "separacion_detectada": avisos_separacion,
        "estandarizacion": estand,
        "PENDIENTE": ("MINERALES = {E170, E171, E172} se sacaron del eje por decision "
                      "propia. Requiere veredicto de la Dra. antes de fijarse."),
        "textos_rotos_advertencia": {"n": len(textos_rotos), "codigos": textos_rotos},
    }
    guardar_reporte("08_vocabulario_off", resumen)

    print(f"  cobertura: {int(cob.en_vocabulario_off.sum())}/{len(cob)} terminos")
    print(f"  sin sinonimo: {resumen['M1_cobertura']['sin_sinonimo']}   "
          f"sin entrada en la taxonomia: {resumen['M1_cobertura']['sin_entrada']}")
    print(f"  M3 recuperadas: {resumen['M3_otras_taxonomias']['recuperadas']}  "
          f"{resumen['M3_otras_taxonomias']['por_codigo']}")
    print(f"  brecha global {resumen['brecha_global_pct']} %  ->  "
          f"{resumen['brecha_global_con_otras_taxonomias_pct']} % contando vit/min")
    print("\n", mec.to_string(index=False))
    if len(modelo):
        print(f"\n  modelo ({metodo}):\n", modelo.to_string(index=False))
    if avisos_separacion:
        print("\n  separacion detectada:", avisos_separacion)
    if estand:
        print("\n  estandarizacion:", estand)


if __name__ == "__main__":
    main()
