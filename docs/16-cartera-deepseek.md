# Qué se le puede copiar a una cartera de IA con 90%

El usuario trajo la **DeepSeek Portfolio** de Autopilot (90% desde febrero de
2025) como inspiración. Este documento analiza qué es, por qué ese 90%
probablemente no es lo que parece, y qué parte de su método sí valía la pena
probar — con el resultado de haberlo probado.

**Resultado: la idea estructural que se le copió (selección transversal) falla
en las 36 combinaciones probadas sobre dos universos. Lo que queda en pie de
su método no es la selección, es la disciplina de tener un control declarado.**

---

## 1. Qué es, según su propio white paper

- **Universo**: empresas del S&P 500 más la mayoría de ETF.
- **Puntuación**: un LLM asigna a cada empresa un número de 1 a 100 usando
  noticias de la última semana (unos 70 medios), ~100 variables financieras y
  un informe macro generado también por IA.
- **Construcción**: se toman las 10 mejor puntuadas; otro LLM arma una cartera
  de 15 activos y decide los pesos.
- **Operativa**: tenencia de un mes, rebalanceo mensual completo.
- **Restricciones**: solo largo, sin apalancados, sin inversos, sin
  volatilidad. Objetivo declarado: batir al S&P 500.

## 2. Por qué ese 90% no prueba lo que parece

Medido con nuestros propios datos sobre **la misma ventana** (2025-02 a
2026-09, 1,6 años):

| Activo | Total en la ventana |
|---|---|
| AMD | **+307%** |
| GDX (mineras de oro) | +147% |
| PLTR | +122% |
| SLV (plata) | +106% |
| NVDA | +86% |
| XLK (tecnología) | +61% |
| **SPY (el mercado)** | **+28,7%** |

Una cartera concentrada de 15 activos inclinada a IA, tecnología y metales en
esa ventana llega al 90% **sin ningún acierto de selección**: NVDA, AMD y PLTR
a partes iguales dan ~172%. El 90% es aproximadamente 3× el mercado, lo cual
es compatible con habilidad, pero también con una apuesta sectorial que salió
bien — y 19 meses no bastan para distinguirlas.

Hay además un problema de escaparate: el mismo marketplace aloja varias
carteras de IA (GPT Portfolio, DeepSeek, AI Leaders, AI Alpha Fund, AI World
War III...). Ver la que rindió 90% no dice nada si no se ven todas las que se
lanzaron. Es el mismo sesgo de supervivencia que en `docs/14` fabricó un
Sharpe 1,12 que resultó ser humo.

**Esto no acusa a nadie de nada**: su white paper es transparente sobre el
método y no promete resultados. Es una advertencia sobre qué se puede concluir
de un número aislado.

## 3. Lo que sí merecía probarse: la dimensión transversal

Las catorce estrategias de nuestro catálogo son **temporales**: cada activo se
juzga contra su propio pasado. Ninguna había preguntado nunca lo otro — **de
los 40, cuáles son los mejores comparados entre ellos**.

Esa es la dimensión que usa la cartera DeepSeek (puntuar y quedarse con las
mejores), y es además la familia con más evidencia publicada en finanzas. Que
no estuviera probada era un hueco real.

Se probó su versión mecánica, sin LLM: rankear por retorno pasado, comprar los
N mejores, rebalancear mensualmente (`scripts/momento_transversal.py`), con el
control contra comprar-y-mantener dentro desde el principio.

### 3.1 Resultados

**Cripto (40 activos, control Sharpe 0,83):**

| | Mejor celda | vs control |
|---|---|---|
| Solo largo | Sharpe 0,90 (top 3, 63d) — DD −88,5% | +0,08 |
| Largo + corto | Sharpe 0,37 | −0,46 |

17 de 18 combinaciones quedan por debajo del control. La única que asoma lo
hace por 0,08 con un drawdown del 88%.

**Diversificado (34 clases de activo, control Sharpe 0,50):**

| | Mejor celda | vs control |
|---|---|---|
| Solo largo | Sharpe 0,41 | **−0,09** |
| Largo + corto | Sharpe 0,20 | −0,30 |

**Las 18 combinaciones quedan por debajo del control.** Ninguna excepción.

### 3.2 Qué significa y qué no

36 celdas, dos universos, ni una que bata a su referencia. Como resultado
negativo es limpio.

Pero hay que acotarlo con honestidad: el momento transversal está documentado
sobre **cientos o miles de acciones individuales**, donde se forman deciles.
Nuestros universos tienen 34 y 40 activos, así que "top 3" es una cartera
extremadamente concentrada y ruidosa, no un decil. **Esto refuta que la idea
funcione con los datos que tenemos, no que el fenómeno no exista.**

Probarlo como es debido exigiría el universo de constituyentes del S&P 500 en
cada fecha, incluidas las empresas que salieron del índice — que es
precisamente el dato que `docs/14` señaló como imprescindible y que no
tenemos.

## 4. Lo que sí se adopta de su método

Tres cosas, y ninguna es la selección:

1. **Declarar el control por delante.** Su objetivo escrito es "batir al
   S&P 500". Nosotros llegamos a esa disciplina tarde y a base de tropezar
   (`docs/14`); ellos la tienen en el documento fundacional. Se mantiene como
   norma: ninguna estrategia larga se evalúa contra cero.
2. **Horizonte mensual y tenencia fija.** Menos decisiones que el motor
   diario, menos ruido, menos costes. Es la forma correcta de operar la
   estructura núcleo+freno de `docs/15`, y encaja con que las aportaciones del
   usuario hagan de rebalanceo.
3. **Concentrar en vez de repartir.** `docs/11` midió que 40 criptos
   correlacionadas son 1,7 apuestas. Si repartir no diversifica, concentrar no
   añade tanto riesgo como parece — aunque en este test concentrar tampoco
   añadió retorno.

## 5. Lo que NO se adopta: el LLM puntuando

No por escepticismo sobre la capacidad del modelo, sino por un problema de
verificación que no tiene arreglo técnico: **es imposible reconstruir qué
habría puntuado un LLM en marzo de 2024 con las noticias de esa semana**.
Cualquier backtest de esa parte está o bien limitado a los meses transcurridos
desde que arrancó, o bien contaminado porque el modelo ya sabe cómo acabó la
historia.

Eso deja solo la evidencia hacia delante, y 19 meses de una sola cartera no
distinguen habilidad de suerte. No es una crítica a su enfoque: es la razón
por la que nosotros no podemos copiarlo y llamarlo validado.

## 6. Dónde queda el objetivo del 100%

Esta iteración no acerca. Lo que sí sigue vivo, y con el mejor resultado
medido hasta ahora, es la **adaptación al régimen** encontrada al hilo de
`docs/15`: mover el peso entre núcleo y freno según el mercado esté por encima
o por debajo de su media de 200 días.

| | 2020-2026 | 2022-2026 (sin el ciclo alcista) |
|---|---|---|
| Fijo 60/40 | +53,8% | +14,0% |
| **Dinámico por régimen** | **+87,5%** | **+47,0%** |

Ese es el candidato serio, y está **sin validar**: la regla se eligió mirando
los datos. El siguiente paso no es probar otra familia más, es pre-registrarla
y pasarla por las puertas como cualquier otra — con costes de rotación y la
prueba del *whipsaw* incluidas.
