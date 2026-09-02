# Diccionario de colorantes, versión 1.1 — CONGELADO

**Fecha:** 20260902T011834Z  
**sha256:** `8c7c8790221bf161dc1353282d1da34595a7176f9a4cf16046c22486e88e9640`  
**Códigos:** 35 (antes 37) · **Términos:** 202 (antes 206)  
**Veredicto de la revisora:** 2026-09-01, Sulem Yali Granados-Balbuena

## Qué quiere decir que esté congelado

La anotación manual de 600 productos se hace **contra esta versión**. Si el diccionario cambia después, la anotación deja de medir lo que se anotó y hay que rehacerla. Por eso el hash: permite escribir en Métodos «se anotó contra la versión 1.1, sha256 `8c7c8790221bf161…`» y que eso sea comprobable.

`tests/test_congelado.py` falla si el contenido cambia sin subir la versión.

## Regla de decisión aplicada

**P2, la función** — «cuando aparece así, ¿está para dar color?» — la decide la revisora. Es lo que el corpus no puede contestar y por eso se preguntó.

**P1, la atestiguación** — «¿se escribe así en una etiqueta mexicana?» — la decide el corpus. Una forma con detecciones no se borra porque la revisora no la haya visto. Podar por P1 solo cuando el término tiene cero detecciones.

## Cambios aplicados

- codigo completo naturales/E101: se elimina (2 terminos: lactoflavina, vitamina b-2)
- codigo completo naturales/E153: se elimina (1 terminos: carbon medicinal)
- fuera del eje  naturales/E140: «clorofilinas»

## Desacuerdo declarado

Términos que la revisora marcó como no habituales en etiqueta mexicana y que el corpus sin embargo contiene. **No se borraron.** Borrar formas atestiguadas porque no son habituales encogería la clase natural, que es justo la que sostiene el resultado del artículo.

| Término | Código | Detecciones |
|---|---|---|
| caroteno | E160a | 17 |
| norbixina | E160b | 13 |
| beta caroteno sintetico | E160a-i | 10 |
| extracto de zanahoria | E160a | 5 |
| extracto de pimenton | E160c | 5 |
| carotenos | E160a | 4 |
| carmin de cochinilla | E120 | 2 |
| carmines | E120 | 1 |
| extracto de zanahoria morada | E163 | 1 |

## Fuera del eje de color

Términos con P2 = no: no son colorantes cuando aparecen así en una etiqueta mexicana. Salen del conteo. **Siguen existiendo en el vocabulario legal de referencia** (`acuerdo_colorantes.yaml`), que no se toca: que la ley los liste es parte del argumento del artículo.

- **E101** — riboflavina, vitamina b2, lactoflavina, vitamina b-2: Fortificacion, no color. La revisora anoto «Suplemento» en los dos terminos que reviso. «lactoflavina» y «vitamina b-2» son la misma sustancia y no se le mostraron por no tener detecciones.
- **E170** — carbonato de calcio: Mineral, no color. Anotado «Mineral».
- **E153** — carbon activado, carbon vegetal, carbon medicinal: Suplemento en dietas, no color. «carbon medicinal» es la misma sustancia y no se le mostro por no tener detecciones.
- **E140** — clorofilina, clorofilinas: P1 = no y P2 = no. Unico punto donde el veredicto discrepa del Acuerdo, que si lista SIN 140 y 141 como colorantes. Tres detecciones; se declara en el manuscrito en vez de resolverse en silencio. Se anade el plural «clorofilinas», que sobrevivio en la version 1.0 por no estar en el archivo revisado. El codigo NO sale completo: «clorofilas», «clorofila» y «verde natural 3» se quedan, con la regla de contexto que ya tenian. *(discrepa del Acuerdo)*

## Lo que NO se congeló

`config/acuerdo_colorantes.yaml`, el vocabulario legal de referencia. Que una forma legal no se imprima nunca es un hallazgo, no un error que limpiar.

## Para descongelar

Editar `config/decisiones_dra.yaml`, subir `VERSION` en el script y correr `--aplicar --rehacer`. **Si ya empezó la anotación, descongelar la invalida.**