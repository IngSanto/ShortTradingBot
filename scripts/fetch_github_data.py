#!/usr/bin/env python3
"""Descarga de datos reales desde repositorios publicos de GitHub.

Via alternativa a ``fetch_data.py`` para entornos donde la politica de red
bloquea los proveedores habituales (Yahoo, Binance, Bybit, Kraken, Stooq) pero
permite ``raw.githubusercontent.com``.

Es peor que un proveedor de verdad -menos activos, sin funding, sin open
interest, con retraso- pero es real, y un dato real imperfecto vale mas que una
serie sintetica perfecta.

    python scripts/fetch_github_data.py --source btc
    python scripts/fetch_github_data.py --source all
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import sys
import urllib.request

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "real")

FUENTES = {
    "btc": {
        "url": ("https://raw.githubusercontent.com/ff137/bitstamp-btcusd-minute-data/"
                "master/data/historical/btcusd_bitstamp_1min_2012-2025.csv.gz"),
        "descripcion": "BTC/USD 1 minuto desde 2012 (Bitstamp)",
        "gzip": True,
    },
    "vix": {
        "url": ("https://raw.githubusercontent.com/datasets/finance-vix/"
                "main/data/vix-daily.csv"),
        "descripcion": "VIX diario OHLC desde 1990",
        "gzip": False,
    },
}


def _descargar(url: str, comprimido: bool) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as resp:
        raw = resp.read()
    return gzip.decompress(raw) if comprimido else raw


def procesar_btc(raw: bytes) -> dict[str, pd.DataFrame]:
    df = pd.read_csv(io.BytesIO(raw))
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_localize(None)
    df = df.set_index("dt").sort_index()

    # Bitstamp rellena los minutos sin operaciones repitiendo el ultimo precio
    # con volumen 0. Si no se quitan, ensucian los maximos y minimos de la barra
    # agregada con niveles en los que nadie opero.
    df = df[df["volume"] > 0]

    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    salidas = {}
    for tf, nombre in [("1D", "BTCUSD_1d"), ("4h", "BTCUSD_4h"), ("1h", "BTCUSD_1h")]:
        bars = df.resample(tf).agg(agg).dropna()
        salidas[nombre] = bars[bars["volume"] > 0]
    return salidas


def procesar_vix(raw: bytes) -> dict[str, pd.DataFrame]:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    # El VIX es un indice: no cotiza volumen. NaN (no cero) para que los filtros
    # de volumen se desactiven en vez de bloquear todas las senales.
    df["volume"] = float("nan")
    return {"VIX_1d": df[["open", "high", "low", "close", "volume"]]}


PROCESADORES = {"btc": procesar_btc, "vix": procesar_vix}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="all", choices=[*FUENTES, "all"])
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    fuentes = list(FUENTES) if args.source == "all" else [args.source]

    for clave in fuentes:
        meta = FUENTES[clave]
        print(f"\n{clave}: {meta['descripcion']}")
        try:
            raw = _descargar(meta["url"], meta["gzip"])
        except Exception as exc:
            print(f"  [x] fallo la descarga: {type(exc).__name__}: {exc}")
            continue
        print(f"  descargado: {len(raw) / 1e6:.1f} MB")

        for nombre, bars in PROCESADORES[clave](raw).items():
            path = os.path.join(DATA_DIR, f"{nombre}.csv")
            bars.to_csv(path, index_label="date")
            print(f"  [v] {nombre}: {len(bars):,} barras "
                  f"({bars.index[0].date()} -> {bars.index[-1].date()})")

    print(f"\nDatos en {os.path.normpath(DATA_DIR)}/")
    print('Siguiente: python scripts/screen_strategies.py --market cripto '
          '--data "data/real/BTCUSD_1d.csv"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
