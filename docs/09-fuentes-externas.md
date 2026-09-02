# Qué fuentes externas son alcanzables, y desde dónde

**Resultado: el runner de GitHub Actions —donde el bot opera de verdad— tiene
salida general a internet. La sesión de desarrollo no.** Son dos redes
distintas y confundirlas lleva a conclusiones equivocadas sobre qué es
operable en producción.

Sondeo reproducible: `scripts/probar_fuentes_noticias.py`, ejecutado por
`.github/workflows/probar-fuentes.yml`. Primera ejecución: run
[33640641289](https://github.com/IngSanto/ShortTradingBot/actions/runs/33640641289),
2026-09-02.

## 1. Por qué se hizo antes de pre-registrar nada

Con el filtro de aglomeración por activo (`docs/07`) se calibró la rejilla
entera y **después** se descubrió que el funding no se podía refrescar en
vivo. El mecanismo era irrelevante: el dato no llegaba. Este sondeo invierte
ese orden — primero se comprueba si el dato puede llegar, y solo entonces se
pre-registra un mecanismo que dependa de él.

## 2. Las tres respuestas que no son lo mismo

| Veredicto | Qué significa | ¿Tiene arreglo? |
|---|---|---|
| `ALCANZABLE` | El servidor responde HTTP, incluido 401/403 pidiendo clave | Sí: es cuestión de credenciales |
| `GEOBLOQUEADO` | Responde, pero rechaza la IP del runner (451) | No con una clave: es la región |
| `BLOQUEADO` | No hay respuesta HTTP (DNS, timeout, túnel rechazado) | No: no hay ruta de red |

Meter los tres casos en un mismo "no funciona" fue exactamente el error que
hizo parecer que no había vía para el funding.

## 3. Resultados

| Categoría | Fuente | Sesión de desarrollo | Runner de GitHub Actions |
|---|---|---|---|
| control | GitHub API | ALCANZABLE 200 | ALCANZABLE 200 |
| control | example.com | **BLOQUEADO** (túnel 403) | ALCANZABLE 200 |
| control | Binance archivo estático | ALCANZABLE 200 | ALCANZABLE 200 |
| control | Binance API en vivo | GEOBLOQUEADO 451 | **GEOBLOQUEADO 451** |
| macro | Reserva Federal (FOMC) | BLOQUEADO | ALCANZABLE 200 |
| macro | FRED (St. Louis Fed) | BLOQUEADO | ALCANZABLE 400 (sin clave) |
| macro | BLS (IPC de EEUU) | BLOQUEADO | ALCANZABLE 200 |
| macro | ForexFactory (espejo JSON) | BLOQUEADO | ALCANZABLE 200 |
| noticias | CryptoPanic | BLOQUEADO | ALCANZABLE 403 (pide clave) |
| noticias | CoinDesk RSS | BLOQUEADO | ALCANZABLE 200 |
| noticias | Cointelegraph RSS | BLOQUEADO | ALCANZABLE 200 |
| noticias | NewsAPI | BLOQUEADO | ALCANZABLE 401 (pide clave) |
| eventos | DefiLlama | BLOQUEADO | ALCANZABLE 200 |
| eventos | Deribit | BLOQUEADO | ALCANZABLE 200 |
| eventos | CoinGecko | BLOQUEADO | ALCANZABLE 200 |

**14 de 15 alcanzables desde el runner.** La única excepción es la API en
vivo de Binance, y falla igual en las dos redes con el mismo código (451):
no es un cortafuegos nuestro, es Binance rechazando la región. Ese 451
idéntico en ambos lados es la prueba de que el problema del funding nunca
fue de red.

## 4. Qué corrige esto de `docs/07`

`docs/07` concluyó que "no hay vía disponible para mantener el funding fresco
en este sistema". La parte verificada de esa frase sigue en pie: **Binance**
no sirve el dato en vivo a esta región. La generalización implícita —que el
entorno no puede traer datos externos— **es falsa**, y este sondeo la refuta.

Consecuencia honesta: el funding *podría* refrescarse desde otro proveedor
(CoinGecko, DefiLlama y Deribit responden). Eso **no reabre** los filtros de
`docs/07` ni `docs/08`: los dos se descartaron por no cumplir el criterio de
éxito sobre datos históricos, no por la operabilidad. El descarte se sostiene
por sí solo. Lo que sí queda corregido es la premisa de entorno.

## 5. Alcanzable no es lo mismo que backtesteable

El sondeo mide **si el dato llega hoy**, no **si existe histórico para
validarlo**, que es la restricción que de verdad decide qué se puede
pre-registrar:

| Fuente | Histórico para el backtest (2022-2026) |
|---|---|
| FOMC, FRED, BLS | **Profundo y gratuito.** Las fechas son registro público |
| ForexFactory (espejo) | Solo la semana en curso: sirve en vivo, no para validar |
| RSS (CoinDesk, Cointelegraph) | Sin histórico: el feed es una ventana móvil |
| CryptoPanic, NewsAPI | Histórico solo en plan de pago |
| Deribit, DefiLlama | Fechas estructuradas reconstruibles, cobertura por comprobar |

Esto ordena los candidatos sin ambigüedad: **el calendario macro es el único
que tiene a la vez feed en vivo e histórico completo y gratuito**. Las
noticias en texto libre tienen lo primero y no lo segundo — no se pueden
validar con la disciplina del resto del catálogo, por muy accesibles que
estén.

## 6. Qué queda pendiente

Este documento no adopta nada: solo establece qué es posible. El siguiente
paso, si se sigue esta vía, es la pre-registración del mecanismo (qué se veta,
con qué criterio de éxito, fijado antes de calibrar), con el calendario macro
como fuente por las razones de la sección 5.
