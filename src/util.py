"""Utilidades compartidas: normalizacion de texto y carga del diccionario."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config" / "colorantes.yaml"
REPORTES = RAIZ / "reportes"
INTERMEDIO = RAIZ / "datos" / "intermedio"


def normalizar(texto: str | None) -> str:
    """Minusculas, sin acentos, puntuacion a espacio, espacios colapsados.

    Se aplica igual al texto de la etiqueta y a los terminos del diccionario,
    para que la comparacion sea simetrica.
    """
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^\w\s&.]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def cargar_diccionario() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    for bloque in ("sinteticos", "naturales", "fuera_de_eje"):
        for codigo, info in d.get(bloque, {}).items():
            info["clase"] = bloque
            info["codigo"] = codigo
            info["terminos_norm"] = sorted(
                {normalizar(t) for t in info.get("terminos", [])}, key=len, reverse=True
            )
    d["genericos"]["terminos_norm"] = [normalizar(t) for t in d["genericos"]["terminos"]]
    return d


def construir_matchers(dic: dict) -> list[tuple[str, str, re.Pattern]]:
    """Devuelve (codigo, clase, patron) UNO POR TERMINO, del mas largo al mas corto.

    El orden tiene que ser por termino y no por sustancia. Si se ordenara por
    sustancia, E120 se probaria antes que E124 —porque su termino mas largo,
    'carmin de cochinilla', tiene 20 caracteres frente a los 17 de 'rojo
    cochinilla a'— y entonces el termino corto 'cochinilla' se comeria el texto
    antes de que E124 tuviera oportunidad. Las dos trampas del dominio dependen
    de esto:

      'rojo cochinilla a' -> E124 SINTETICO, no 'cochinilla' -> E120 natural
      'carmin de indigo'  -> E132 SINTETICO, no 'carmin'     -> E120 natural

    Hay una prueba en tests/test_diccionario.py que lo verifica. Si la tocas y
    falla, es que reintrodujiste el error.
    """
    return [(c, b, re.compile(rf"(?<!\w){re.escape(t)}(?!\w)"))
            for t, c, b in terminos_ordenados(dic)]


def terminos_ordenados(dic: dict) -> list[tuple[str, str, str]]:
    """(termino, codigo, clase) del termino mas largo al mas corto. Ver construir_matchers."""
    terminos = [
        (t, codigo, bloque)
        for bloque in ("sinteticos", "naturales", "fuera_de_eje")
        for codigo, info in dic.get(bloque, {}).items()
        for t in info["terminos_norm"] if t
    ]
    terminos.sort(key=lambda x: len(x[0]), reverse=True)
    return terminos


def detectar(texto_norm: str, matchers) -> dict[str, str]:
    """Devuelve {codigo: clase} de los colorantes hallados, consumiendo el texto.

    Consumir es lo que resuelve las trampas: al reconocer 'rojo cochinilla a' se
    borra del texto, de modo que 'cochinilla' ya no puede volver a coincidir.
    """
    hallados, resto = {}, texto_norm
    for codigo, clase, patron in matchers:
        if patron.search(resto):
            hallados[codigo] = clase
            resto = patron.sub(" ", resto)
    return hallados


# Codigos cuyo termino nombra tambien un ingrediente, vitamina, mineral o especia
# de uso NO colorante. Solo cuentan si la palabra "colorante" aparece cerca.
#
# Se declara UNA sola vez y la importan 05 y 06, para que no puedan divergir.
# Cuando se publique el diccionario como material suplementario, esto debe
# migrar a colorantes.yaml como campo `requiere_contexto` de cada entrada.
#
# Historial:
#   v1 (23/08) E100, E101, E140, E160a, E160c, E170, E171
#              Motivo: curcuma-especia, vitamina B2, minerales, carotenos y
#              paprika como ingrediente.
#   v2 (23/08) + E160b, E162, E163
#              Motivo: son trampas especificas del mercado mexicano. El achiote
#              es condimento antes que colorante (recado rojo, cochinita); la
#              jamaica en un agua de jamaica ES la bebida, no la colorea; el
#              betabel aparece como jugo o extracto en calidad de ingrediente.
#              La correccion es del instrumento, no del umbral: se aplica de
#              forma uniforme y se reportan las dos versiones.
#   v3 (01/09) + E172, SPIRULINA, E164 -veredicto de la Dra. Granados-Balbuena,
#              config/decisiones_dra.yaml, codigos_a_agregar-. Oxido de hierro
#              y espirulina se declaran a veces como suplemento, no colorante;
#              azafran es especia antes que colorante y "azafran indio/de
#              indias" (curcuma) ganan primero por ser mas largos.
#              E101 y E170 salieron del diccionario por completo al congelar
#              (fuera del eje: fortificacion y mineral, no color). Se dejan
#              aqui listados porque no estorban -ya no hay termino que mapee a
#              esos codigos- y quitarlos borraria el historial de por que
#              entraron.
REQUIEREN_CONTEXTO = frozenset({
    "E100", "E101", "E140", "E160a", "E160b", "E160c", "E162", "E163",
    "E170", "E171", "E172", "SPIRULINA", "E164",
})


# Marcadores que abren un segmento de ADVERTENCIA DE TRAZAS ("puede contener
# soya, leche, gluten, amarillo 5"), no una declaracion de que el producto
# lleva el colorante. Medidos sobre los 600 textos del conjunto anotado
# (parche 14, 05/09/2026): "puede contener" 92, "elaborado en una/un
# linea/equipo/planta" 13, "trazas de" 10, "fabricado en una/un
# linea/equipo/planta" 4, "pueden contener" 1. "may contain" y "puede haber"
# no salieron en la muestra pero se agregan por si aparecen en el corpus
# completo. Aplicar sobre texto ya normalizado (normalizar()): minusculas,
# sin acentos.
#
# "CONTIENE:" NO es un marcador y no se agrega: es la declaracion obligatoria
# de alergenos -el producto SI los lleva-, no una advertencia de trazas.
# Tratarlo como marcador borraria detecciones legitimas (38 casos en la
# muestra de 600).
_MARCADORES_ADVERTENCIA_TRAZAS = [
    re.compile(r"puede\s+contener"),
    re.compile(r"pueden\s+contener"),
    re.compile(r"elaborado\s+en\s+(?:una?\s+)?(?:linea|equipo|planta)"),
    re.compile(r"fabricado\s+en\s+(?:una?\s+)?(?:linea|equipo|planta)"),
    re.compile(r"trazas\s+de"),
    re.compile(r"may\s+contain"),
    re.compile(r"puede\s+haber"),
]

# Si el marcador aparece antes de este umbral (fraccion del texto), no se
# recorta: la posicion mediana real del marcador es el 82 % del texto, y solo
# 2 de 93 casos en la muestra caian antes del 30 %. Un marcador tan al
# principio casi siempre es texto de OCR revuelto -ver el caso
# 7500525199010 en la prueba de tests/test_advertencia_alergenos.py-, donde
# recortar ahi borraria la lista de ingredientes real.
UMBRAL_TEXTO_ROTO = 0.30


def quitar_advertencia_trazas(texto_norm: str) -> tuple[str, bool]:
    """(texto_para_detectar, texto_roto). Recorta el texto en el primer
    marcador de advertencia de trazas, para que un colorante mencionado solo
    ahi -"...puede contener...amarillo 5"- no cuente como detectado. Si el
    colorante tambien aparece ANTES del marcador, sigue contando: se detecta
    sobre el texto recortado, no sobre el original completo, pero el tramo
    anterior al marcador queda intacto.

    Bug que corrige (parche 14, 05/09/2026): 13 de 600 productos de la
    muestra anotada -8.7 % del estrato sintetico- declaraban un colorante
    unicamente dentro de una linea de "puede contener" y el flujo los contaba
    como deteccion real. Ejemplo real (7501030421313): "PIEL DE CERDO, SAL
    YODADA, ACEITE VEGETAL PUEDE CONTENER: SOYA, LECHE, GLUTEN, AMARILLO 5"
    -el producto no lleva amarillo 5, la mencion es la advertencia de
    alergenos obligatoria por la tartrazina.

    Si el marcador aparece antes de UMBRAL_TEXTO_ROTO del texto, no se
    recorta -devuelve el texto tal cual- y texto_roto=True, para que el
    llamador registre el producto aparte en vez de confiar en el corte:
    a esa altura del texto casi siempre es un OCR revuelto, no una etiqueta
    real que abra con la advertencia."""
    if not texto_norm:
        return texto_norm, False
    inicios = [m.start() for pat in _MARCADORES_ADVERTENCIA_TRAZAS
               for m in [pat.search(texto_norm)] if m]
    if not inicios:
        return texto_norm, False
    ini = min(inicios)
    if ini / len(texto_norm) < UMBRAL_TEXTO_ROTO:
        return texto_norm, True
    return texto_norm[:ini], False


def como_lista(valor) -> list:
    """Normaliza a lista de cadenas cualquier campo de tipo lista del parquet.

    BUG QUE ARREGLA (2026-08-23): al leer parquet con pandas, las columnas de
    lista llegan como numpy.ndarray, que NO es list ni tuple. Un
    `isinstance(x, (list, tuple))` las descarta en silencio, y por eso el conteo
    de categorias en 03_cobertura_sesgo.py salio vacio pese a que el 52.8 % de
    los productos tienen categoria. Nunca uses isinstance con estos campos.
    """
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    try:
        if hasattr(valor, "tolist"):
            valor = valor.tolist()
        return [str(x) for x in valor if x is not None and str(x).strip()]
    except TypeError:
        return []


def guardar_reporte(nombre: str, datos: dict) -> Path:
    REPORTES.mkdir(parents=True, exist_ok=True)
    ruta = REPORTES / f"{nombre}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {ruta}")
    return ruta
