# Teoría propia: Continuación Bajista con Riesgo Comprimido (CBRC)

**Estado: FALSADA.** Los apartados 1 a 4 se escribieron **antes** de ejecutar
ninguna prueba. El apartado 5, después. Las tres predicciones declaradas
fallaron.

---

## 1. Las cuatro premisas, todas medidas

### P1 — Vender fuerza pierde; vender debilidad gana

La separación más limpia que han producido los datos, sobre 11.000+ operaciones
en 40 perpetuos:

| Naturaleza | Estrategias | Positivas | E[R] medio |
|---|---|---|---|
| **Continuación** (vende debilidad) | 3 | **3 de 3** (todas t>2) | **+0,141** |
| **Fade** (vende fuerza) | 6 | **0 de 6** (todas t<−2) | **−0,111** |

No hay una sola excepción en ninguno de los dos grupos. En perpetuos de cripto,
la reversión a la media en el lado corto no existe como fuente de ventaja.

### P2 — El funding extremo predice subida, no agotamiento

Lo descubrimos al falsar `funding_fade_short`, que era nuestra apuesta principal:

| Barras tras funding en decil superior | Rendimiento | Media general |
|---|---|---|
| 5 | +5,11% | +1,10% |
| 10 | **+10,28%** | +2,32% |

Un funding disparado no marca largos a punto de capitular: marca una tendencia
alcista fuerte. **Es la premisa que más valor tiene, porque nos costó una
hipótesis entera.**

### P3 — La compresión de volatilidad es el mejor punto de entrada

`squeeze_breakdown` es la estrategia más fuerte del catálogo (t=5,12) y la única
invariante de escala. Su ventaja no está en predecir la dirección, sino en
**entrar donde el riesgo es barato**: con la volatilidad comprimida, el stop en
ATR está cerca en términos absolutos, así que el mismo movimiento produce un
R-múltiplo mayor.

### P4 — El contexto estructural filtra el ruido

`pullback_to_ema_short` exige EMA(50) < EMA(200) y funciona (t=5,85).
`squeeze_breakdown` **no tiene filtro de tendencia**: opera cualquier compresión
que se resuelva a la baja, también dentro de mercados alcistas.

---

## 2. La hipótesis

> Un corto tiene ventaja cuando se dan **a la vez** cuatro condiciones: la
> estructura es bajista, el riesgo está barato porque la volatilidad se ha
> comprimido, el gatillo es una **pérdida de nivel** (nunca un rechazo de
> máximo), y **no hay flujo alcista saturado**.

Las dos primeras vienen de combinar lo que ya funciona por separado. La cuarta
es nueva, y es donde está la aportación propia.

### Lo que aporta CBRC frente a lo que ya teníamos

1. **Compresión + estructura, juntas.** `squeeze_breakdown` opera compresiones sin mirar la tendencia; `pullback_to_ema_short` mira la tendencia pero entra en el retroceso, cuando la volatilidad ya se ha expandido. Nadie exige las dos cosas.

2. **El veto de funding: convertir el fracaso en filtro.** Demostramos que el funding extremo positivo predice **subida**. En vez de tirar ese hallazgo con la estrategia que lo produjo, lo usamos al revés: **no abrir cortos cuando el funding está en su decil superior.** No es una señal de entrada, es un veto. Es la única parte del sistema que sale de un experimento fallido nuestro.

### Reglas

| # | Condición | Origen |
|---|---|---|
| 1 | EMA(50) < EMA(200) — estructura bajista confirmada | P4 |
| 2 | Ancho de Bollinger(20) en percentil ≤ 35 de las últimas 120 barras | P3 |
| 3 | Cierre por debajo del mínimo de las 10 barras previas | P1 |
| 4 | **Funding NO en el decil superior de las últimas 90 barras** | **P2, invertida** |
| 5 | Stop 2 ATR, objetivo 4 ATR, máximo 20 barras | — |

La regla 4 se desactiva sola si el activo no trae `funding_rate`: el sistema
sigue siendo operable en mercados sin funding, solo que sin ese veto.

---

## 3. Qué predice esta teoría, y qué la falsaría

Predicciones comprobables, **fijadas antes de medir**:

1. **CBRC bate a `squeeze_breakdown`** en expectativa por operación. Si el filtro de estructura y el veto de flujo aportan algo, tiene que verse aquí.
2. **El veto de funding mejora el resultado.** Si quitarlo no cambia nada, la premisa P2 no es accionable y hay que decirlo.
3. **Opera menos y mejor.** Al exigir cuatro condiciones simultáneas habrá muchas menos entradas; la expectativa por operación debe compensarlo.
4. **Mantiene alfa en régimen alcista**, como las dos que ya pasaron.

**Qué la falsaría:** que CBRC no bata a `squeeze_breakdown`, o que quitar el
veto de funding no empeore el resultado. En el primer caso, la complejidad
añadida no se paga. En el segundo, la aportación propia es decorativa.

---

## 4. Protocolo de validación

El riesgo aquí es evidente: hemos mirado estos datos muchas veces, así que
diseñar sobre ellos y validar sobre ellos sería sobreajuste por construcción.

