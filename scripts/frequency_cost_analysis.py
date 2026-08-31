#!/usr/bin/env python3
"""¿Compensa operar con mucha más frecuencia? El análisis del coste frente al edge.

Motivado por una pregunta directa: si el edge por operación es pequeño pero se
opera muchas veces al día, ¿no debería compensar el volumen? La respuesta corta,
medida aquí con datos propios en tres temporalidades: no, porque el coste fijo
por operación no se encoge con el horizonte, pero el movimiento de precio que se
puede capturar sí (escala con la raíz del tiempo). Cuanto más corto el horizonte,
peor la proporción coste/edge.

    python scripts/frequency_cost_analysis.py

Requiere que existan en data/cripto/ los mismos 10 símbolos en 1d, 4h y 1h
(descargados con fetch_binance_public.py --interval {1d,4h,1h}).
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot import indicators as ind  # noqa: E402
from shortbot.backtest import BacktestConfig, CostModel  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.evaluation import evaluate_universe  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.strategies import build  # noqa: E402

SIMBOLOS = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT",
            "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT"]
BARRAS_DIA = {"1d": 1, "4h": 6, "1h": 24}
PERFIL = get_market("cripto")
COSTE_IDA_VUELTA = 2 * PERFIL.costs.side_cost


def cargar(tf: str) -> dict[str, pd.DataFrame]:
    out = {}
    for s in SIMBOLOS:
        path = f"data/cripto/{s}_{tf}.csv"
        if os.path.exists(path):
            out[s] = load_csv(path)
    return out


def config_para(tf: str, con_friccion: bool) -> BacktestConfig:
    ppy = 365 * BARRAS_DIA[tf]  # el carry es anual: repartirlo mal falsea el resultado
    comm = PERFIL.costs.commission_bps if con_friccion else 0.0
    slip = PERFIL.costs.slippage_bps if con_friccion else 0.0
    return BacktestConfig(risk_per_trade=0.01, costs=CostModel(
        comm, slip, PERFIL.costs.borrow_annual_pct, periods_per_year=ppy))


def main() -> int:
    print("=" * 100)
    print("PARTE 1 — Coste fijo por operación")
    print("=" * 100)
    print(f"Comisión {PERFIL.costs.commission_bps} bps + slippage {PERFIL.costs.slippage_bps} bps "
          f"por lado -> {COSTE_IDA_VUELTA:.3%} de ida y vuelta.")
    print("Esto no cambia con la temporalidad: pagas lo mismo por operar 1 vez al día")
    print("que por operar 1 vez cada hora.\n")

    print("=" * 100)
    print("PARTE 2 — El movimiento de precio SÍ se encoge con el horizonte")
    print("=" * 100)
    print(f"{'tf':>4s} {'ATR mediano':>13s} {'coste/ATR':>11s} {'riesgo=2xATR':>13s} {'coste/riesgo':>13s}")
    for tf in ["1d", "4h", "1h"]:
        uni = cargar(tf)
        if not uni:
            print(f"  {tf}: sin datos, omitido")
            continue
        atrs = pd.concat([(ind.atr(d, 14) / d["close"]).dropna() for d in uni.values()])
        atr_med = float(atrs.median())
        riesgo = 2 * atr_med
        print(f"{tf:>4s} {atr_med:13.3%} {COSTE_IDA_VUELTA/atr_med:10.1%}  "
              f"{riesgo:13.3%} {COSTE_IDA_VUELTA/riesgo:12.1%}")

    print("\n" + "=" * 100)
    print("PARTE 3 — ¿Sobrevive el edge al aumentar la frecuencia? (parámetros SIN escalar)")
    print("=" * 100)
    print(f"{'estrategia':22s} {'tf':>4s} {'n':>6s} {'ops/día*':>9s} "
          f"{'E[R] real':>10s} {'sin fricción':>13s} {'fricción cuesta':>16s}")
    for nombre in ["pullback_to_ema_short", "squeeze_breakdown"]:
        for tf in ["1d", "4h", "1h"]:
            uni = cargar(tf)
            if not uni:
                continue
            dias = len(next(iter(uni.values()))) / BARRAS_DIA[tf]
            real = evaluate_universe(build(nombre), uni, None, config_para(tf, True))
            limpio = evaluate_universe(build(nombre), uni, None, config_para(tf, False))
            if real["trades"] < 5:
                print(f"{nombre:22s} {tf:>4s}   muestra insuficiente ({real['trades']} ops)")
                continue
            print(f"{nombre:22s} {tf:>4s} {real['trades']:6d} {real['trades']/dias:9.3f} "
                  f"{real['expectancy_r']:+10.3f} {limpio['expectancy_r']:+13.3f} "
                  f"{limpio['expectancy_r']-real['expectancy_r']:16.3f}")
        print(f"  (*) operaciones/día sumando los {len(SIMBOLOS)} activos\n")

    print("=" * 100)
    print("CONCLUSIÓN")
    print("=" * 100)
    print("El coste de fricción (comisión+slippage) no cae al operar más seguido: el")
    print("ATR se encoge más rápido que el coste, así que cada operación paga una")
    print("fracción MAYOR de su riesgo en costes fijos cuanto más corto el horizonte.")
    print("Y en los datos: el propio edge (antes de costes) también se degrada al")
    print("acortar el horizonte del patrón. Las dos cosas juntas explican por qué")
    print("'muchas operaciones pequeñas' no compensa aquí sin una fuente de ventaja")
    print("distinta (cobrar el spread como market maker, no perseguir el precio).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
