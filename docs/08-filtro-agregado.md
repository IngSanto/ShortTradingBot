# Filtro de aglomeración agregado (D4-bis): veto por amplitud de mercado

**Estado: EN CALIBRACIÓN.** Las secciones 1 a 3 se escriben ahora, antes de
calcular ningún resultado, siguiendo la misma disciplina que `docs/07`. La
sección 4 se completa después, con lo que salga.

---

## 0. Por qué esto y no otra cosa

`docs/07` descartó el filtro de aglomeración **por activo** (veto si el
funding de *ese* símbolo estaba en su percentil extremo negativo). Falló
porque los peores trades del catálogo no vienen de que un activo concreto
tuviera el corto masificado — vienen de sacudidas que golpean **varios
activos el mismo día** (el caso que disparó todo esto: RUNE, SUI y XLM
tocando stop el mismo 19 de agosto). Un veto por activo no puede anticipar
un evento que es, por naturaleza, de mercado entero.

Esta es esa hipótesis distinta, con su propia pre-registración.

## 1. El problema que ataca

Sigue siendo un **filtro de riesgo, no una estrategia**: nunca genera una
entrada, solo puede vetar entradas nuevas que las estrategias ya querían
abrir. Lo que cambia es la unidad de medida: en vez de mirar el funding de
un activo contra su propio historial, mira **cuántos activos del universo
están simultáneamente en su percentil extremo negativo el mismo día**.

**Mecanismo, fijado antes de calibrar nada:**

> Para cada día, calcular la **amplitud** (`breadth`): la fracción de
> activos del universo de diseño cuyo funding está, ese día, en su propio
> percentil extremo negativo (mismo cálculo por activo que en `docs/07`:
> percentil sobre una ventana móvil de N días). Si esa fracción supera un
> umbral `τ`, vetar **toda** entrada nueva en corto ese día, en **todos**
> los activos y estrategias — no solo en el activo que dispara la señal.

La lógica: cuando una porción grande del universo tiene el lado corto
masificado a la vez, es la firma de un apretón de mercado en marcha (o
inminente), no de un activo aislado. El veto es deliberadamente más brusco
que el de `docs/07` porque el riesgo que ataca también lo es — bloquea por
contexto de mercado, no por condición del activo.

## 2. Qué se calibra y qué NO se calibra

**Se calibra** (parámetros de implementación de un mecanismo ya fijado):
- Umbral de amplitud `τ`: {15%, 20%, 25%, 30%, 40%} del universo de diseño
  simultáneamente en su percentil extremo.
- Percentil individual usado para decidir si UN activo cuenta como
  "masificado" ese día: {10%, 20%}.

**Fijo, no se calibra** (para no repetir el error de re-abrir dimensiones ya
exploradas): la ventana del percentil individual se fija en 90 días — en
`docs/07` percentil y ventana se movieron juntos sin que la ventana
cambiara la conclusión en ningún caso, así que ampliar la rejilla en esa
dimensión otra vez sería gastar comparaciones múltiples sin motivo nuevo.

**No se calibra en absoluto, porque sería otra hipótesis:** que el veto sea
selectivo (solo el activo que "contribuye" a la amplitud) en vez de
universal — la sección 0 ya explica por qué se eligió universal a propósito.

Se reporta la rejilla completa (5 × 2 = 10 combinaciones), no el mejor
punto — mismo criterio de "meseta, no punto aislado" que en `docs/07`.

## 3. Criterio de éxito, fijado ahora

Métricas objetivo, sobre el conjunto de diseño (24 activos), agregando las
dos estrategias aprobadas:

1. **Reduce el riesgo de cola correlacionado**: el número de *días con
   ≥2 stops simultáneos* baja, o el peor trade agregado mejora, de forma
   consistente en la región que cumple (no en un único punto suelto). Esta
   es la métrica que más importa aquí — es literalmente lo que el
   mecanismo dice atacar (sacudidas que golpean varios activos el mismo
   día), a diferencia de `docs/07` donde solo había peor-trade individual.
2. **No destruye la muestra**: conserva al menos el 70% de las operaciones
   originales. Un veto de mercado entero es más contundente que uno por
   activo — más fácil que se coma la muestra sin querer, así que este
   límite importa más aquí que en `docs/07`.
3. **No hunde la expectativa**: el E[R] tras el filtro no cae más de un
   15% respecto al original.

El filtro se adopta si existe una región amplia de la rejilla (no un solo
punto) donde las tres condiciones se cumplen a la vez, para ambas
estrategias. **Si ninguna región cumple, se descarta y se dice así** — iguales
reglas que `docs/07`, no se persigue un punto aislado.

**Limitación conocida de antemano, heredada de `docs/07`:** el funding solo
tiene cobertura real hasta 2026-07-31 (archivo mensual de Binance, sin vía
de refresco en vivo — confirmado bloqueado tanto en desarrollo como en un
runner real de GitHub Actions). La calibración se hace sobre ese tramo. Si
el filtro pasara el criterio, seguiría sin ser operable en producción hasta
que exista una fuente de funding fresca — esto ya se documentó como
consecuencia de `docs/07` y sigue aplicando aquí sin cambios.

## 4. Resultados

_Pendiente._
