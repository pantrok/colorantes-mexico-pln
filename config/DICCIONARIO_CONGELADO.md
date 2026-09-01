# Diccionario de colorantes, versión 1.0 — CONGELADO

**Fecha:** 20260901T182830Z  
**sha256:** `30ee4ee19059402c4840ee61c3a38bebdc57e76bf5de5a00e41c12f6d3ed8312`  
**Códigos:** 37 (antes 38) · **Términos:** 206 (antes 217)  
**Veredicto de la revisora:** 2026-09-01, Sulem Yali Granados-Balbuena

## Qué quiere decir que esté congelado

La anotación manual de 600 productos se hace **contra esta versión**. Si el diccionario cambia después, la anotación deja de medir lo que se anotó y hay que rehacerla. Por eso el hash: permite escribir en Métodos «se anotó contra la versión 1.0, sha256 `30ee4ee19059402c…`» y que eso sea comprobable.

`tests/test_congelado.py` falla si el contenido cambia sin subir la versión.

## Regla de decisión aplicada

**P2, la función** — «cuando aparece así, ¿está para dar color?» — la decide la revisora. Es lo que el corpus no puede contestar y por eso se preguntó.

**P1, la atestiguación** — «¿se escribe así en una etiqueta mexicana?» — la decide el corpus. Una forma con detecciones no se borra porque la revisora no la haya visto. Podar por P1 solo cuando el término tiene cero detecciones.

## Cambios aplicados

- fuera del eje  naturales/E101: «riboflavina»
- fuera del eje  naturales/E101: «vitamina b2»
- fuera del eje  naturales/E140: «clorofilina»
- fuera del eje  naturales/E153: «carbon vegetal»
- fuera del eje  naturales/E153: «carbon activado»
- fuera del eje  naturales/E170: «carbonato de calcio»
- codigo vacio    naturales/E170: se elimina
- podado         sinteticos/E160a-i: «betacaroteno sintetico» (0 detecciones)
- podado         sinteticos/E160a-i: «beta-caroteno sintetico» (0 detecciones)
- podado         sinteticos/E160a-i: «caroteno sintetico» (0 detecciones)
- podado         sinteticos/E160a-i: «carotenos sinteticos» (0 detecciones)
- podado         sinteticos/E160e: «beta apo 8 carotenal» (0 detecciones)
- contexto       naturales/E172: requiere_contexto = true
- contexto       naturales/SPIRULINA: requiere_contexto = true

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

- **E101** — riboflavina, vitamina b2: Fortificacion, no color. La revisora anoto «Suplemento» en ambos.
- **E170** — carbonato de calcio: Mineral, no color. Anotado «Mineral».
- **E153** — carbon activado, carbon vegetal: Suplemento en dietas, no color.
- **E140** — clorofilina: P1 = no y P2 = no. Unico punto donde el veredicto discrepa del Acuerdo, que si lista SIN 140 y 141 como colorantes. Tres detecciones; se declara en el manuscrito en vez de resolverse en silencio. *(discrepa del Acuerdo)*

## Lo que NO se congeló

`config/acuerdo_colorantes.yaml`, el vocabulario legal de referencia. Que una forma legal no se imprima nunca es un hallazgo, no un error que limpiar.

## Para descongelar

Editar `config/decisiones_dra.yaml`, subir `VERSION` en el script y correr `--aplicar --rehacer`. **Si ya empezó la anotación, descongelar la invalida.**