- Los 40 activos se han partido **60/40 con semilla fija**, y la partición está congelada en `config/holdout_split.json`, commiteada **antes** de ejecutar ninguna prueba.
- **Diseño (24 activos):** ahí se desarrolla y se itera.
- **Reserva (16 activos):** se mira **una sola vez**, al final. Si se mira antes, deja de ser reserva.
- **Se cuentan las iteraciones** sobre el conjunto de diseño y se declaran. Más de 5-10 y el resultado de la reserva pierde validez.

Los resultados van al apartado 5, que se rellena después de ejecutar.


---

## 5. Resultados: la teoría queda falsada

Ejecutado sobre los **24 activos de diseño** (48.612 barras). La reserva no se
tocó — ver apartado 5.4.

### 5.1 Las tres predicciones, contrastadas

| Predicción declarada | Resultado | ¿Se cumple? |
|---|---|---|
| 1. CBRC bate a `squeeze_breakdown` | +0,106 vs **+0,139** | **NO** |
| 2. El veto de funding mejora el resultado | +0,106 con veto, **+0,108 sin él** | **NO** |
| 3. Opera menos y mejor | 545 ops vs 676, y **peor** expectativa | **NO** |

Las tres fallan. Según el criterio de falsación del apartado 3, la teoría no se
sostiene.

### 5.2 Desmontaje por componentes

| Variante | n | E[R] | t |
|---|---|---|---|
| CBRC completa | 545 | +0,106 | 2,24 |
| CBRC sin veto de funding | 553 | +0,108 | 2,29 |
| **CBRC sin filtro de estructura** | 819 | **+0,112** | 2,92 |
| CBRC sin compresión | 844 | +0,078 | 2,06 |
| `squeeze_breakdown` (referencia) | 676 | **+0,139** | 3,21 |

Quitando nuestras dos aportaciones, lo que queda es `squeeze_breakdown`. **CBRC
es `squeeze_breakdown` con dos filtros que no hacen nada.**

### 5.3 Qué sí aprendimos

**La compresión es un mecanismo real, pero binario.** Etiquetando cada operación
por el estado de compresión del día de entrada:

| Estado al entrar | n | E[R] | t |
|---|---|---|---|
| Comprimida (≤ percentil 50) | 794 | **+0,110** | +2,74 |
| Expandida (> percentil 50) | 496 | −0,017 | −0,39 |
| **Diferencia** | | **+0,127 R** | **+2,15** |

Pero **no hay gradiente fino**: por deciles los resultados rebotan sin orden
(+0,126, +0,195, +0,043, +0,272, −0,054...) y la correlación de rangos es
−0,037 (t=−1,34). Afinar el umbral sería ajustar ruido. El filtro binario que ya
teníamos es lo correcto.

**El filtro de estructura no perjudica: no aporta.** Separando las operaciones
de `squeeze_breakdown` según la estructura del día de entrada:

| Estructura al entrar | n | E[R] | t |
|---|---|---|---|
| Bajista (EMA50 < EMA200) | 456 | +0,135 | +2,58 |
| No bajista | 220 | +0,146 | +1,90 |

Diferencia de **0,010 R con t=0,11**: indistinguible. El filtro descarta un
tercio de la muestra sin mejorar la calidad, y perder muestra sin ganar nada
empeora el sistema.

**Implicación que sí es interesante:** la ventaja de `squeeze_breakdown` **no
tiene que ver con la tendencia**. Depende solo del estado de volatilidad. Eso
encaja con que rinda mejor en régimen alcista (+0,224) que bajista (+0,121), lo
que era contraintuitivo hasta ahora.

**Y nuestro mejor hallazgo no es accionable como filtro.** El funding extremo
predice subida —eso está sólidamente medido— pero vetar los cortos en el decil
superior cambia el resultado en −0,002 R. La razón es simple: casi nunca
coinciden. Un funding disparado y una volatilidad comprimida son estados de
mercado incompatibles, así que el veto casi no llega a actuar (545 operaciones
frente a 553 sin él: veta 8 de 553, un 1,4%).

### 5.4 La reserva sigue intacta

**No se ha tocado.** No tenía sentido gastarla: la reserva sirve para confirmar
un candidato que ya ha superado el diseño, y CBRC no lo superó. Mirarla ahora
solo habría destruido su valor para el siguiente intento.

Iteraciones consumidas sobre el conjunto de diseño: **2** (la teoría completa, y
la medición del gradiente de compresión). El presupuesto sigue holgado.

---

## 6. La siguiente hipótesis

El desmontaje deja una pista concreta. Si la ventaja depende del estado de
volatilidad y no de la tendencia, lo que la estrategia está capturando es la
**asimetría de velocidad**: las caídas son más rápidas que las subidas, así que
una expansión de volatilidad desde compresión paga más en el lado corto.

Eso genera una predicción comprobable y distinta de todo lo anterior:

> La ventaja debería ser **mayor en los activos con asimetría negativa más
> pronunciada** (los que caen más rápido de lo que suben), y debería poder
> medirse *antes* de operar, con la asimetría histórica de cada activo.

Es una selección **transversal** —qué activo operar— en vez de otro filtro
temporal. No la hemos probado nunca, usa los 40 activos que ya tenemos, y de
confirmarse daría algo que ninguna estrategia del catálogo tiene: un criterio
para elegir en qué operar y no solo cuándo.
