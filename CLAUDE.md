# Proyecto: colorantes naturales y sintéticos en el mercado alimentario mexicano

Contexto operativo para Claude Code. Léelo completo antes de tocar nada.

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

La Dra. confirmó que en México **las etiquetas declaran por nombre de compuesto** («extracto de betalaína», «ácido carmínico») y no por código E. Esa es la razón por la que el campo estructurado pierde información, y medir esa pérdida es el número de portada.

## Las cuatro comprobaciones de esta fase

Cada script produce un número y un archivo en `reportes/`. En orden de importancia:

1. **`02_brecha_tags.py` — la brecha de `additives_tags`.** De los productos mexicanos cuyo `ingredients_text` menciona un colorante por nombre, ¿qué proporción **no** lo tiene en `additives_tags`? Decide el título y el encuadre. **Va primero.**
2. **`03_cobertura_sesgo.py` — cobertura y sesgo.** Conteo por categoría contra el censo del INSP (38 872 productos, Contreras-Manzano et al. 2022) y contra Zancheta et al. 2025 (15 846 productos mexicanos, 2017). Concentración por marca y por contribuyente.
3. **`04_calidad_texto.py` — calidad de `ingredients_text`.** Vacío, truncado, idioma, indicios de OCR. Determina si el pipeline de PLN es viable.
4. **`01_subconjunto_mx.py` — tamaño y forma del subconjunto.** Es prerrequisito de todo lo demás.

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

```
config/colorantes.yaml    diccionario semilla y matriz tono × solubilidad
src/00_explorar_esquema.py
src/01_subconjunto_mx.py
src/02_brecha_tags.py     <- el importante
src/03_cobertura_sesgo.py
src/04_calidad_texto.py
src/util.py
datos/crudo/              volcado (en .gitignore)
datos/intermedio/         subconjunto mexicano en parquet
reportes/                 salidas en json y md
```

## Trampas del dominio que hay que respetar

El diccionario en `config/colorantes.yaml` incluye casos que rompen el emparejamiento ingenuo:

- **«rojo cochinilla A»** es E124, **sintético**. **«cochinilla»** a secas es E120, natural. Buscar la subcadena «cochinilla» los confunde.
- **«carmín de índigo»** es E132, **sintético**. **«carmín»** es E120, natural.
- **«extracto de zanahoria»** puede ser colorante o ingrediente alimentario según el contexto.
- **«cúrcuma»** puede ser especia o colorante.

Estas ambigüedades son la justificación del brazo de reconocimiento de entidades frente al de diccionario: el diccionario no desambigua por contexto.

## Diseño de la validación del PLN (para más adelante, no ahora)

Tres brazos, con el umbral fijado antes de correr nada:

1. `additives_tags` tal cual.
2. Diccionario en español con normalización y emparejamiento difuso.
3. Transformador en español afinado (BETO, RoBERTa-BNE) sobre el conjunto anotado.

Si el brazo 3 no supera al 2, es un hallazgo legítimo y se reporta. No se decide la hipótesis después.

## Restricciones de la revista

25 cuartillas máximo con figuras y tablas. Word, APA autor-año, sin notas al pie. Estructura: Introducción · Materiales y métodos · Resultados y discusión · Conclusiones · Referencias. Al menos 40 % de las referencias de los últimos cinco años. Meta: 45–55 referencias; hay 142 candidatas en `referencias_unificadas.ris`.

## Qué NO hacer en esta fase

- No escribir secciones del manuscrito.
- No entrenar ni afinar modelos.
- No construir el pipeline de NER completo.
- No hacer gráficas bonitas todavía: primero los números.
- No tocar el diccionario semilla sin registrar por qué.
