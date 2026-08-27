# Cómo construye Open Food Facts el campo `additives_tags`

> Verificado el 25 de agosto de 2026 contra el código fuente de Product Opener,
> commit `76f4f43b6052835eeff822efddb0b0f37dd9a13f`. No es una impresión ni una
> lectura de documentación: son las funciones y los tests unitarios del
> repositorio.

Este documento existe porque el proyecto venía trabajando con una hipótesis que
resultó **falsa**. Hay que leerlo antes de interpretar los scripts 07 y 08, y
antes de escribir una línea de la Introducción.

---

## Lo que creíamos

> «Los colorantes sintéticos se declaran por número E o nombre estandarizado; los
> naturales, por nombre de compuesto o de fuente. Por eso los campos
> estructurados ven unos y no otros.»

Esa frase iba a ser el mecanismo central del artículo y la «frase memorable» de
la conclusión. **Está mal.**

## Lo que el código dice

### 1. El campo se deriva del texto, siempre

`additives_tags` no es un campo que capture nadie. Se recalcula en cada guardado
del producto:

    lib/ProductOpener/FoodProducts.pm → specific_processes_for_food_product()
      → extract_additives_from_text()   (lib/ProductOpener/Ingredients.pm)

La función **borra** los campos previos y los reconstruye segmentando
`ingredients_text` y canonicalizando cada segmento contra la taxonomía
`additives`. No hay ninguna ruta por la que un contribuyente escriba ese campo
a mano.

**Consecuencia para el manuscrito:** nuestra comparación no es «campo
estructurado contra texto libre». Es **un analizador contra otro analizador
sobre el mismo insumo**. Hay que declararlo en Métodos desde el primer borrador,
y explica por qué la comparación de Tseng et al. (2022) —texto de BFPD contra
etiquetas de OFF, dos fuentes independientes— es metodológicamente más limpia
que la nuestra.

### 2. OFF no reconoce solo códigos E

La taxonomía tiene **659 entradas, 631 con traducción al español y 622 con
sinónimos nominales**. Su propio test unitario detecta `nitrite de sodium`,
`érythorbate de sodium` y `lactate de potassium` en un texto **sin un solo
código E**.

La primera mitad de nuestra frase —«los sintéticos se declaran por número»— no
puede sostener el argumento, porque OFF también reconoce nombres.

### 3. Existe una regla de clase obligatoria

Para **45 entradas** de la taxonomía, el nombre de la sustancia no basta. El
campo `mandatory_additive_class` exige que el texto haya declarado antes la
clase tecnológica, o que aparezca el código E. El test es literal:

    "safran"              → []
    "colorant : safran"   → ["en:e164"]

Entre colorantes, la regla aplica a:

| Código | Sustancia | Clase exigida |
|---|---|---|
| E120 | cochinilla, ácido carmínico, carmín | `en:colour` |
| E123 | amaranto | `en:colour` |
| E150 | caramelo | `en:colour` |
| E160a | carotenos | `en:colour` |
| E164 | azafrán | `en:colour` |
| E170(i) | carbonato de calcio | `en:colour` entre otras |

**Esto es, casi literalmente, nuestra regla de sesenta caracteres.** La
reinventamos sin saberlo. Con una diferencia que importa: OFF exige la clase en
posición estructural dentro de la segmentación; nosotros aceptamos proximidad
dentro de una ventana. La nuestra es más permisiva, así que parte de la brecha
que medimos puede ser esa diferencia de rigor y no una omisión.

Nótese que **E123 es sintético y también está sujeto a la regla**. Es el caso de
prueba limpio: si la regla explica la brecha, E123 debería comportarse como los
naturales pese a ser azoico.

### 4. Vitaminas y minerales van a otra taxonomía

Por diseño (issue #1131), vitaminas, minerales, aminoácidos y nucleótidos se
etiquetan en `vitamins_tags` y `minerals_tags`, **no** en `additives_tags`,
aunque tengan número E.

Golpea directo a los dos códigos más «perdidos» de nuestra corrida bruta:

- **E101 riboflavina** — 605 detecciones, 98.5 % de brecha aparente
- **E170 carbonato de calcio** — 206 detecciones, 78.0 %

Buscarlos solo en `additives_tags` **es un error de medición nuestro**. Hay que
corregirlo antes de reportar cualquier cifra agregada.

---

## Lo que sí explica la asimetría

Se cruzó nuestro diccionario contra el vocabulario español de la taxonomía,
término por término. Lo que falta no es aleatorio:

| Código | términos nuestros | en OFF | ejemplos que OFF **no** tiene |
|---|---|---|---|
| E163 antocianinas | 14 | 3 | extracto de col morada, camote morado, hibisco, enocianina |
| E162 betalaínas | 10 | 6 | **extracto de betalaína**, betalaínas, concentrado de betabel |
| E160b achiote | 7 | 6 | extracto de achiote, atsuete, urucú, annatto |
| E160c páprika | 6 | 10 | páprika, oleorresina de páprika |
| espirulina | 3 | **0** | no existe entrada en la taxonomía |
| E129 rojo allura | 9 | 7 | fd&c rojo 40, rojo 40, ci 16035 |
| E102 tartrazina | 9 | 8 | amarillo no. 5, fd&c amarillo 5, ci 19140 |

La taxonomía está construida en **español ibérico** y le faltan dos familias de
formas a la vez: las de fuente que usa el etiquetado mexicano, y las de estilo
FD&C que llegan del mercado estadounidense.

Y ahí está la asimetría real. A los sintéticos les faltan términos
*alternativos* a formas que OFF sí tiene —tiene «tartrazina», tiene «rojo
allura»— así que el producto casi siempre engancha por alguno. A los naturales
les falta con frecuencia **la única forma que se usa**: la Dra.
Granados-Balbuena confirmó que en México se declara «extracto de betalaína», y
esa cadena no está en la taxonomía.

## El enunciado corregido

> El vocabulario fijo de una base internacional no cubre las formas de
> declaración locales, y falla de forma asimétrica porque los colorantes
> naturales se declaran con muchas formas que varían por región mientras los
> sintéticos tienen pocas y estables.

Es mejor que el anterior: está diagnosticado al mecanismo, se verifica contra
código y taxonomía públicos, y genera una **predicción comprobable** —en el
subconjunto español de OFF la brecha del lado natural debería ser mucho menor—
que cuesta unas horas de cómputo.

## Lo que esto no invalida

El hallazgo sigue en pie y sigue siendo el eje del artículo. Lo que cambia es su
enunciado y su alcance:

- **No** es «el campo estructurado es ciego al origen».
- **Sí** es «el vocabulario de este analizador no cubre las formas de
  declaración locales, y eso cae desproporcionadamente sobre los naturales».
- La convergencia con el 37.9 % de Tseng del lado sintético se mantiene.
- La crítica al criterio de inclusión de Tseng —«no usado en cocina doméstica»
  borra los naturales por definición— se mantiene y ahora tiene compañía: OFF
  resuelve el mismo problema con una regla de clase obligatoria en vez de con
  una exclusión. Son dos soluciones distintas al mismo hecho incómodo: los
  colorantes naturales también son alimentos.

## Fuentes

- `lib/ProductOpener/Ingredients.pm`, `extract_additives_from_text()`
- `lib/ProductOpener/FoodProducts.pm`, `specific_processes_for_food_product()`
- `taxonomies/additives.txt`
- openfoodfacts-server, issue #1131 — *Remove vitamins and minerals from additives*
- openfoodfacts-server, issue #2417 — *Improved integration of additives taxonomy in ingredients taxonomy*
