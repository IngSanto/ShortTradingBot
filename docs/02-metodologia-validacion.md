# Metodología: de la hipótesis al dinero real

Cuatro puertas. Una estrategia solo pasa a la siguiente si supera **todos** los
criterios de la anterior. El objetivo de este proceso no es encontrar estrategias
buenas: es **descartar rápido y barato** las malas, antes de que cuesten dinero.

---

## Puerta 1 — Criba (coste: minutos)

`python scripts/screen_strategies.py`

Pasa todo el catálogo por el mismo aro con costes realistas.

**Se descarta si:**
- Menos de 30 operaciones → sin muestra no hay conclusión, ni buena ni mala.
- Expectativa negativa **con los costes a cero** → si no gana ni en el vacío, no hay nada que optimizar.

**No se promociona por tener buen número.** Esta puerta solo elimina.

---

## Puerta 2 — Robustez (coste: horas)

`python scripts/screen_strategies.py --robustness --regimes`

Aquí es donde mueren las estrategias que parecían buenas.

| Prueba | Criterio para pasar | Qué detecta |
|---|---|---|
| **Meseta de parámetros** | >60% de las combinaciones con expectativa positiva | Sobreajuste. Si solo gana con RSI>90 y pierde con RSI>88, no hay edge: hay una casualidad. |
| **Consistencia entre activos** | `assets_positive` > 0,5 | Una acción afortunada disfrazada de sistema. |
| **t-estadístico** | \|t\| > 2 | Si no, el resultado no se distingue del ruido por bonita que sea la curva. **La meseta no sustituye a esto**: mide que no dependes de un parámetro afortunado, no que el resultado sea real. |
| **Desglose por régimen** | Saber en cuál gana | Un sistema que solo gana en régimen bajista es un **seguro**, no alfa. Es válido, pero hay que dimensionarlo como seguro. |
| **Sensibilidad a costes** | Sigue positiva al doblar slippage y préstamo | Un edge que muere al doblar el slippage no sobrevive al mercado real. |

**Regla dura:** nunca elegir el mejor parámetro de la rejilla. Se elige el
**centro de la meseta**. El máximo de una rejilla es casi siempre ruido.

---

## Puerta 2.5 — Temporalidad cruzada (coste: minutos)

**Añadida tras matar a `squeeze_breakdown`**, que había superado la puerta 2 con
una meseta de parámetros perfecta (27/27 combinaciones positivas) y signo
positivo en todos los sub-periodos.

Si una estrategia captura una regularidad real del mercado, debe dejar rastro
—más débil, pero del mismo signo— al cambiar la temporalidad. Un edge que solo
existe en barras diarias y desaparece en 4h casi siempre es una muestra pequeña
disfrazada de sistema.

**Cómo se aplica:** se reconstruyen las barras desde el dato de origen (1 min o
tick) en al menos dos temporalidades y se compara la expectativa. Los parámetros
se dejan **iguales**: reoptimizarlos para la nueva temporalidad convertiría la
prueba en otro ejercicio de ajuste.

**Se descarta si** el signo se invierte o la expectativa cae a cero en la
temporalidad con más muestra.

**Por qué es tan barata y tan letal:** multiplica la muestra por 5-10 sin
conseguir un solo dato nuevo. `squeeze_breakdown` pasó de +0,393 R (55
operaciones) a −0,012 R (239 operaciones) sin más que cambiar de diario a 4h.

## Puerta 3 — Walk-forward y datos no vistos (coste: días)

Hasta aquí hemos mirado los datos muchas veces, y eso contamina: cada decisión
tomada mirando el histórico completo es sobreajuste encubierto.

1. **Reserva ciega.** Aparta el **último 20%** del histórico *antes de empezar* y no lo mires. Es tu única prueba honesta.
2. **Walk-forward anclado** (`walk_forward_split`): parámetros elegidos solo en `train`, resultado medido solo en `test`.
3. **Criterio:** la expectativa fuera de muestra debe mantenerse por encima del **50% de la de dentro de muestra**. Una degradación mayor significa que estabas ajustando ruido.
4. **Prueba de mercados cruzados:** si funciona en un activo, debe funcionar decentemente en activos parecidos. Si solo funciona en uno, es una anécdota.

