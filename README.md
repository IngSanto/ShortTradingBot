# ShortTradingBot

Laboratorio para diseñar, validar y (solo después) operar estrategias de trading
**en corto** sobre gráficas de mercados específicos.

La premisa del proyecto: la mayoría de las estrategias que parecen funcionar no
funcionan. Este repo está construido para **descartarlas rápido y barato**, y
para que lo que sobreviva llegue al dinero real habiendo pasado por cuatro
filtros, no por una corazonada.

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/01-estrategias-candidatas.md`](docs/01-estrategias-candidatas.md) | **Empieza aquí.** Catálogo de 15 estrategias en corto: tesis, reglas exactas, cómo falla cada una y cuáles priorizar. |
| [`docs/02-metodologia-validacion.md`](docs/02-metodologia-validacion.md) | Las cuatro puertas de validación, el escalado a real y la gestión de riesgo específica del corto. |

## Puesta en marcha

```bash
pip install -r requirements.txt

# Criba de todo el catálogo (datos sintéticos)
python scripts/screen_strategies.py

# Con desglose por régimen y barrido de robustez
python scripts/screen_strategies.py --regimes --robustness

# Con tus propios datos
python scripts/screen_strategies.py --data "data/*.csv"

# Pruebas del motor
python -m pytest tests/ -q
```

Los CSV necesitan columnas `date,open,high,low,close,volume`.

## Estructura

```
src/shortbot/
  indicators.py     Indicadores vectorizados, sin lookahead
  data.py           Carga de CSV/yfinance + generador sintético con regímenes
  backtest.py       Motor short-only barra a barra
  metrics.py        Métricas de evaluación
  evaluation.py     Agregación por universo, robustez, regímenes, walk-forward
  strategies/       10 estrategias implementadas, agrupadas por familia
scripts/
  screen_strategies.py   Criba comparativa del catálogo completo
tests/              Pruebas de que el motor no se engaña a sí mismo
```

## Qué hace honesto a este motor

Un backtest de cortos es fácil de falsear sin querer. Estas cuatro decisiones son
las que evitan que los resultados sean publicidad:

1. **Sin lookahead.** La señal se calcula al cierre de `t`; la orden se ejecuta en la apertura de `t+1`.
2. **Los huecos se pagan.** Si la apertura ya supera el stop —el escenario típico de un *short squeeze*— el fill es a esa apertura, no al stop. Un corto puede perder 10R en una sesión, y el motor lo refleja.
3. **El corto cuesta dinero cada día.** Comisión, slippage y coste de préstamo/funding proporcional al tiempo en mercado.
4. **No fabrica alfa.** Un test comprueba que entradas aleatorias sobre una serie sin deriva y sin costes dan expectativa estadísticamente nula.

Sobre datos sintéticos todas las estrategias dan expectativa negativa. Es el
resultado correcto: un paseo aleatorio no contiene estructura explotable. Esa
tabla valida **el código**, no el *edge*.

## Estado

- [x] Motor de backtesting short-only con costes realistas
- [x] Catálogo de 10 estrategias implementadas + 5 identificadas pendientes de datos
- [x] Criba, robustez paramétrica y desglose por régimen
- [ ] Conexión a datos reales (proveedor por decidir)
- [ ] Validación walk-forward sobre histórico real
- [ ] Paper trading
- [ ] Operativa real con escalado gradual

> Nada de este repo es asesoramiento financiero. Operar en corto puede generar
> pérdidas superiores al capital invertido.
