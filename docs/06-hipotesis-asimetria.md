# Hipótesis de asimetría: selección de activos por velocidad de caída

**Estado: pre-registrada.** Este documento se escribe **antes** de calcular ninguna
correlación con el resultado de las estrategias. La sección 4 se rellena después.

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

*(pendiente de ejecución)*
