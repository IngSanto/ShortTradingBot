#!/usr/bin/env python3
"""Descarga un universo diseñado para ser VARIADO, no para haber ganado.

`docs/13` dejo dos problemas medidos en el universo de acciones que habia:

  1. **Sesgo de seleccion.** Eran 15 nombres escogidos a mano -AAPL, NVDA,
     TSLA, META, PLTR...- que resultan ser los ganadores de la decada.
     Comprarlos y no hacer nada rendia mas que la estrategia. Cualquier cosa
     larga sobre esa cesta luce bien, y no significa nada.
  2. **Poca variedad real.** 40 criptos con correlacion 0,56 equivalen a 1,7
     apuestas independientes, no a 40.

Este universo ataca las dos cosas a la vez usando indices de clase de activo
en vez de valores sueltos:

  - **No hay supervivencia que sesgar.** Un indice sectorial no desaparece
    cuando a sus componentes les va mal: los sustituye. XLE existia en 2014
    antes del desplome del petroleo y sigue existiendo; una accion energetica
    que quebro no estaria en la lista de hoy.
  - **La variedad es estructural, no estadistica.** Bonos, materias primas,
    divisas y renta variable no se mueven juntos por como estan construidos,
    no porque la muestra haya salido asi.

Fuente: API publica de graficos de Yahoo Finance, que responde con cabecera de
navegador (con la de urllib devuelve 429).

    python scripts/fetch_universo_diversificado.py
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SALIDA = os.path.join(RAIZ, "data", "diversificado")
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{t}"
       "?period1={p1}&period2={p2}&interval=1d")
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# La agrupacion no es decorativa: es la hipotesis de diversificacion. Si al
# medir la correlacion los grupos no se separan, este universo no vale mas que
# el anterior y hay que decirlo.
UNIVERSO = {
    "renta_variable_sector": ["XLE", "XLF", "XLK", "XLV", "XLI", "XLP", "XLU", "XLB", "XLY"],
    "renta_variable_region": ["SPY", "IWM", "EFA", "EEM", "EWJ", "FXI"],
    "bonos":                 ["TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "EMB"],
    "materias_primas":       ["GLD", "SLV", "USO", "UNG", "DBA", "DBB", "GDX"],
    "divisas":               ["UUP", "FXE", "FXY"],
    "inmobiliario":          ["VNQ", "IYR"],
}


def descargar(ticker: str, desde: str, hasta: str, intentos: int = 4) -> pd.DataFrame | None:
    p1 = int(pd.Timestamp(desde).timestamp())
    p2 = int(pd.Timestamp(hasta).timestamp())
    peticion = urllib.request.Request(URL.format(t=ticker, p1=p1, p2=p2),
                                      headers={"User-Agent": AGENTE})
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(peticion, timeout=30) as r:
                datos = json.loads(r.read())
            break
        except Exception:  # noqa: BLE001 - 429 y cortes de conexion son normales aqui
            time.sleep(2 ** intento)
    else:
        return None

    res = (datos.get("chart") or {}).get("result")
    if not res:
        return None
    r0 = res[0]
    q = r0["indicators"]["quote"][0]
    df = pd.DataFrame({
        "date": pd.to_datetime(r0["timestamp"], unit="s").normalize(),
        "open": q["open"], "high": q["high"], "low": q["low"],
        "close": q["close"], "volume": q["volume"],
    }).dropna(subset=["open", "high", "low", "close"])
    return df if len(df) > 250 else None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", default="2010-01-01")
    p.add_argument("--hasta", default=str(pd.Timestamp.utcnow().date()))
    args = p.parse_args()

    os.makedirs(SALIDA, exist_ok=True)
    fallos = []
    for grupo, tickers in UNIVERSO.items():
        for t in tickers:
            destino = os.path.join(SALIDA, f"{t}.csv")
            if os.path.exists(destino):
                print(f"  {grupo:24s} {t:6s} ya estaba", flush=True)
                continue
            df = descargar(t, args.desde, args.hasta)
            if df is None:
                fallos.append(t)
                print(f"  {grupo:24s} {t:6s} FALLO", flush=True)
                continue
            df.to_csv(destino, index=False)
            print(f"  {grupo:24s} {t:6s} {len(df):5d} barras "
                  f"({df['date'].min().date()} -> {df['date'].max().date()})", flush=True)
            time.sleep(0.4)   # el endpoint devuelve 429 si se le aprieta

    hechos = len([f for f in os.listdir(SALIDA) if f.endswith(".csv")])
    print(f"\n{hechos} activos en {os.path.relpath(SALIDA, RAIZ)}"
          f"{f' | fallaron: {fallos}' if fallos else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
