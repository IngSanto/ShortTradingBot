#!/usr/bin/env python3
"""Descarga de datos historicos para los tres mercados del plan de validacion.

    python scripts/fetch_data.py --market acciones --start 2010-01-01
    python scripts/fetch_data.py --market futuros
    python scripts/fetch_data.py --market cripto --exchange binanceusdm

Guarda un CSV por simbolo en ``data/<mercado>/``. Para cripto descarga ademas
el historico de funding y lo agrega a diario: es el dato que da sentido a
``funding_fade_short``, la estrategia con mejor tesis del catalogo.

NOTA: requiere salida a internet hacia Yahoo Finance (acciones/futuros) o hacia
el exchange (cripto). En entornos con proxy restrictivo fallara; ejecutalo en
tu maquina.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.markets import MERCADOS, get_market  # noqa: E402

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "data")


def _save(df: pd.DataFrame, market_key: str, symbol: str) -> str:
    outdir = os.path.join(DATA_ROOT, market_key)
    os.makedirs(outdir, exist_ok=True)
    safe = symbol.replace("/", "-").replace(":", "_")
    path = os.path.join(outdir, f"{safe}.csv")
    df.to_csv(path, index_label="date")
    return path


# --------------------------------------------------------------------------- #
# Acciones y futuros (Yahoo Finance)
# --------------------------------------------------------------------------- #

def fetch_yfinance(symbols, start: str, end: str | None, market_key: str) -> list[str]:
    try:
        import yfinance as yf
    except ImportError:
        raise SystemExit("Falta yfinance. Instala: pip install yfinance")

    saved = []
    for symbol in symbols:
        try:
            raw = yf.download(symbol, start=start, end=end, interval="1d",
                              auto_adjust=False, progress=False)
        except Exception as exc:
            print(f"  [x] {symbol}: {type(exc).__name__}: {exc}")
            continue
        if raw is None or raw.empty:
            print(f"  [x] {symbol}: sin datos (simbolo erroneo o red bloqueada)")
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).lower() for c in raw.columns]
        df = raw[["open", "high", "low", "close", "volume"]].dropna()
        path = _save(df, market_key, symbol)
        print(f"  [v] {symbol}: {len(df)} barras -> {path}")
        saved.append(path)
    return saved


# --------------------------------------------------------------------------- #
# Cripto perpetuos (ccxt): OHLCV + historico de funding
# --------------------------------------------------------------------------- #

def _fetch_ohlcv_paged(ex, symbol: str, timeframe: str, since: int, limit: int = 1000):
    rows, cursor = [], since
    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
        if not batch:
            break
        rows += batch
        if len(batch) < limit:
            break
        cursor = batch[-1][0] + 1
        time.sleep(ex.rateLimit / 1000)
    return rows


def _fetch_funding_paged(ex, symbol: str, since: int, limit: int = 1000):
    rows, cursor = [], since
    while True:
        try:
            batch = ex.fetch_funding_rate_history(symbol, since=cursor, limit=limit)
        except Exception as exc:
            print(f"      (funding no disponible: {type(exc).__name__})")
            return []
        if not batch:
            break
        rows += batch
        if len(batch) < limit:
            break
        cursor = batch[-1]["timestamp"] + 1
        time.sleep(ex.rateLimit / 1000)
    return rows


def fetch_ccxt(symbols, start: str, exchange_id: str, timeframe: str) -> list[str]:
    try:
        import ccxt
    except ImportError:
        raise SystemExit("Falta ccxt. Instala: pip install ccxt")

    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    since = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    saved = []

    for symbol in symbols:
        try:
            ohlcv = _fetch_ohlcv_paged(ex, symbol, timeframe, since)
        except Exception as exc:
            print(f"  [x] {symbol}: {type(exc).__name__}: {exc}")
            continue
        if not ohlcv:
            print(f"  [x] {symbol}: sin datos")
            continue

        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None)
        df = df.drop(columns="ts").set_index("date")

        # El funding se cobra cada 8h: se suma para obtener la tasa diaria, que
        # es la unidad en la que razona la estrategia y el modelo de costes.
        funding = _fetch_funding_paged(ex, symbol, since)
        if funding:
            f = pd.DataFrame(funding)
            f["date"] = pd.to_datetime(f["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
            daily = f.set_index("date")["fundingRate"].astype(float).resample("D").sum()
            df["funding_rate"] = daily.reindex(df.index, method="ffill")
            print(f"      funding: {len(f)} registros, media diaria "
                  f"{df['funding_rate'].mean():.5f} "
                  f"({df['funding_rate'].mean() * 365:.1%} anualizado)")

        path = _save(df, "cripto", symbol)
        print(f"  [v] {symbol}: {len(df)} barras -> {path}")
        saved.append(path)
    return saved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", required=True, choices=sorted(MERCADOS),
                    help="Mercado a descargar")
    ap.add_argument("--symbols", nargs="*", help="Sobrescribe el universo sugerido")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--exchange", default="binanceusdm", help="Exchange ccxt (solo cripto)")
    ap.add_argument("--timeframe", default="1d", help="Temporalidad ccxt (solo cripto)")
    args = ap.parse_args()

    profile = get_market(args.market)
    symbols = args.symbols or list(profile.universo_sugerido)

    print(f"\nMercado : {profile.nombre}")
    print(f"Fuente  : {profile.fuente}")
    print(f"Simbolos: {len(symbols)} desde {args.start}\n")

    if args.market == "cripto":
        saved = fetch_ccxt(symbols, args.start, args.exchange, args.timeframe)
    else:
        saved = fetch_yfinance(symbols, args.start, args.end, args.market)

    print(f"\n{len(saved)}/{len(symbols)} simbolos guardados en data/{args.market}/")
    if not saved:
        print("\nNinguna descarga funciono. Causas habituales:")
        print("  - Sin salida a internet (proxy corporativo o entorno aislado).")
        print("  - Simbolo mal escrito (cripto usa 'BTC/USDT:USDT' para perpetuos).")
        return 1

    print(f"\nSiguiente paso:\n"
          f"  python scripts/screen_strategies.py --market {args.market} "
          f'--data "data/{args.market}/*.csv"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
