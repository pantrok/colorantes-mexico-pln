# Revisión del diccionario — Dra. Granados-Balbuena

**Qué es esto.** El instrumento del artículo es un diccionario de 148 términos
que reconoce colorantes en el texto de la lista de ingredientes. Todo lo demás
—las cifras, la validación, el conjunto que vamos a anotar— descansa en que ese
diccionario esté bien. Nadie con formación en química de alimentos lo ha
revisado todavía.

**Cuánto tiempo.** Entre hora y media y dos horas. El archivo viene ordenado por
número de detecciones, de mayor a menor: **los primeros veinte renglones deciden
casi todo**. Si se acaba el tiempo, con esos veinte y el bloque de veredictos de
abajo es suficiente para seguir.

**El archivo.** `08_revision_dra.csv`, se abre en Excel. Cinco columnas vacías
al final para llenar.

---

## Las cuatro preguntas del archivo

Para cada renglón (un término del diccionario):

**P1 — ¿se usa en etiqueta mexicana?**
Solo hace falta contestarla en los renglones donde `detecciones` es **0**. Son
términos que pusimos nosotros y que nunca aparecieron en ningún producto.
Responder `si` / `no` / `duda`. Un `no` significa que sobra y lo quitamos.

**P2 — cuando aparece, ¿está declarando un colorante?**
Esta es la importante, y es para los renglones **con detecciones**. La pregunta
no es si la sustancia existe, sino si al leerla en una lista de ingredientes uno
entendería que está ahí para dar color, o si está como otra cosa: especia,
vitamina, mineral, ingrediente.
Responder `si` / `no` / `a veces`.

Ejemplo de por qué importa: `curcuma` tiene 78 detecciones (y `curcumina`,
33 más, en un renglón aparte). Si en la mayoría está como especia y no como
colorante, nuestra cifra de colorantes naturales está inflada.

**P3 — ¿el código E es el correcto?**
Responder `si`, o `no` y cuál debería ser.

**P4 — ¿la clase es la correcta?**
Las clases son cuatro: `sintetico`, `natural_botanico`, `carmin`,
`mineral_inorganico`. Responder `si`, o `no` y cuál.

**comentario** — para lo que no cabe en las anteriores.

---

## Los seis veredictos que necesito por escrito

Estos no salen del archivo. Son decisiones de clasificación que tomé yo sin
formación en el tema y que cambian los resultados. Necesito un sí o un no de
usted en cada uno, aunque sea en dos líneas.

**1. Los pigmentos inorgánicos.**
Saqué del eje natural/sintético al carbonato de calcio (E170), el dióxido de
titanio (E171) y los óxidos de hierro (E172), y los puse en una clase aparte,
`mineral_inorganico`. Mi razonamiento: no son ni de origen botánico o animal ni
azoicos de síntesis, así que no participan de la sustitución que estudia el
artículo.
**¿Es defendible, o el dióxido de titanio debería contar como sintético?**
Esto mueve las cifras: el E171 tiene una brecha muy baja (21.7 %) y mientras
estuvo dentro de «naturales» jalaba el promedio natural hacia abajo.

**2. La riboflavina (E101).**
Tiene 814 detecciones que nuestro filtro descartó por parecer fortificación con
vitamina B2 y no colorante.
**¿La riboflavina se usa alguna vez como colorante en alimento empacado
mexicano, o en la práctica siempre es fortificación?**
Si siempre es fortificación, la sacamos del diccionario y se acabó el problema.
Si a veces es colorante, hay que quedarse con ella y explicar cómo se distingue.

**3. El carbón vegetal (E153).**
El diccionario trae `carbon activado` y `carbon medicinal` como términos suyos.
**¿Esos dos nombran colorante, o son de suplemento y farmacia?**

**4. «Extracto de zanahoria».**
Lo tenemos como caroteno (E160a). **¿En una etiqueta mexicana eso declara
colorante, o es más bien ingrediente?** Y por separado: `extracto de zanahoria
morada` lo tenemos como antocianina (E163). ¿Correcto?

**5. Los óxidos de hierro (E172).**
**¿Se usan en alimento empacado en México, o esto es cosmética?**

**6. La espirulina.**
Open Food Facts no tiene ninguna entrada para espirulina ni ficocianina en su
taxonomía de aditivos: no existe como aditivo para ellos. Nosotros la contamos
como colorante natural, con 6 detecciones.
**¿Es correcto tratarla como colorante, dado que en México se declara más bien
como ingrediente?**

---

## Lo que también sirve, si le sobra tiempo

**Términos que faltan.** Es lo único que no puedo sacar de ningún lado. Si al
leer la lista piensa «esto también se declara así y no está», anótelo al final
del archivo. Ya sabemos que faltan formas: usted mencionó `extracto de
betalaína` y `ácido carmínico`, y los dos están, pero seguro hay más.

Interesan sobre todo las formas de **achiote, páprika, cúrcuma, betabel,
jamaica y carmín**, porque son los códigos donde nuestra medición se comporta de
manera más extraña.

---

## Por qué esto es urgente y no cosmético

Encontramos que Open Food Facts —la base de la que salen todos los datos— tiene
su vocabulario de colorantes escrito en español de España. Dice «pimentón», no
«páprika». No tiene «extracto de achiote», ni «atsuete», ni «extracto de
betalaína», ni «oleorresina de páprika».

De nuestros 148 términos, su base solo reconoce 56.

Ese es el hallazgo principal del artículo: **el vocabulario de una base
internacional no cubre cómo se declaran realmente los colorantes en México, y
falla más del lado natural que del sintético.** Un colorante cuyo término no
está en su vocabulario tiene casi veinticinco veces más probabilidad de
quedarse sin registrar.

Pero ese resultado se sostiene solo si nuestros 148 términos son formas que de
verdad se usan en etiquetas mexicanas. Si una parte los inventamos nosotros, lo
que estaríamos midiendo es nuestra propia imaginación.

Por eso hace falta su revisión antes de escribir nada, y antes de que empecemos
a anotar los 600 productos a mano — porque esa anotación se hace contra este
diccionario y no se puede repetir.

---

## Qué necesito de vuelta

El archivo con las columnas llenas, aunque sea solo en los primeros veinte
renglones, y los seis veredictos contestados. Con eso se congela el diccionario,
se vuelve a correr todo una última vez, y ya nadie lo toca.