**Cuenta las miradas.** Cada vez que ajustas algo mirando el resultado del test,
gastas una parte de su validez. Anota cuántas iteraciones has hecho: si son más
de 5-10, el resultado fuera de muestra ya no es fiable y necesitas datos nuevos.

---

## Puerta 4 — Paper trading en vivo (coste: 2-3 meses, y no se puede acelerar)

El backtest no captura: latencia, rechazos de orden, disponibilidad real de
títulos para tomar prestados, slippage en el momento exacto de tu señal, ni tu
propia reacción a una racha de 8 pérdidas seguidas.

**Duración mínima: 60 sesiones o 50 operaciones**, lo que sea más largo.

**Se compara contra el backtest del mismo periodo**, no contra el histórico:
- Slippage real vs. estimado.
- Nº de señales ejecutadas vs. generadas (las que no se pudieron ejecutar son un coste oculto).
- Coste de préstamo real vs. supuesto.

**Se pasa a real si** la expectativa en vivo está dentro del 50% de la simulada
**y** el número de operaciones ejecutadas es ≥80% de las señales.

---

## Paso a dinero real: escalado gradual

No se pasa de paper a tamaño completo. Se escala por tramos, y cada tramo tiene
que ganarse el siguiente:

| Tramo | Riesgo por operación | Condición para avanzar |
|---|---|---|
| 1 | 0,10% | 30 operaciones dentro de lo esperado |
| 2 | 0,25% | 30 más, drawdown < 2× el simulado |
| 3 | 0,50% | 50 más, sin sorpresas operativas |
| 4 | 1,00% (objetivo) | — |

**Vuelta atrás automática:** si el drawdown supera **1,5× el máximo histórico
simulado**, se baja un tramo. Sin discutirlo, sin excepciones. La regla existe
precisamente para los momentos en que no querrás cumplirla.

---

## Gestión de riesgo específica del corto

Estas reglas no son opcionales; son las que evitan que un solo evento borre la
cuenta:

1. **Riesgo por operación ≤ 1%** del capital hasta el stop.
2. **Filtro de aglomeración obligatorio:** veto si interés corto sobre flotante > 20%, si los días para cubrir > 5, o si el coste de préstamo > 20% anual.
3. **Sin cortos con resultados a menos de 3 sesiones** salvo que la estrategia sea explícitamente de eventos.
4. **Tope de exposición corta agregada** y límite por sector: los cortos correlacionan brutalmente en un rebote de mercado. Diez cortos en tecnología son *una* posición, no diez.
5. **Stop mental de cartera:** si el drawdown mensual supera el umbral, se para el bot y se revisa. Un sistema que no se puede apagar no es un sistema.
6. **Asume que el stop no te protegerá en el hueco.** Dimensiona pensando en la apertura, no en el stop. El motor de este repo ya lo modela así (`test_hueco_en_contra_se_paga_a_la_apertura_no_al_stop`).

---

## Errores que invalidan un backtest (y en los que es fácil caer)

- **Lookahead** — usar el cierre del día para entrar ese mismo día. *El motor entra siempre en la apertura siguiente.*
- **Sesgo de supervivencia** — probar solo con las empresas que hoy existen. Para cortos es **devastador**: las que quebraron eran precisamente los mejores cortos, y son las que faltan de tu muestra.
- **Ignorar el coste de préstamo** — convierte sistemáticamente un sistema perdedor en ganador sobre el papel.
- **Suponer ejecución en valores ilíquidos** — la señal existe; la posibilidad de tomar prestado, no.
- **Optimizar sobre todo el histórico** y presentar ese resultado como esperado.
- **Reciclar la muestra ciega** después de haberla mirado. Una vez vista, ya no es ciega.
