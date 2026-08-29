#!/usr/bin/env python3
"""Descarga masiva desde el archivo publico de Binance (data.binance.vision).

Es la mejor fuente gratuita para cripto y la unica accesible que trae **funding
rate**, el dato que da sentido a ``funding_fade_short``. No necesita clave de
API ni cuenta: son ficheros ZIP mensuales servidos estaticamente.

    python scripts/fetch_binance_public.py --symbols BTCUSDT ETHUSDT --start 2020-01

Descarga, por simbolo:
  - klines (OHLCV) del perpetuo USD-M
  - fundingRate, agregado a diario y unido a las barras

El resultado va a ``data/cripto/`` en el formato que espera el resto del
proyecto, con ``funding_rate`` ya incorporado.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date

import pandas as pd

BASE = "https://data.binance.vision/data/futures/um/monthly"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cripto")

KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]


def _meses(start: str, end: str | None) -> list[str]:
    inicio = pd.Period(start, freq="M")
    fin = pd.Period(end, freq="M") if end else pd.Period(date.today(), freq="M") - 1
    return [str(p) for p in pd.period_range(inicio, fin, freq="M")]


def _descargar_zip(url: str) -> pd.DataFrame | None:
    """Devuelve None si el mes no existe (404), que es normal en los extremos."""
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        nombre = zf.namelist()[0]
        with zf.open(nombre) as fh:
            # Algunos meses traen cabecera y otros no: se detecta por la
            # primera celda, que en los ficheros con datos es un timestamp.
            primera = fh.readline().decode("utf-8", "replace")
        with zf.open(nombre) as fh:
            tiene_cabecera = not primera.split(",")[0].strip().strip('"').isdigit()
            return pd.read_csv(fh, header=0 if tiene_cabecera else None)


def descargar_klines(symbol: str, interval: str, meses: list[str]) -> pd.DataFrame:
    trozos = []
    for mes in meses:
        url = f"{BASE}/klines/{symbol}/{interval}/{symbol}-{interval}-{mes}.zip"
        df = _descargar_zip(url)
        if df is None:
            continue
        df.columns = KLINE_COLS[:len(df.columns)]
        trozos.append(df)
        print(f"    klines {mes}: {len(df)} barras")
    if not trozos:
        return pd.DataFrame()

    out = pd.concat(trozos, ignore_index=True)
    # Binance cambio de milisegundos a microsegundos en 2025: se normaliza por
    # magnitud en vez de por fecha, que es mas robusto ante nuevos cambios.
    ts = out["open_time"].astype("int64")
    unidad = "us" if ts.iloc[0] > 1e15 else "ms"
    out["date"] = pd.to_datetime(ts, unit=unidad, utc=True).dt.tz_localize(None)
    out = out.set_index("date").sort_index()
    return out[["open", "high", "low", "close", "volume"]].astype(float)


def descargar_funding(symbol: str, meses: list[str]) -> pd.Series:
    trozos = []
    for mes in meses:
        url = f"{BASE}/fundingRate/{symbol}/{symbol}-fundingRate-{mes}.zip"
        df = _descargar_zip(url)
        if df is None:
            continue
        trozos.append(df)
    if not trozos:
        return pd.Series(dtype=float)

    out = pd.concat(trozos, ignore_index=True)
    out.columns = [str(c).strip().lower() for c in out.columns]
    col_ts = next((c for c in out.columns if "time" in c), out.columns[0])
    col_tasa = next((c for c in out.columns if "rate" in c), out.columns[-1])

    ts = out[col_ts].astype("int64")
    unidad = "us" if ts.iloc[0] > 1e15 else "ms"
    out["date"] = pd.to_datetime(ts, unit=unidad, utc=True).dt.tz_localize(None)
    # El funding se liquida cada 8h: se suma para obtener la tasa diaria, que es
    # la unidad en la que razonan la estrategia y el modelo de costes.
    # min_count=1 es imprescindible: sin el, resample().sum() devuelve 0 para
    # los dias SIN registros, y un hueco de datos se convierte en un "funding
    # cero" perfectamente creible que la estrategia leeria como dato real.
    # BNBUSDT tenia asi 743 dias falsos a cero de 2.364.
    return out.set_index("date")[col_tasa].astype(float).resample("D").sum(min_count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="+",
                    default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
                             "XRPUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
                             "ADAUSDT", "LTCUSDT"])
    ap.add_argument("--interval", default="1d", help="1d, 4h, 1h, 15m...")
    ap.add_argument("--start", default="2020-01", help="Mes inicial YYYY-MM")
    ap.add_argument("--end", default=None, help="Mes final YYYY-MM")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    meses = _meses(args.start, args.end)
    print(f"\n{len(args.symbols)} simbolos x {len(meses)} meses ({meses[0]} -> {meses[-1]})")

    guardados = 0
    for symbol in args.symbols:
        print(f"\n{symbol}")
        try:
            bars = descargar_klines(symbol, args.interval, meses)
        except Exception as exc:
            print(f"  [x] {type(exc).__name__}: {exc}")
            continue
        if bars.empty:
            print("  [x] sin datos")
            continue

        try:
            funding = descargar_funding(symbol, meses)
        except Exception as exc:
            print(f"  [!] funding no disponible ({type(exc).__name__}); se guarda sin el")
            funding = pd.Series(dtype=float)

        if not funding.empty:
            # ffill con limite: arrastrar el ultimo funding conocido un par de
            # dias es razonable, pero rellenar un hueco de meses inventaria un
            # dato. Lo que quede en NaN desactiva la estrategia esas barras.
            bars["funding_rate"] = funding.reindex(bars.index).ffill(limit=2)
            cobertura = bars["funding_rate"].notna().mean()
            if cobertura < 0.95:
                print(f"  [!] funding solo cubre el {cobertura:.0%} de las barras")
            media = bars["funding_rate"].mean(skipna=True)
            print(f"  funding: media diaria {media:.5f} ({media * 365:+.1%} anualizado)")
            if media > 0:
                print("           positivo -> los largos pagan: el corto COBRA carry")

        path = os.path.join(DATA_DIR, f"{symbol}_{args.interval}.csv")
        bars.to_csv(path, index_label="date")
        print(f"  [v] {len(bars):,} barras -> {os.path.normpath(path)}")
        guardados += 1

    print(f"\n{guardados}/{len(args.symbols)} simbolos guardados.")
    if guardados:
        print('\nSiguiente:\n  python scripts/screen_strategies.py --market cripto '
              f'--data "data/cripto/*_{args.interval}.csv" --robustness')
    else:
        print("\nNada descargado. Si el entorno bloquea data.binance.vision, "
              "hay que anadirlo a la lista de dominios permitidos.")
    return 0 if guardados else 1


if __name__ == "__main__":
    raise SystemExit(main())
