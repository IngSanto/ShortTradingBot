#!/usr/bin/env python3
"""Calibra las dos hipotesis de interes abierto pre-registradas en docs/12.

  oi_deleverage_short   hipotesis nueva: el desapalancamiento en curso
                        continua. Rejilla de 3 percentiles.
  oi_flush_short        ya estaba escrita en el registro desde antes de que
                        existieran los datos. Se evalua TAL CUAL, sin tocar
                        un parametro: una sola comparacion, cero calibracion.

Criterio en dos niveles (docs/12, seccion 5). El primero es el de siempre; el
segundo existe porque docs/11 demostro que pasar las puertas no basta para el
objetivo -una estrategia puede ser valida y no aportar nada a la cartera.

    python scripts/calibrate_oi.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.backtest import ShortBacktester  # noqa: E402
from shortbot.data import cargar_open_interest, load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.strategies import build  # noqa: E402

METRICAS = os.path.join(RAIZ, "data", "metricas")

PERCENTILES = [0.05, 0.10, 0.20]
T_MINIMO = 2.914          # Bonferroni K=14 (docs/12, seccion 0.1)
MIN_ACTIVOS_POSITIVOS = 0.50
MIN_COBERTURA = 0.80      # misma regla que validar_metricas.py
MIN_CELDAS_MESETA = 2     # de 3


def universo(conjunto: str) -> dict[str, pd.DataFrame]:
    """Precio + interes abierto, solo de los activos que pasan la validacion."""
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    activos = {}
    for s in split[conjunto]:
        ruta_m = os.path.join(METRICAS, f"{s}_metrics_1d.csv")
        if not os.path.exists(ruta_m):
            continue
        df = load_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"))
        oi = cargar_open_interest(ruta_m)
        comun = df.loc[oi.index.min():]
        if len(comun) == 0 or oi.reindex(comun.index).notna().mean() < MIN_COBERTURA:
            continue
        df = comun.copy()
        df["open_interest"] = oi.reindex(df.index)
        activos[s] = df
    return activos


def evaluar(nombre: str, activos: dict, cfg, **params) -> dict:
    trozos, positivos = [], 0
    for simbolo, df in activos.items():
        sig = build(nombre, **params).generate_signals(df, None)
        res = ShortBacktester(cfg).run(df, sig)
        if res.trades.empty:
            continue
        t = res.trades.copy()
        t["simbolo"] = simbolo
        trozos.append(t)
        if t["r_multiple"].mean() > 0:
            positivos += 1
    if not trozos:
        return {"n": 0}
    todas = pd.concat(trozos, ignore_index=True)
    r = todas["r_multiple"].dropna()
    # t de una muestra sobre los R-multiples: la misma que uso el catalogo
    # para las doce estrategias anteriores, para que los numeros comparen.
    t_stat = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else 0.0
    return {"n": len(todas), "E[R]": r.mean(), "t": t_stat,
            "activos_positivos": positivos / max(len(trozos), 1),
            "peor_r": r.min(), "trades": todas}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conjunto", choices=["diseno", "reserva"], default="diseno")
    args = p.parse_args()

    activos = universo(args.conjunto)
    cfg = get_market("cripto").config()
    print(f"Conjunto '{args.conjunto}': {len(activos)} activos con interes abierto validado")
    if not activos:
        print("Sin datos suficientes todavia: la descarga no ha terminado.")
        return 1
    print(f"  {', '.join(sorted(activos))}\n")

    filas = []
    for pct in PERCENTILES:
        r = evaluar("oi_deleverage_short", activos, cfg, percentile=pct)
        if r["n"]:
            filas.append({"estrategia": "oi_deleverage_short", "param": f"pct={pct:.0%}",
                          "n": r["n"], "E[R]": round(r["E[R]"], 3), "t": round(r["t"], 2),
                          "act_pos": round(r["activos_positivos"], 2),
                          "peor_r": round(r["peor_r"], 2),
                          "pasa_t": r["t"] >= T_MINIMO,
                          "pasa_activos": r["activos_positivos"] >= MIN_ACTIVOS_POSITIVOS})

    r = evaluar("oi_flush_short", activos, cfg)
    if r["n"]:
        filas.append({"estrategia": "oi_flush_short", "param": "tal cual",
                      "n": r["n"], "E[R]": round(r["E[R]"], 3), "t": round(r["t"], 2),
                      "act_pos": round(r["activos_positivos"], 2),
                      "peor_r": round(r["peor_r"], 2),
                      "pasa_t": r["t"] >= T_MINIMO,
                      "pasa_activos": r["activos_positivos"] >= MIN_ACTIVOS_POSITIVOS})

    if not filas:
        print("Ninguna de las dos genero operaciones.")
        return 1
    tabla = pd.DataFrame(filas)
    print(tabla.to_string(index=False))

    print(f"\nNIVEL 1 (umbral t >= {T_MINIMO}, activos positivos >= {MIN_ACTIVOS_POSITIVOS:.0%}):")
    for est in tabla["estrategia"].unique():
        sub = tabla[tabla["estrategia"] == est]
        celdas = int((sub["pasa_t"] & sub["pasa_activos"]).sum())
        exigidas = MIN_CELDAS_MESETA if est == "oi_deleverage_short" else 1
        veredicto = "PASA" if celdas >= exigidas else "NO PASA"
        print(f"  {est:22s} {celdas} de {len(sub)} celdas cumplen "
              f"(hacen falta {exigidas}) -> {veredicto}")
    print("\nEl nivel 2 (subir el Sharpe de cartera desde 0,46) solo se evalua "
          "si alguna pasa el nivel 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
