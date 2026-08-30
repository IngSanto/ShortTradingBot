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
| [`docs/01-estrategias-candidatas.md`](docs/01-estrategias-candidatas.md) | **Empieza aquí.** Catálogo de 17 estrategias en corto: tesis, reglas exactas, cómo falla cada una y en qué orden probarlas. Incluye cuánto pesa elegir mercado. |
| [`docs/02-metodologia-validacion.md`](docs/02-metodologia-validacion.md) | Las puertas de validación, el escalado a real y la gestión de riesgo específica del corto. |
| [`docs/03-resultados-datos-reales.md`](docs/03-resultados-datos-reales.md) | **Resultados sobre datos reales.** Qué sobrevive, qué se ha descartado y por qué. Se actualiza con cada tanda. |
| [`docs/04-teoria-propia.md`](docs/04-teoria-propia.md) | Teoría propia CBRC: hipótesis, predicciones declaradas y su falsación. |
| [`config/catalogo.json`](config/catalogo.json) | **El catálogo.** Estrategias aprobadas para paper, en observación y descartadas con su motivo. |

## Puesta en marcha

```bash
pip install -r requirements.txt

# 1a. Datos reales desde GitHub (funciona con red restringida)
python scripts/fetch_github_data.py --source all

# 1b. Datos reales desde proveedores (requiere acceso a Yahoo/Binance)
python scripts/fetch_data.py --market cripto   --start 2019-01-01
python scripts/fetch_data.py --market acciones --start 2010-01-01
python scripts/fetch_data.py --market futuros  --start 2010-01-01

# 2. Criba del catálogo con los costes propios de cada mercado
python scripts/screen_strategies.py --market cripto --data "data/cripto/*.csv"

# Sin datos reales funciona igual, con series sintéticas
python scripts/screen_strategies.py --market cripto --regimes --robustness

# 3. Cuánto pesa el mercado, con la estrategia constante
python scripts/compare_markets.py

# 4. Paper trading (puerta 4)
python scripts/paper_run.py --actualizar   # avanza un día
python scripts/paper_run.py --informe      # solo el informe

# Pruebas del motor
python -m pytest tests/ -q
```

Los CSV necesitan columnas `date,open,high,low,close,volume`; en cripto,
además `funding_rate` y `open_interest` si están disponibles.

## Estructura

```
src/shortbot/
  indicators.py     Indicadores vectorizados, sin lookahead
  data.py           Carga de CSV/yfinance + generadores sintéticos (spot y perpetuo)
  markets.py        Perfiles de acciones, cripto y futuros: costes, carry, universo
  backtest.py       Motor short-only barra a barra
  metrics.py        Métricas de evaluación
  evaluation.py     Agregación por universo, robustez, regímenes, walk-forward
  strategies/       12 estrategias implementadas, agrupadas por familia
scripts/
  fetch_data.py          Descarga histórica de los tres mercados (Yahoo/ccxt)
  fetch_github_data.py   Descarga desde repos públicos de GitHub (red restringida)
  screen_strategies.py   Criba comparativa del catálogo completo
  validate.py            Puertas 1, 2, 2.5 y 3 con veredicto por estrategia
  timeframe_test.py      Puerta 2.5: la misma estrategia en varias temporalidades
  regime_test.py         ¿Alfa o solo cobertura? Separa alcista de bajista
  compare_markets.py     Aísla el efecto del mercado sobre la misma estrategia
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

## Decisiones tomadas

- **Solo corto**, sin cobertura larga. Descarta el pairs trading; sube el peso de las estrategias de horizonte corto y de las que leen flujo directamente.
- **Validar en los tres mercados** (acciones, cripto perpetuos, futuros) con los costes propios de cada uno, y decidir con datos.

Una medida ya disponible: la ventaja de cripto sobre acciones para un corto es
**proporcional al tiempo en mercado** (~3,9 bps/día de diferencia de carry). Las
estrategias de tendencia, que aguantan 20-40 sesiones, solo tienen sentido en
cripto o futuros; en acciones el préstamo se come el resultado.

## Estado

- [x] Motor de backtesting short-only con costes realistas
- [x] Catálogo de 12 estrategias implementadas + 5 identificadas
- [x] Perfiles de mercado y cuantificación del efecto del carry
- [x] Criba, robustez paramétrica y desglose por régimen
- [x] Scripts de descarga para los tres mercados
- [x] Datos reales vía GitHub: BTC/USD 2012-2025 (diario, 4h y 1h) y VIX 1990-2026
- [x] Primera criba sobre datos reales: **3 estrategias descartadas, 0 promovidas**
- [ ] **Universo real de los tres mercados** — bloqueado: la política de red de este entorno deniega Yahoo, Binance, Bybit, Kraken, Stooq, CoinGecko, Polygon y Alpha Vantage. Solo `raw.githubusercontent.com` es accesible. Requiere una máquina con salida a internet.
- [ ] Histórico de funding y open interest — sin ellos, las dos estrategias con mejor tesis siguen sin evaluar
- [x] Validación sobre histórico real: **2 de 12 estrategias superan las puertas 1 a 3**
- [x] Catálogo de estrategias aprobadas (`config/catalogo.json`)
- [ ] **Paper trading (puerta 4) — EN CURSO** desde 2026-08-30. `pullback_to_ema_short` al 0,1%, workflow diario. Mínimo 60 sesiones o 50 operaciones.
- [ ] Dinero real con escalado gradual — nada hasta que la puerta 4 termine
- [ ] Operativa real con escalado gradual

> Nada de este repo es asesoramiento financiero. Operar en corto puede generar
> pérdidas superiores al capital invertido.
