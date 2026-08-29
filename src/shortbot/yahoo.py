"""Cliente minimo del endpoint de graficos de Yahoo Finance.

``yfinance`` hace un baile de cookies y 'crumb' contra ``fc.yahoo.com`` y
``guce.yahoo.com`` que falla detras de un proxy restrictivo, y ademas usa
impersonacion TLS que el tunel corta. El endpoint v8 de graficos no necesita
nada de eso: basta una cabecera User-Agent normal.

Menos dependencias, menos superficie de fallo y control total sobre los
reintentos, que con Yahoo hacen falta: devuelve 429 con facilidad.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

import pandas as pd

BASE = "https://query2.finance.yahoo.com/v8/finance/chart/"

# Deliberadamente escueto. Una cadena de Chrome completa hace que el borde de
# Yahoo devuelva 429 de forma sistematica -parece que marca como scraper a quien
# se hace pasar por navegador sin serlo-, mientras que este User-Agent minimo
# pasa sin problema. Verificado: con Chrome/120 falla siempre, con esto no.
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}


class YahooError(RuntimeError):
    pass


def _get_json(url: str, intentos: int = 5, espera: float = 1.5) -> dict:
    """Reintenta con espera creciente: Yahoo limita por tasa con agresividad."""
    ultimo = None
    for i in range(intentos):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            ultimo = exc
            if exc.code not in (429, 500, 502, 503):
                raise
        except Exception as exc:                      # reset de conexion, timeout
            ultimo = exc
        time.sleep(espera * (2 ** i))
    raise YahooError(f"Yahoo no respondio tras {intentos} intentos: {ultimo}")


def download(
    symbol: str,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """OHLCV diario de Yahoo. Devuelve DataFrame vacio si no hay datos."""
    p1 = int(pd.Timestamp(start).timestamp())
    p2 = int(pd.Timestamp(end).timestamp()) if end else int(pd.Timestamp.utcnow().timestamp())
    query = urllib.parse.urlencode({
        "period1": p1, "period2": p2, "interval": interval,
        "events": "div,split", "includeAdjustedClose": "true",
    })
    payload = _get_json(f"{BASE}{urllib.parse.quote(symbol)}?{query}")

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise YahooError(f"{symbol}: {chart['error'].get('description', chart['error'])}")
    resultados = chart.get("result") or []
    if not resultados:
        return pd.DataFrame()

    r = resultados[0]
    quote = (r.get("indicators", {}).get("quote") or [{}])[0]
    if not r.get("timestamp") or not quote:
        return pd.DataFrame()

    df = pd.DataFrame({
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("close"),
        "volume": quote.get("volume"),
    }, index=pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_localize(None))

    # Yahoo intercala nulos en dias sin cotizacion (festivos de un mercado que
    # cotiza en otro huso, subastas vacias). Se eliminan: una barra sin precio
    # no es una barra.
    df = df.dropna(subset=["open", "high", "low", "close"])
    df.index = df.index.normalize() if interval.endswith("d") else df.index
    return df[~df.index.duplicated(keep="last")].sort_index()
