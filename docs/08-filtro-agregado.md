# Filtro de aglomeración agregado (D4-bis): veto por amplitud de mercado

**Estado: NO ADOPTADO.** No cumple el criterio de éxito pre-registrado —
`squeeze_breakdown` pierde entre 20% y 55% de su expectativa en las 10
combinaciones de la rejilla, con mecanismo identificado y verificado
(sección 4.2). Las secciones 1 a 3 se escribieron antes de calibrar nada;
la sección 4, después.

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

### 4.1 La rejilla, en la región más ancha (percentil individual 10%)

| Umbral τ | `squeeze_breakdown` retención / caída E[R] | `pullback_to_ema_short` retención / caída E[R] | Días de stop simultáneo (base 110) |
|---|---|---|---|
| 15% | 65,1% / **+19,5%** | 89,5% / -13,5% | 87 (-23) |
| 20% | 76,2% / **+52,3%** | 96,0% / -7,5% | 94 (-16) |
| 25% | 79,1% / **+54,8%** | 97,0% / -5,6% | 97 (-13) |
| 30% | 84,6% / **+46,2%** | 98,9% / -1,5% | 101 (-9) |
| 40% | 87,9% / **+26,3%** | 99,0% / -1,0% | 102 (-8) |

(caída E[R] en negrita = por encima del 15% permitido; el signo positivo
significa que el E[R] se hunde, no que mejora — es `(base-filtrado)/|base|`)

Al percentil individual 20% el resultado es estrictamente peor en ambas
estrategias (más días vetados por el mismo umbral, sin ninguna ganancia a
cambio) — no aporta una región nueva, así que no se repite aquí.

**Lo que sí funciona, de forma consistente en las 10 combinaciones:** los
días con ≥2 stops simultáneos bajan de 110 a un rango de 87-102 — el
mecanismo reduce el riesgo de cola *correlacionado*, tal como se diseñó
(sección 1). Pero eso no basta: el criterio pide las tres condiciones a la
vez, y **`squeeze_breakdown` no cumple la condición de expectativa en
ninguna de las 10 celdas** — su E[R] cae entre 20% y 55%, muy por encima
del 15% permitido, en toda la rejilla.

### 4.2 Por qué: el filtro le quita a `squeeze_breakdown` exactamente sus
mejores operaciones

Se comprobó directamente si los trades vetados eran mejores o peores que
los que quedaron (percentil 10%, umbral 25%, `squeeze_breakdown`):

| | n | E[R] |
|---|---|---|
| Trades vetados | 291 | **+0,244 R** |
| Trades conservados | 385 | +0,059 R |

Los trades que el filtro bloquea rinden **cuatro veces mejor** que los que
deja pasar. No es ruido: tiene sentido de mecanismo. `squeeze_breakdown`
entra precisamente cuando un activo rompe de una compresión de
volatilidad — y esas rupturas tienden a ocurrir en los mismos días en que
el mercado entero se mueve con fuerza, que es justo cuando la amplitud de
funding extremo sube (muchos activos con el corto masificado a la vez).
El filtro y la ventaja de la estrategia están mirando la **misma
volatilidad de mercado** desde dos ángulos distintos: uno la lee como
riesgo a evitar, la otra como la oportunidad que persigue. Vetar por
amplitud alta no separa el riesgo de la ventaja para esta estrategia — las
elimina juntas.

`pullback_to_ema_short` no tiene este problema (su edge no depende de
rupturas violentas), por eso pasa el criterio ampliamente en la misma
rejilla — pero el criterio, fijado en la sección 3, exige que **ambas**
estrategias lo cumplan.

### 4.3 Balance

**Según el criterio pre-registrado, el filtro NO se adopta.** No por falta
de evidencia — al contrario, el resultado es limpio y consistente en las
10 combinaciones de la rejilla, con un mecanismo identificado y verificado
directamente (4.2), no solo inferido. Es un "no" bien fundamentado, no un
resultado ambiguo.

Lo que se confirma:
- El mecanismo de amplitud **sí** reduce el riesgo de cola correlacionado
  (menos días de stops simultáneos) de forma consistente en toda la
  rejilla — la hipótesis de `docs/07` sección 4.3 sobre eventos de mercado
  entero era correcta en ese sentido.
- Pero el mismo movimiento de mercado que produce esos stops
  correlacionados es, para `squeeze_breakdown`, la fuente de su mejor
  operaciones — vetar por amplitud agregada no distingue entre ambos.
- El peor trade individual (no el agregado por día) no mejora en ninguna
  combinación — el filtro atenúa la frecuencia de sacudidas correlacionadas,
  no la magnitud del peor caso aislado.

No queda una pista nueva que perseguir aquí: el propio mecanismo revela por
qué un veto de amplitud de mercado, aplicado de forma universal a todas las
estrategias, no puede servir a la vez a una que depende de esa volatilidad
y a una que no. Filtrarlo solo para `squeeze_breakdown` no sería calibrar
parámetros de un mecanismo fijo, sería otra hipótesis —y, dado que a esa
estrategia el filtro le quita justo lo que la hace rentable, no hay razón
para pensar que valdría la pena pre-registrarla.
