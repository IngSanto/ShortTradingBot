# Filtro de aglomeración (D4): veto por funding extremo negativo

**Estado: diseño pre-registrado.** El mecanismo y el criterio de éxito se fijan
en este documento **antes** de correr ninguna calibración. La sección 4 se
rellena después.

---

## 1. El problema que ataca

Es un **filtro de riesgo, no una estrategia**: nunca genera una entrada, solo
puede **vetar** una que la estrategia ya quería abrir. Ataca la asimetría más
peligrosa del corto — el *short squeeze* — con el equivalente en perpetuos del
interés corto / días para cubrir que se usa en acciones (`docs/01`, D4).

**Mecanismo, fijado antes de calibrar nada:**

> Vetar una entrada nueva en corto si el funding del activo está en su
> **percentil extremo negativo** de los últimos N días. Funding muy negativo
> significa que los cortos ya están pagando a los largos: el lado corto de ese
> activo ya está masificado, que es justo el ingrediente de un apretón que
> jugaría en contra de abrir uno más ahí.

Es la traducción directa del D4 original (que pedía datos de acciones que no
existen en perpetuos) al dato equivalente que sí tenemos.

## 2. Qué se calibra y qué NO se calibra

**Se calibra** (parámetros de implementación de un mecanismo ya fijado):
- Percentil de corte: {5%, 10%, 15%, 20%}
- Ventana de cálculo del percentil: {60, 90, 120} días

**No se calibra**, porque cambiarlo sería otra hipótesis, no un ajuste de
parámetros: la dirección del veto (negativo, no positivo — eso ya lo probamos
y falló al revés con `funding_fade_short`), ni qué dato se usa (funding, no
otra cosa).

Se reporta **la rejilla completa**, no el mejor punto: si un solo punto de 12
se ve bien y el resto no, es ruido, no una calibración válida.

## 3. Criterio de éxito, fijado ahora

El filtro se adopta si, sobre el conjunto de diseño (24 activos), para **ambas**
estrategias aprobadas, existe una región amplia de la rejilla (no un solo punto)
donde se cumplen las tres condiciones a la vez:

1. **Reduce el riesgo de cola**: el peor trade mejora, o la frecuencia de
   `gap_stop` baja, de forma consistente (no en un único parámetro suelto).
2. **No destruye la muestra**: conserva al menos el 70% de las operaciones
   originales. Un filtro que veta la mitad de las oportunidades no es un
   ajuste fino, es cambiar de estrategia.
3. **No hunde la expectativa**: el E[R] tras el filtro no cae más de un 15%
   respecto al original. Reducir cola a costa de la expectativa entera no es
   una mejora neta, hay que verlo explícitamente.

**Si ninguna región de la rejilla cumple las tres a la vez, el filtro se
descarta y se dice así.** No se persigue una combinación que solo funcione en
un punto aislado.

## 4. Resultados

*(pendiente de ejecución)*
