# El respaldo normativo del mecanismo

> Verificado el 27 de agosto de 2026 contra el texto del Diario Oficial de la
> Federación. Esto cierra el hueco más grave que tenía el artículo: hasta hoy,
> la única evidencia de cómo se declaran los colorantes en México era un mensaje
> de WhatsApp de la Dra. Granados-Balbuena.

## Lo que dice la ley

**NOM-051-SCFI/SSA1-2010, numeral 4.2.2.2.4:**

> «En la declaración de aditivos utilizados en la elaboración de los alimentos y
> bebidas no alcohólicas preenvasados debe utilizarse el nombre común o en su
> defecto, alguno de los sinónimos, establecidos en el Acuerdo. Las enzimas y
> saborizantes, saboreador o aromatizantes podrán ser declarados como
> denominaciones genéricas.»

**El Acuerdo, artículo DECIMOSEGUNDO:**

> «Los aditivos listados en el presente Acuerdo, con excepción de las enzimas,
> los coadyuvantes de elaboración y los saborizantes, deberán indicarse, en la
> declaración de ingredientes contenida en el etiquetado, con el nombre común o,
> en su defecto, con alguno de los sinónimos enumerados en el presente Acuerdo.»

«El Acuerdo» está definido en el numeral 3.1 de la norma como el *Acuerdo por el
que se determinan las sustancias permitidas como aditivos y coadyuvantes en
alimentos, bebidas y suplementos alimenticios*, de la Secretaría de Salud
(DOF 16/07/2012, con modificaciones en 2013 y 2016).

## Las cuatro consecuencias

**1. México declara por NOMBRE, no por código. Por ley.**
No es una costumbre ni una preferencia del mercado: es obligación normativa. El
artículo no autoriza declarar por número.

**2. Los colorantes NO tienen exención de nombre genérico.**
La exención existe y está acotada a enzimas, coadyuvantes y saborizantes. Un
colorante no puede declararse solo como «colorante»: tiene que ir el nombre
específico. Esto importa porque Open Food Facts, para 45 entradas de su
taxonomía —entre ellas E120 carmín y E160a carotenos—, **exige lo contrario**:
que la clase tecnológica esté declarada, o si no no reconoce la sustancia. La
regla `mandatory_additive_class` está diseñada contra una práctica de etiquetado
que en México no es la obligatoria.

**3. México usa SIN, no números E.**
El identificador oficial es el **SIN**, Sistema Internacional de Numeración del
Codex, con las siglas en español, más el **No. CI** del Colour Index para los
colorantes. La expresión «número E» **no aparece** en el Acuerdo. Nuestro
diccionario está construido sobre códigos E porque así los guarda Open Food
Facts, y eso hay que declararlo en Métodos: estamos usando la nomenclatura
europea como llave sobre un mercado que se rige por otra.

**4. Los sinónimos del Acuerdo son jurídicamente vinculantes.**
Cualquiera de ellos es una declaración válida en etiqueta. El formato de una
entrada real del Anexo III:

    12. ERITROSINA Y SUS LACAS
        ROJO ALIMENTOS 14. ROJO 3 FD&C
        No. CI: 45430, SIN: 127
        Sinónimos: 2',4',5',7'-Tetrayodo-...-monohidrato disódico.
                   Rojo 3. Rojo FD&C 3. Rojo ácido 51

Nótese que los sinónimos van separados por **punto**, no por coma, y que
incluyen tanto las formas de estilo FD&C —las que Open Food Facts no tiene— como
el nombre químico completo.

## Por qué esto reencuadra el hallazgo

Hasta ahora la comparación era: **nuestro diccionario** contra el vocabulario de
Open Food Facts. La objeción evidente es que los términos los pusimos nosotros y
podríamos haber inventado formas que nadie imprime.

Con el Acuerdo, la comparación correcta es: **el vocabulario legalmente
obligatorio en México** contra el vocabulario de Open Food Facts. Eso ya no es
una elección nuestra, y la objeción desaparece.

El enunciado del hallazgo pasa a ser:

> La normativa mexicana obliga a declarar cada aditivo por su nombre común o por
> alguno de los sinónimos de una lista oficial. El vocabulario español de Open
> Food Facts no se construyó a partir de esa lista, sino con nomenclatura
> ibérica y europea. La consecuencia es una omisión sistemática, medible, y
> concentrada en los colorantes naturales.

Eso es verificable por cualquiera contra dos documentos públicos.

## Los anexos, ya descargados y verificados (27/08)

La URL que traía la primera versión de este documento
(`.../file/926080/ANEXO_III.pdf`) ya no resuelve — gob.mx resube estos
archivos y cambia el ID de adjunto cada vez. Las vigentes al 27/08/2026:

- **ANEXO III — Colorantes con una IDA establecida** (actualizado 11/05/2026)
  `https://www.gob.mx/cms/uploads/attachment/file/1090701/ANEXO_III.pdf`
- **ANEXO IV — Colorantes que pueden ser utilizados de acuerdo a las BPF**
  (actualizado 03/11/2025)
  `https://www.gob.mx/cms/uploads/attachment/file/1078651/ANEXO_IV.pdf`

Copia local de ambos en `datos/externo/ANEXO_III.pdf` y `ANEXO_IV.pdf`, para
no depender de que la URL siga viva. Verificados campo por campo contra
`config/acuerdo_colorantes.yaml`: la separación 160a(i)/160a(ii) del beta
caroteno, el CI 42900 del azul brillante, la inversión Azul Alimentos 1/2, y
las tres entradas de antocianinas BPF (zanahoria negra 23/10/2018, papa
dulce morada 21/10/2020, campanilla azul 03/11/2025) coinciden exactas.

El Anexo IV es el que más importa: ahí caen espirulina y las antocianinas
más recientes (zanahoria negra, papa dulce morada, campanilla azul) que aún
no entran al Acuerdo publicado en el DOF. Achiote, páprika, betabel y
clorofilas ya estaban en el Anexo III desde ediciones anteriores.

Con esos dos PDF se puede hacer lo que antes no se podía: reconstruir el
diccionario desde la lista oficial en vez de desde la intuición, y medir la
cobertura de Open Food Facts contra un vocabulario que no elegimos nosotros.
Es el script 10 y probablemente el resultado más sólido del artículo.

## Un dato adicional que confirma el gancho regulatorio

El numeral 12 del Anexo III —**eritrosina, SIN 127**— fue dejado insubsistente
por acuerdo del **28 de mayo de 2026**, con 24 meses de plazo para reformular.
Coincide con lo que ya traía el plan de capítulos. Nuestro corte de datos
documenta el punto de partida de esa transición.

## Fuentes

- NOM-051-SCFI/SSA1-2010, numerales 3.1 y 4.2.2.2.1 a 4.2.2.2.4
  `https://dof.gob.mx/normasOficiales/4010/seeco11_C/seeco11_C.htm`
- Acuerdo de aditivos, artículos SEGUNDO, DECIMOSEGUNDO y DECIMOTERCERO,
  DOF 16/07/2012, códigos 5259470 a 5259473
- Nota DOF 5788852, formato del Anexo III
