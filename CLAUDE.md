# Proyecto: colorantes naturales y sintéticos en el mercado alimentario mexicano

Contexto operativo para Claude Code. Léelo completo antes de tocar nada.

**Antes de generar o aplicar un parche nuevo, lee también `BITACORA_PARCHES.md`.**
Registra, parche por parche, qué se aplicó tal cual y qué se corrigió o se
decidió al aplicarlo en local — sin eso, un parche nuevo puede reabrir un bug
o una decisión que ya se resolvió en la corrida anterior, tal como pasó entre
los parches 12 y 13.

## Qué es esto

Artículo destinado a **CienciaUAT** (revista mexicana, Web of Science con JCR, español obligatorio, gratuita). Pregunta: qué categorías del mercado alimentario mexicano ya sustituyeron colorantes sintéticos por naturales, cuáles no, y qué las distingue.

Colaboración entre **Daniel** (ciencia de datos, IA) y la **Dra. Sulem Yali Granados-Balbuena** (química de alimentos, IPN-UPIIT; colorantes naturales, antocianinas de *Dahlia*, betalaínas, carmín).

**Esta fase es exploración de datos, no modelado ni redacción.** El objetivo es producir cuatro números que deciden el encuadre del artículo. Nada más. No escribas el manuscrito, no entrenes modelos, no propongas arquitecturas.

## Decisiones ya tomadas — no las reabras

| Decisión | Estado |
|---|---|
| Revista | CienciaUAT. Cerrado. |
| Idioma | Español; solo resumen en inglés. |
| Diseño | **Transversal**, no temporal. Cerrado con evidencia. |
| `created_t` | **No se usa como fecha de reformulación.** Mide alta de contribuidor. |
| NOM-051 como ancla temporal | Descartada: la reformulación documentada solo tocó nutrimentos críticos. |
| Modelo de clasificación | **Fuera.** En diseño transversal la etiqueta sería circular. |
| Caramelo E150 | Fuera del eje natural/sintético. Se menciona en discusión. |
| Carmín E120 | Natural, pero se reporta **por separado**: su barrera es de certificación, no de estabilidad. |
| E160a, E101, E140 | Origen no recuperable de la etiqueta. **Limitación declarada**, no contribución. |
| Recolección de datos nueva | No hay. Solo datos públicos. |

## El aporte del artículo, formulado con precisión

**No es** aplicar PLN a listas de ingredientes: eso ya está publicado (Tseng et al. 2022 buscó 64 aditivos sensoriales en 241 688 productos; IngID del USDA analiza listas desde 2021).

**Sí es**, en este orden:

1. Primera caracterización del sistema de color del mercado mexicano en el eje sustitución.
2. Primer recurso léxico anotado de colorantes alimentarios **en español** — no existe ninguno.
3. Cuantificación de lo que `additives_tags` no captura.

### El mecanismo de la brecha estaba mal enunciado (corregido el 25/08)

El enunciado original de este documento decía que los sintéticos se declaran por número y los naturales por nombre, y que por eso el campo estructurado los distingue. **Eso es falso**, verificado contra el código fuente de Open Food Facts (commit `76f4f43b6052835eeff822efddb0b0f37dd9a13f`; ver `HALLAZGO_openfoodfacts.md` en la raíz). `additives_tags` no es un campo capturado: `extract_additives_from_text()` lo recalcula en cada guardado segmentando `ingredients_text` contra la taxonomía multilingüe `additives` (659 entradas, 631 con traducción al español), que reconoce nombres de sustancia además de códigos E. Por lo tanto **la comparación no es campo estructurado contra texto libre: es un analizador contra otro sobre el mismo insumo**, y hay que decirlo así en Métodos.

