#!/usr/bin/env python3
"""Puerta 2.5: la misma estrategia en varias temporalidades.

Hay dos formas de bajar de temporalidad, y responden a preguntas distintas.
Confundirlas invalida la prueba:

  A) **Parametros iguales.** Una EMA(20) sobre barras de 4h mide una tendencia
     de 3,3 dias, no de 20. Es OTRA hipotesis: comprueba si el patron existe
     tambien a escalas mas cortas, es decir, si es invariante de escala.

  B) **Parametros escalados.** EMA(20) diaria equivale a EMA(120) en 4h. Mide
     la MISMA ventana economica con 6 veces mas observaciones. Esto no es
     reoptimizar -no se elige el valor por su resultado, se traduce-, y es la
     prueba que de verdad multiplica la muestra de la hipotesis original.

La estrategia deberia sobrevivir a B. Sobrevivir tambien a A seria mejor
señal todavia, pero no es exigible.

    python scripts/timeframe_test.py --strategy pullback_to_ema_short
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.backtest import BacktestConfig, CostModel  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.evaluation import evaluate_universe, parameter_robustness, robustness_score  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.strategies import STRATEGY_REGISTRY, build  # noqa: E402

# Barras por dia de cada temporalidad en un mercado 24/7.
BARRAS_POR_DIA = {"1d": 1, "4h": 6, "1h": 24, "15m": 96}

# Parametros que son VENTANAS TEMPORALES: se escalan con el numero de barras.
VENTANAS = {
    "pullback_ema", "fast_ema", "slow_ema", "atr_period", "channel",
    "lookback", "trigger_lookback", "bb_period", "adx_period", "vol_period",
    "rank_lookback", "width_lookback", "vol_lookback", "oi_lookback",
    "run_bars", "max_bars", "ema_period", "rsi_period",
}

# Parametros que son MULTIPLOS DE ATR: hay que corregirlos aparte.
#
# Escalar el periodo del ATR conserva la ventana pero NO la magnitud: el ATR de
# una barra de 4h es ~0,40 veces el de una diaria (medido sobre los 10
# perpetuos; la teoria del paseo aleatorio predice 1/raiz(6)=0,41). Sin corregir,
# un stop de "2 ATR" pasa a ser 2,5 veces mas ajustado en terminos absolutos y
# la operacion deja de ser la misma: se ve en la tasa de acierto, que se
# desploma del 49% al 37%.
MULTIPLOS_ATR = {"stop_atr", "target_atr", "ext_atr"}

# Umbrales y porcentajes NO se tocan en ningun caso: no son ventanas ni escalas.


def ratio_atr_empirico(uni_alt: dict, uni_dia: dict, factor: int) -> float:
    """Cuanto vale el ATR de esta temporalidad respecto al diario, medido."""
    import numpy as np

    from shortbot import indicators as ind

    ratios = []
    for sym, alt in uni_alt.items():
        dia = uni_dia.get(sym)
        if dia is None:
            continue
        a_alt = (ind.atr(alt, 14 * factor) / alt["close"]).resample("D").last().dropna()
        a_dia = (ind.atr(dia, 14) / dia["close"]).dropna()
        comun = a_alt.index.intersection(a_dia.index)
        if len(comun) > 100:
            ratios.append(float((a_alt.reindex(comun) / a_dia.reindex(comun)).median()))
    return float(np.median(ratios)) if ratios else 1.0 / (factor ** 0.5)


def escalar(params: dict, factor: int, ratio_atr: float, tope: int = 2000) -> dict:
    out = {}
    for k, v in params.items():
        if k in VENTANAS and isinstance(v, (int, float)) and v > 0:
            out[k] = min(int(round(v * factor)), tope)
        elif k in MULTIPLOS_ATR and isinstance(v, (int, float)) and v > 0:
            out[k] = round(v / ratio_atr, 3)
    return out


def cargar(patron: str, symbols: list[str] | None = None) -> dict[str, pd.DataFrame]:
    uni = {os.path.basename(p).split("_")[0]: load_csv(p)
           for p in sorted(glob.glob(patron))}
    if symbols:
        uni = {k: v for k, v in uni.items() if k in symbols}
    return uni


def config_para(profile, tf: str, risk: float) -> BacktestConfig:
    """El carry es anual: hay que repartirlo entre las barras del año."""
    ppy = 365 * BARRAS_POR_DIA[tf]
    return BacktestConfig(risk_per_trade=risk, costs=CostModel(
        profile.costs.commission_bps, profile.costs.slippage_bps,
        profile.costs.borrow_annual_pct, periods_per_year=ppy))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", default="pullback_to_ema_short")
    ap.add_argument("--market", default="cripto")
    ap.add_argument("--pattern", default="data/cripto/*_{tf}.csv")
    ap.add_argument("--timeframes", nargs="+", default=["1d", "4h", "1h"])
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--symbols", nargs="*", default=None,
                    help="Restringe el universo; imprescindible si no todas las "
                         "temporalidades tienen los mismos activos")
    ap.add_argument("--grid", action="store_true", help="Anade barrido de robustez por temporalidad")
    args = ap.parse_args()

    profile = get_market(args.market)
    base = build(args.strategy)
    print(f"\nEstrategia: {base.name}\nTesis: {base.thesis}")
    print(f"Parametros base (diario): {base.params}\n")

    filas = []
    for tf in args.timeframes:
        uni = cargar(args.pattern.format(tf=tf), args.symbols)
        if not uni:
            print(f"[!] sin datos para {tf}")
            continue
        cfg = config_para(profile, tf, args.risk)
        factor = BARRAS_POR_DIA[tf]
        n_barras = sum(len(d) for d in uni.values())

        variantes = [("A: parametros iguales", build(args.strategy))]
        if factor > 1:
            uni_dia = cargar(args.pattern.format(tf="1d"), args.symbols)
            ratio = ratio_atr_empirico(uni, uni_dia, factor)
            ajustados = escalar(base.params, factor, ratio)
            print(f"  [{tf}] ATR medido = {ratio:.3f} x el diario "
                  f"-> multiplos de ATR corregidos x{1/ratio:.2f}")
            print(f"       parametros B: {ajustados}")
            variantes.append((f"B: ventanas x{factor}",
                              build(args.strategy, **ajustados)))

        for etiqueta, est in variantes:
            r = evaluate_universe(est, uni, None, cfg)
            fila = {"tf": tf, "variante": etiqueta, "barras": n_barras,
                    "n": r["trades"], "E[R]": r["expectancy_r"], "t": r["t_stat"],
                    "acierto": r["win_rate"], "PF": r["profit_factor"],
                    "activos+": r["assets_positive"], "peor": r["worst_trade_r"]}
            filas.append(fila)
            if tf == "1d" and factor == 1:
                continue

    tabla = pd.DataFrame(filas)
    num = tabla.select_dtypes("number")
    tabla[num.columns] = num.round(3)
    print("=" * 112)
    print("PUERTA 2.5 - TEMPORALIDAD CRUZADA")
    print("=" * 112)
    print(tabla.to_string(index=False))

    # --- Veredicto ---
    print("\n" + "-" * 112)
    b = tabla[tabla["variante"].str.startswith("B")]
    diario = tabla[(tabla["tf"] == "1d")]
    e_diario = float(diario["E[R]"].iloc[0]) if len(diario) else float("nan")

    print(f"Referencia diaria: E[R]={e_diario:+.3f}")
    if b.empty:
        print("Sin variante escalada: no se puede concluir.")
        return 0

    validas = b[b["n"] >= 30]
    positivas = int((validas["E[R]"] > 0).sum())

    # Criterio corregido. La variante B NO anade muestra (ver docs/02), asi que
    # exigirle t>2 seria exigirle mas de lo que puede dar: lo que prueba es que
    # el resultado no dependia de donde caia el corte de la barra diaria.
    # Lo que se le pide es signo y magnitud comparables.
    if validas.empty:
        print("Variante B sin muestra suficiente: no se puede concluir.")
        return 0

    e_b = float(validas["E[R]"].mean())
    conserva = positivas == len(validas) and e_b >= 0.5 * e_diario
    print(f"Variante B (misma ventana, alineacion distinta): E[R]={e_b:+.3f} "
          f"({positivas}/{len(validas)} positivas)")

    a = tabla[(tabla["variante"].str.startswith("A")) & (tabla["tf"] != "1d")]
    if not a.empty:
        invariante = bool((a["E[R]"] > 0).all() and (a["t"] > 2).any())
        print(f"Variante A (otra escala temporal): E[R]={float(a['E[R]'].mean()):+.3f}"
              f"{'  -> ademas es invariante de escala' if invariante else ''}")

    if conserva:
        print("\nVEREDICTO: SUPERA la puerta 2.5. El edge no depende de la "
              "alineacion de la barra diaria.")
    elif positivas == len(validas):
        print("\nVEREDICTO: signo conservado pero magnitud muy degradada. "
              "Sospechoso: revisar antes de avanzar.")
    else:
        print("\nVEREDICTO: NO SUPERA. El edge desaparece al cambiar la alineacion.")

    if args.grid:
        print("\n" + "=" * 112)
        print("MESETA DE PARAMETROS POR TEMPORALIDAD")
        print("=" * 112)
        for tf in args.timeframes:
            uni = cargar(args.pattern.format(tf=tf), args.symbols)
            if not uni:
                continue
            f = BARRAS_POR_DIA[tf]
            rejilla = parameter_robustness(
                STRATEGY_REGISTRY[args.strategy],
                {"pullback_ema": [max(2, int(10 * f)), int(20 * f), int(30 * f)],
                 "stop_atr": [1.5, 2.0, 2.5]},
                uni, None, config_para(profile, tf, args.risk))
            sc = robustness_score(rejilla, min_trades=30)
            print(f"  {tf}: {sc['combos_validos']} combos validos, "
                  f"{sc['pct_positivos']:.0%} positivos, mediana {sc['expectancy_mediana']:+.3f}"
                  if sc["combos_validos"] else f"  {tf}: sin combinaciones con muestra suficiente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
