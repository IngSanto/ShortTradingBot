# Auditoría de todo lo construido: qué números eran reales

Tras cuatro espejismos detectados en la misma sesión, el usuario pidió revisar
todo lo propuesto buscando más casos. Este documento es esa revisión.

**Resultado: se encontraron dos problemas reales que inflaban la propuesta
final, y se corrigen aquí. La estructura sobrevive; los números bajan.**

| | Lo que se dijo | Lo corregido |
|---|---|---|
| Mezcla 50/50, periodo completo | +51,5% (Sharpe 1,08) | **+42,6%** (Sharpe 0,95) |
| Mezcla 50/50, 2022-2026 | +21,2% | **+19,4%** |

---

## 1. Rebalanceo diario del núcleo: 14 puntos inventados

**El defecto.** El núcleo se calculó como la media diaria de los retornos de
los 40 activos. Eso equivale a **rebalancear los 40 a partes iguales todos los
días**, cosa que nadie hace: implicaría 40 órdenes diarias con sus costes.

Y no es un detalle cosmético — la volatilidad de cripto hace que ese
rebalanceo continuo genere un "bono" grande:

| Núcleo | CAGR | Sharpe |
|---|---|---|
| Rebalanceo diario (lo usado) | **+40,1%** | 0,83 |
| Comprar y olvidar (realista) | **+26,3%** | 0,71 |

**Catorce puntos de CAGR que no existen.** Es el mismo tipo de error que el
Sharpe 1,12 de `docs/14`: un número correcto de una simulación que no
corresponde a nada que se pueda operar.

**Corregido**: todas las cifras de la sección 0 usan ya el núcleo de
comprar-y-olvidar.

## 2. Supervivencia en el universo cripto, con efecto en dos direcciones

**El defecto.** De los 40 activos, **39 llegan hasta hoy**. El universo es "40
perpetuos que existen ahora", así que faltan las monedas que murieron por el
camino — LUNA (mayo 2022), FTT (noviembre 2022) y las altcoins que se fueron a
cero.

**Lo interesante es que sesga en direcciones opuestas:**

- **El núcleo queda inflado.** Un inversor real de 2020 habría comprado
  también las que desaparecieron.
- **El bot queda perjudicado.** Un sistema solo corto habría ganado mucho
  precisamente en esos derrumbes; excluirlos le quita sus mejores operaciones
  posibles.

O sea: **el 26,3% del núcleo sigue siendo optimista, y el 12% del bot es
conservador.** No se puede cuantificar sin los datos de las monedas muertas,
que Binance no publica para pares retirados. Queda declarado como sesgo
conocido y no corregible con lo que hay.

## 3. Contaminación dentro de muestra en la pata del bot

La curva de retornos del bot sale de un backtest sobre **los mismos datos con
los que se diseñaron y calibraron sus estrategias**. La reserva de 16 activos
sirvió para confirmar las estrategias por separado, pero la curva de cartera
mezcla diseño y reserva.

No invalida el resultado —las estrategias sí pasaron una confirmación fuera de
muestra— pero significa que **el 12% del bot no es una expectativa limpia**.
La única cifra limpia sería la del paper trading, que lleva 3 días.

## 4. Lo que se revisó y SÍ estaba bien

Para que la auditoría sea creíble tiene que decir también qué aguantó:

- **El recorte en −95%** que usa el simulador para no producir equities
  negativos: se temía que estuviera tapando ruinas en los casos apalancados.
  No lo hace. El peor día real es −42,8% (núcleo), −30,1% (bot) y −21,4% (la
  mezcla), así que el recorte **no se activa ni una sola vez** en ninguna
  cifra reportada, incluidas las de apalancamiento 1,5 y 2.
- **El filtro de eventos macro** (`docs/10`, adoptado) sí pasó una prueba de
  permutación con 20.000 barajados: p=0,005 en diseño y p=0,022 en reserva
  para `squeeze_breakdown`. Su limitación —que el efecto no replica en
  `pullback_to_ema_short`— ya estaba documentada, no es un hallazgo nuevo.
- **La correlación núcleo-bot** apenas cambia al corregir el núcleo: −0,229
  frente a −0,257. El mecanismo de cobertura no dependía del defecto.
- **El motor bidireccional** tiene la prueba de simetría (un largo sobre una
  serie = un corto sobre la serie reflejada), que es la más exigente posible y
  que ya atrapó dos signos invertidos durante su construcción.

## 5. Los cinco espejismos, y qué los cazó

| Espejismo | Qué parecía | Qué era | Lo cazó |
|---|---|---|---|
| Sharpe 1,12 en acciones (`docs/13`) | Alfa | Beta de 15 ganadores escogidos | Control comprar-y-mantener |
| Interés abierto (`docs/12`) | Señal débil | Ruido: la t bajaba al crecer n | Ver la t contra el tamaño de muestra |
| Momento transversal (`docs/16`) | Familia nueva | 36 celdas bajo su control | Control declarado por delante |
| Peso por régimen (`docs/17`) | +87,5% | Dentro del rango de la suerte | Prueba nula con regímenes aleatorios |
| **Núcleo diario (este)** | **+40,1%** | **+26,3% operable** | **Preguntar si se puede ejecutar** |

Los cinco comparten firma: **un número correcto que responde a una pregunta
distinta de la que importa**. Y cada uno lo cazó un control diferente, lo que
sugiere que la lista de controles no está completa.

## 6. La propuesta, corregida

Con el núcleo realista y costes de rebalanceo mensual:

| Cartera | Periodo completo | Max DD | 2022-2026 |
|---|---|---|---|
| Núcleo solo (comprar y olvidar) | +26,3% | −89,9% | **−25,8%** |
| Bot solo | +12,0% | −84,1% | +31,8% |
| **50/50** | **+42,6%** | **−37,1%** | **+19,4%** |
| 40/60 (más peso al bot) | +39,6% | −45,7% | +25,3% |

La mezcla sigue batiendo a las dos patas por separado y sigue partiendo el
drawdown por la mitad. **El mecanismo aguanta la auditoría; la magnitud no.**

## 7. Qué falta por saber, y no se puede saber con backtest

1. **La correlación en vivo.** Todo depende de `ρ`, medida sobre un backtest
   contaminado. El paper trading lleva **1 operación cerrada y 3 días**.
2. **El coste real de ejecución** del núcleo en cripto (spread, slippage al
   entrar en 40 pares).
3. **Si el bot sigue funcionando** cuando opera con dinero de verdad y no
   contra un fichero CSV.

Ninguna de las tres se resuelve con más análisis. Se resuelven dejando correr
el paper trading y midiendo.