Además, Open Food Facts desvía vitaminas, minerales, aminoácidos y nucleótidos a `vitamins_tags`/`minerals_tags` (issue #1131), aunque tengan número E. E101 (riboflavina) y E170 (carbonato de calcio) caen ahí; buscarlos solo en `additives_tags` es un error de medición nuestro, no una omisión de la base. `01_subconjunto_mx.py` ya extrae ambos campos (`vitaminas_tags`, `minerales_tags`).

**Enunciado corregido:** el vocabulario de la taxonomía `additives` está construido en español ibérico y no cubre las formas de declaración locales; falla de forma asimétrica porque los colorantes naturales se declaran con muchas formas que varían por región (extracto de betalaína, achiote, jamaica) mientras los sintéticos tienen pocas y estables (tartrazina, rojo allura). Esa asimetría —no la ceguera al origen— es el eje del artículo.

## Las cuatro comprobaciones de esta fase

Cada script produce un número y un archivo en `reportes/`. En orden de importancia:

1. **`02_brecha_tags.py` — la brecha de `additives_tags`.** De los productos mexicanos cuyo `ingredients_text` menciona un colorante por nombre, ¿qué proporción **no** lo tiene en `additives_tags`? Decide el título y el encuadre. **Va primero.**
2. **`03_cobertura_sesgo.py` — cobertura y sesgo.** Conteo por categoría contra el censo del INSP (38 872 productos, Contreras-Manzano et al. 2022) y contra Zancheta et al. 2025 (15 846 productos mexicanos, 2017). Concentración por marca y por contribuyente.
3. **`04_calidad_texto.py` — calidad de `ingredients_text`.** Vacío, truncado, idioma, indicios de OCR. Determina si el pipeline de PLN es viable.
4. **`01_subconjunto_mx.py` — tamaño y forma del subconjunto.** Es prerrequisito de todo lo demás.

Ampliado el 25/08 con `05_auditoria_brecha.py` (brecha depurada), `06_sustitucion_por_categoria.py` (P1/P2 por categoría), `08_vocabulario_off.py` (mecanismo) y `07_forma_y_clase.py` (la corrida que decide la tesis; corre después de 08). Ver `HALLAZGO_openfoodfacts.md` y la sección de estructura más abajo.

## Tres predicciones fijadas antes de ver los datos

Están registradas para que no se acomoden al resultado. Si fallan, se reporta que fallaron.

- **P1 — Azul sin reemplazo.** No hay natural estable y autorizado equivalente a E132/E133. Las categorías dependientes del azul no habrán sustituido.
- **P2 — Amarillo hidrosoluble, el cuello de botella.** Los amarillos naturales son mayoritariamente hidrofóbicos. La tartrazina (E102) persistirá en bebidas más que otros sintéticos. Excepciones a declarar: riboflavina E101 es hidrosoluble; hay curcumina hidrodispersable.
- **P3 — Sustitución por producto nuevo, no por reformulación.** Las marcas abren líneas con tonos más suaves en vez de reformular. Los productos con natural aparecerán como referencias distintas, no como versiones modificadas.

## Reglas de trabajo

- **Todo en español**: nombres de variables, comentarios, salidas, gráficas. El manuscrito va en español y el repositorio es material suplementario citable.
- **Nada de `created_t` como fecha de reformulación.** Si necesitas fechas, es para caracterizar la actividad de contribución, y así hay que etiquetarlo en la gráfica.
- **Determinismo**: fija semillas, registra la versión del volcado de Open Food Facts y su fecha de descarga en `reportes/procedencia.json`.
- **Open Food Facts es ODbL.** Hay que citarla y respetar la cláusula de atribución compartida. Anótalo en el README de salida.
- **No inventes umbrales después de ver los resultados.** Si un umbral hace falta, se decide y se escribe antes.
- **Cuando un dato no exista, dilo.** No imputes silenciosamente.

## Datos

**Fuente preferida:** volcado Parquet de Open Food Facts (Hugging Face, `openfoodfacts/product-database`). Se consulta con DuckDB para poder podar columnas y filtrar por país sin cargar todo en memoria.

**Advertencia importante:** el esquema del Parquet tiene columnas anidadas (`product_name`, `ingredients_text` suelen ser listas de estructuras con `lang`/`text`) y **cambia entre versiones**. `00_explorar_esquema.py` existe justamente para introspeccionar antes de asumir nada. No hardcodees nombres de columna sin haberlo corrido.

Alternativa si el Parquet falla: el CSV comprimido de `static.openfoodfacts.org/data/`, más pesado y con menos tipos.

**El subconjunto mexicano se filtra por `countries_tags` que contenga `en:mexico`.** Ojo: hay productos con varios países; decide y documenta si se incluyen los multipaís (recomendación: sí, con una bandera que lo marque).

## Estructura

*(Nota: esta lista se quedó fija en el estado del 25/08 y no se ha actualizado
con los scripts 09–14 ni los archivos de congelamiento. Ver `BITACORA_PARCHES.md`
para el estado real y completo.)*

```
BITACORA_PARCHES.md          que se aplico y que se corrigio, parche por parche
config/colorantes.yaml       diccionario semilla y matriz tono × solubilidad
config/categorias.yaml       taxonomia OFF -> 12 categorias analiticas
src/00_explorar_esquema.py
src/01_subconjunto_mx.py
src/02_brecha_tags.py        <- brecha bruta
src/03_cobertura_sesgo.py
src/04_calidad_texto.py
src/05_auditoria_brecha.py   <- brecha depurada (66.1 %), esta es la que se cita
src/06_sustitucion_por_categoria.py   evalua P1/P2 por categoria
src/07_forma_y_clase.py      <- LA CORRIDA QUE DECIDE. Corre DESPUES de 08.
src/08_vocabulario_off.py    <- explica el mecanismo. Corre ANTES de 07.
src/util.py                  REQUIEREN_CONTEXTO, como_lista(), terminos_ordenados()
datos/crudo/                 volcado (en .gitignore)
datos/intermedio/            subconjunto mexicano en parquet
datos/externo/               taxonomia additives.txt de OFF (no es nuestra; ver LEEME.md)
reportes/                    salidas en json y md
HALLAZGO_openfoodfacts.md    por que el mecanismo original estaba mal enunciado
```

**Orden de ejecución de 07 y 08: `08` siempre antes que `07`.** `08` diagnostica por qué existe la brecha (cobertura de vocabulario, `mandatory_additive_class`, desvío a otras taxonomías); `07` la mide en detalle, con el falsador 1 que decide si el eje es origen o forma de declaración. Correr `07` primero produce tablas convincentes de una cifra cuyo mecanismo aún no se conoce — ya pasó una vez que la tabla del `02` se mezcló con el porcentaje del `05` sin que nadie lo notara.

## Trampas del dominio que hay que respetar

El diccionario en `config/colorantes.yaml` incluye casos que rompen el emparejamiento ingenuo:

- **«rojo cochinilla A»** es E124, **sintético**. **«cochinilla»** a secas es E120, natural. Buscar la subcadena «cochinilla» los confunde.
- **«carmín de índigo»** es E132, **sintético**. **«carmín»** es E120, natural.
- **«extracto de zanahoria»** puede ser colorante o ingrediente alimentario según el contexto.
- **«cúrcuma»** puede ser especia o colorante.

Estas ambigüedades son la justificación del brazo de reconocimiento de entidades frente al de diccionario: el diccionario no desambigua por contexto.

## Diseño de la validación del PLN

Dos brazos, con el umbral fijado antes de correr nada:

1. `additives_tags` tal cual.
2. Diccionario en español con normalización y emparejamiento difuso.

**El brazo 3 (transformador afinado, BETO/RoBERTa-BNE) queda fuera del artículo.** Decisión cerrada el 25/08. Motivo: presupuesto de espacio —25 cuartillas incluyendo figuras, tablas y anexos— y no falta de mérito. El conjunto anotado se construye igual, porque era necesario para validar los brazos 1 y 2, no para el 3.

### El conjunto anotado

600 productos en cuatro estratos: 150 con sintético detectado, 250 con natural detectado, 100 con detección ambigua descartada por la regla de contexto, 100 sin ninguna detección. Doble anotación; la Dra. adjudica discordias. Semilla fija, pesos de reponderación declarados (`07_forma_y_clase.py`, bloque E). Se deposita en Zenodo con DOI bajo ODbL.

**κ se reporta partido: κ_detección y κ_clase, nunca un solo número agregado.** El desacuerdo entre anotadores vive en la clasificación de función y origen, no en la delimitación del tramo; un promedio esconde dónde está el problema.

**Etiqueta `origen_indeterminado`** (E160a, E101, E140): el anotador **no** debe adivinar entre sintético y natural. Existe una tercera categoría explícita. Forzar la dicotomía hunde κ artificialmente.

**El manuscrito no lleva anexo.** Las 25 cuartillas ya lo incluyen; un anexo sería texto disfrazado. Todo material de respaldo (diccionario anotado, muestra de 600, tablas por código) va a Zenodo.

## Correcciones de dato (25/08)

- El diccionario tiene **153 términos**, no 148: 60 sintéticos, 80 naturales, 13 de caramelo. Más 13 genéricos aparte. 31 sustancias, sin duplicados. Verificado contra `config/colorantes.yaml`; no se modificó el archivo, solo el conteo documentado.
- Bisikalo et al. es **2025**, no 2026. Revista de la propia institución de los autores, sin indexación en Scopus ni Web of Science. Su cifra aparece de tres formas incompatibles en el mismo artículo. No citar como referencia de desempeño.
- El carmín cargando en F6 junto con nitritos y eritorbato está en la **Tabla Suplementaria 6** de Zancheta et al. (2025), la de México — no en la Tabla 4, que es la muestra global.
- La comparación con Dunford et al. (2025) es **solo de sintéticos**: su 19 % no incluye colorantes naturales. La comparación con Chiu et al. (2025) requiere incluir el caramelo E150, que su 19.8 % sí cuenta (`07_forma_y_clase.py`, bloque D).

## Restricciones de la revista

25 cuartillas máximo con figuras y tablas. Word, APA autor-año, sin notas al pie. Estructura: Introducción · Materiales y métodos · Resultados y discusión · Conclusiones · Referencias. Al menos 40 % de las referencias de los últimos cinco años. Meta: 45–55 referencias; hay 142 candidatas en `referencias_unificadas.ris`.

## Qué NO hacer en esta fase

- No escribir secciones del manuscrito.
- No entrenar ni afinar modelos.
- No construir el pipeline de NER completo.
- No hacer gráficas bonitas todavía: primero los números.
- No tocar el diccionario semilla sin registrar por qué.

## Qué NO hacer, ampliado (25/08)

- **No mezclar universos.** La tabla de brecha por código del script `02` es del universo **sin depurar**; el 66.1 % del script `05` es del **depurado**. Ya se presentaron juntos una vez en el mismo documento. No repetirlo.
- **No comparar nuestro agregado ponderado contra el 37.9 % de Tseng.** Él reporta la **mediana del porcentaje por aditivo**. Son estadísticos distintos. `07_forma_y_clase.py` calcula la mediana precisamente para que exista la cifra comparable.
- **No interpretar el índice de cárnicos.** ~92 % con ~38 % de carmín se reporta con su composición al lado y no se comenta. Cualquier párrafo interpretativo ahí se leerá como afirmación de sustitución cuando en realidad es una categoría que nunca usó sintéticos.
- **No reportar comidas preparadas** (natural alto en `06`) hasta que el estrato de descartados del conjunto anotado resuelva si es señal o filtrado insuficiente de páprika y achiote en sazonadores.
- **No afirmar capacidad de sustitución.** No hay literatura de fuerza tintórea ni de costo para páprika y achiote en aplicación seca dentro de las 142 referencias. Se plantea como hipótesis declarada o no se plantea.
- **No actualizar `datos/externo/additives.txt` a mitad del análisis.** La taxonomía cambia; el commit usado va en `reportes/procedencia.json`.
