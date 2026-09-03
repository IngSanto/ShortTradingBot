#!/usr/bin/env python3
"""Descarga interes abierto y posicionamiento del archivo publico de Binance.

Hasta ahora el sistema solo ha mirado precio y volumen. Estos ficheros traen
algo que la serie de precios NO contiene: cuanta posicion hay abierta, de que
lado esta, y quien la tiene.

    sum_open_interest            contratos abiertos
    sum_open_interest_value      lo mismo en USD
    sum_toptrader_long_short_ratio   ratio de POSICION de las cuentas grandes
    count_toptrader_long_short_ratio ratio de CUENTAS grandes por lado
    count_long_short_ratio       ratio de cuentas, todo el mercado (retail)
    sum_taker_long_short_vol_ratio   flujo agresor: compras contra ventas

La distincion entre `sum_toptrader` y `count_long_short` es la interesante:
una es el dinero grande, la otra es la multitud. Que diverjan es informacion;
el precio solo muestra el resultado neto.

Los ficheros son diarios y de 5 minutos. Se agregan a una fila por dia -el
cierre del dia UTC, mas la media y el maximo del dia- para que casen con las
barras diarias que ya usa el backtest. Los zips se borran segun se procesan:
el historico completo en crudo son varios GB y no aporta nada guardarlo.

    python scripts/fetch_binance_metrics.py [--simbolos BTCUSDT ETHUSDT]
"""

from __future__ import annotations

import argparse
import concurrent.futures as futuros
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SALIDA = os.path.join(RAIZ, "data", "metricas")
URL = ("https://data.binance.vision/data/futures/um/daily/metrics/"
       "{s}/{s}-metrics-{d}.zip")

COLUMNAS = ["sum_open_interest", "sum_open_interest_value",
            "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
            "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]

INICIO_ARCHIVO = "2020-09-01"  # primer dia que publica Binance


def un_dia(simbolo: str, dia: str) -> pd.Series | None:
    """Una fila diaria, o None si ese dia no existe (activo aun no listado)."""
    try:
        with urllib.request.urlopen(URL.format(s=simbolo, d=dia), timeout=30) as r:
            crudo = r.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(crudo)) as z:
            df = pd.read_csv(z.open(z.namelist()[0]))
    except (zipfile.BadZipFile, pd.errors.EmptyDataError):
        return None
    if df.empty or not set(COLUMNAS).issubset(df.columns):
        return None

    df = df.sort_values("create_time")
    fila = {"fecha": dia}
    for c in COLUMNAS:
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        if v.empty:
            continue
        # El cierre es el valor que un sistema que decide al cierre del dia
        # tendria delante; la media y el maximo describen lo que paso dentro.
        fila[f"{c}_cierre"] = float(v.iloc[-1])
        fila[f"{c}_media"] = float(v.mean())
    if "sum_open_interest_cierre" in fila:
        oi = pd.to_numeric(df["sum_open_interest"], errors="coerce").dropna()
        fila["sum_open_interest_max"] = float(oi.max())
        fila["sum_open_interest_min"] = float(oi.min())
    return pd.Series(fila)


def un_simbolo(simbolo: str, dias: list[str], hilos: int) -> int:
    destino = os.path.join(SALIDA, f"{simbolo}_metrics_1d.csv")
    hechos = set()
    if os.path.exists(destino):
        hechos = set(pd.read_csv(destino)["fecha"].astype(str))
    pendientes = [d for d in dias if d not in hechos]
    if not pendientes:
        return 0

    filas = []
    with futuros.ThreadPoolExecutor(max_workers=hilos) as ex:
        for fila in ex.map(lambda d: un_dia(simbolo, d), pendientes):
            if fila is not None:
                filas.append(fila)
    if not filas:
        return 0

    nuevo = pd.DataFrame(filas)
    if hechos:
        nuevo = pd.concat([pd.read_csv(destino), nuevo], ignore_index=True)
    nuevo = nuevo.drop_duplicates("fecha").sort_values("fecha")
    os.makedirs(SALIDA, exist_ok=True)
    nuevo.to_csv(destino, index=False)
    return len(filas)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--simbolos", nargs="*", default=None)
    p.add_argument("--hasta", default=None, help="ultimo dia (por defecto, el de los precios)")
    p.add_argument("--hilos", type=int, default=16)
    args = p.parse_args()

    if args.simbolos:
        simbolos = args.simbolos
    else:
        split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
        simbolos = split["diseno"] + split["reserva"]

    fin = args.hasta or str(pd.Timestamp.utcnow().normalize().date() - pd.Timedelta(days=1))
    dias = [str(d.date()) for d in pd.date_range(INICIO_ARCHIVO, fin, freq="D")]
    print(f"{len(simbolos)} simbolos x {len(dias)} dias, {args.hilos} descargas en paralelo")

    for n, simbolo in enumerate(simbolos, 1):
        traidos = un_simbolo(simbolo, dias, args.hilos)
        destino = os.path.join(SALIDA, f"{simbolo}_metrics_1d.csv")
        total = len(pd.read_csv(destino)) if os.path.exists(destino) else 0
        print(f"  [{n:2d}/{len(simbolos)}] {simbolo:12s} +{traidos:5d} nuevos, {total:5d} dias",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
