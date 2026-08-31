# Hipótesis de asimetría: selección de activos por velocidad de caída

**Estado: FALSADA — en la dirección opuesta a la predicha.** Las secciones 1 a 3
se escribieron antes de calcular ninguna correlación. La sección 4, después.

Origen: al desmontar la teoría propia CBRC (`docs/04-teoria-propia.md`), encontramos
que la ventaja de `squeeze_breakdown` no depende de la estructura de tendencia, solo
del estado de volatilidad. Eso sugiere que lo que captura no es "tendencia bajista",
sino la **asimetría de velocidad**: en muchos activos las caídas son más rápidas y
violentas que las subidas (el "efecto apalancamiento" clásico de las series
financieras). Si eso es cierto, debería poder medirse **antes** de operar, con la
asimetría histórica de cada activo — y sería el primer criterio de selección
transversal (qué activo operar) que tendría el catálogo, frente a los filtros
puramente temporales (cuándo operar) que ya tenemos.

---

## 1. La métrica, fijada de antemano

Para cada activo, sobre su historia diaria completa **antes** del recorte de
diseño/reserva:

- **Sesgo (skewness)** de los retornos logarítmicos diarios. Es la medida estándar
  de este fenómeno en series financieras: sesgo negativo = las caídas extremas
  pesan más que las subidas extremas.
- **Ratio de semivolatilidad**: desviación típica de los retornos negativos dividida
  entre la de los positivos. Un ratio > 1 significa que, cuando el activo cae, lo
  hace con más violencia relativa de la que sube.

Las dos son complementarias: el sesgo pondera la cola extrema; el ratio de
semivolatilidad pondera la dispersión típica. Si ambas apuntan igual, el resultado
es más creíble que con una sola.

**Ninguna de las dos métricas se elige después de ver qué correlaciona mejor.** Se
fijan aquí, se calculan, y el resultado se reporta tal cual salga.

## 2. El activo de prueba

`squeeze_breakdown` es el objetivo principal: es la estrategia cuya ventaja
resultó independiente de la tendencia, que es lo que motivó esta hipótesis.
`pullback_to_ema_short` se reporta también, como contraste — su edge sí venía
ligado a la estructura, así que no hay razón a priori para esperar la misma
relación con la asimetría.

## 3. Método y criterio de falsación

1. Calcular ambas métricas para los **24 activos de diseño** (la reserva de 16
   no se toca).
2. Correlación de Spearman entre cada métrica y la expectativa media en R de esa
   estrategia sobre ese activo (trades agregados por símbolo).
3. Con solo 24 puntos la potencia estadística es baja — hay que ser honestos con
   eso. Criterio de falsación, fijado ahora:
   - **Confirma** si ambas correlaciones tienen el signo predicho (sesgo más
     negativo y ratio de semivolatilidad más alto → mayor expectativa) y al
     menos una de las dos tiene \|t\| > 1.5 (equivalente aproximado a p<0.15
     a dos colas con n=24; el umbral es más laxo que en las pruebas con miles
     de operaciones porque aquí la unidad de observación es el activo, no la
     operación).
   - **Falsada** si el signo no es el predicho en ninguna de las dos, o si
     ambas tienen \|t\| < 1.
   - **No concluyente** en cualquier otro caso — y entonces no se gasta la
     reserva: hace falta más señal antes de arriesgarla.
4. Solo si el resultado en diseño **confirma**, se mide **una vez** sobre los 16
   activos de reserva como confirmación final.

## 4. Resultados

Ejecutado sobre los **24 activos de diseño**. La reserva de 16 no se ha tocado —
el criterio de falsación fijado en la sección 3 dice explícitamente que si no
confirma, no se gasta.

### 4.1 El signo es el contrario en las cuatro comparaciones

| Métrica → estrategia | ρ (Spearman) | t | Signo predicho | ¿Se cumple? |
|---|---|---|---|---|
| Sesgo → `squeeze_breakdown` | +0,337 | +1,68 | negativo | **No** |
| Ratio semivol → `squeeze_breakdown` | −0,278 | −1,36 | positivo | **No** |
| Sesgo → `pullback_to_ema_short` | +0,397 | **+2,03** | negativo | **No** |
| Ratio semivol → `pullback_to_ema_short` | −0,423 | **−2,19** | positivo | **No** |

No es un resultado ambiguo: las cuatro correlaciones tienen el signo contrario al
predicho, y dos de las cuatro superan además el umbral de significancia fijado
(\|t\|>1,5), en la dirección opuesta. Según el criterio de la sección 3
("falsada si el signo no es el predicho en ninguna de las dos"), la hipótesis
queda **falsada con claridad**, no en zona de "no concluyente".

### 4.2 Un dato de contexto que ya avisaba

La distribución de sesgo del propio universo de diseño tiene **media positiva**
(+0,275), no negativa. El "efecto apalancamiento" clásico —las caídas pesan más
que las subidas— es un hecho bien documentado en acciones, pero **no se replica
en este universo de cripto**: aquí las subidas extremas (pumps parabólicos de
activos de baja capitalización) pesan más que las caídas. Construir la hipótesis
sobre una intuición importada de otro mercado, sin comprobar primero si la
premisa de base se sostenía en cripto, fue el error de partida.

### 4.3 Lo que sí queda, sin perseguirlo ahora

Los activos con **sesgo más positivo** —los más propensos a subidas parabólicas
violentas, tipo meme-coin— resultan mejores candidatos para el corto, no peores.
Es una historia coherente y distinta: no es "las caídas son rápidas", es "las
subidas eufóricas se revierten con fuerza", que es literalmente lo que
`squeeze_breakdown` (compresión de volatilidad + ruptura a la baja) está
diseñado para capturar.

**Esto NO se convierte aquí en una hipótesis nueva.** Hacerlo ahora —tras ver
esta correlación— sería exactamente el error que este protocolo existe para
evitar: elegir la métrica después de mirar qué correlaciona. Si se quiere
perseguir, necesita su propia pre-registración, con su propio criterio de
falsación, en un documento nuevo.

### 4.4 Presupuesto de iteraciones

Con esta van **3** iteraciones sobre el conjunto de diseño (CBRC completa, el
gradiente de compresión de CBRC, y esta). Sigue holgado dentro del límite de
5-10 declarado en la metodología.

