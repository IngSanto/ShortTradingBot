#!/usr/bin/env python3
"""Calibra el filtro de aglomeracion AGREGADO (docs/08-filtro-agregado.md).

A diferencia de calibrate_crowding_filter.py (por activo), aqui el veto es
el mismo para todo el universo el mismo dia: se calcula la amplitud de
aglomeracion (fraccion de activos con el corto masificado ese dia) y, si
supera un umbral, se veta la entrada en TODOS los activos ese dia.

Corre la rejilla completa de {percentil individual} x {umbral de amplitud}
sobre las dos estrategias aprobadas, en el conjunto de DISENO, recortado al
tramo con cobertura real de funding (docs/07, seccion 4.1).

    python scripts/calibrate_aggregate_filter.py
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from shortbot.backtest import ShortBacktester  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.risk_filters import (  # noqa: E402
    amplitud_aglomeracion,
    aplicar_veto,
    veto_amplitud_mercado,
)
from shortbot.strategies import build  # noqa: E402

PERCENTILES = [0.10, 0.20]
UMBRALES = [0.15, 0.20, 0.25, 0.30, 0.40]
VENTANA = 90  # fija, no se calibra -ver docs/08, seccion 2
ESTRATEGIAS = ["squeeze_breakdown", "pullback_to_ema_short"]

MIN_RETENCION = 0.70
MAX_CAIDA_ER = 0.15

CORTE_FUNDING = "2026-07-31"

REASONS_STOP = {"stop", "gap_stop"}


def cargar_diseno() -> dict[str, pd.DataFrame]:
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    universo = {s: load_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"))
                for s in split["diseno"]}
    return {s: df.loc[:CORTE_FUNDING] for s, df in universo.items()}


def correr_estrategia(nombre: str, universo: dict, cfg, veto: pd.Series | None) -> pd.DataFrame:
    """Trades de un universo completo para una estrategia, con o sin veto de mercado."""
    trozos = []
    for simbolo, df in universo.items():
        est = build(nombre)
        sig = est.generate_signals(df, None)
        if veto is not None:
            sig = aplicar_veto(sig, df, veto)
        res = ShortBacktester(cfg).run(df, sig)
        if not res.trades.empty:
            t = res.trades.copy()
            t["simbolo"] = simbolo
            trozos.append(t)
    return pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()


def dias_stop_simultaneos(trades: pd.DataFrame) -> int:
    """Numero de fechas donde >=2 trades (de cualquier activo/estrategia) tocan stop."""
    if trades.empty:
        return 0
    stops = trades[trades["reason"].isin(REASONS_STOP)]
    conteo = stops.groupby("exit_date").size()
    return int((conteo >= 2).sum())


def resumen(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"n": 0, "expectancy_r": float("nan"), "peor_r": float("nan")}
    r = trades["r_multiple"].dropna()
    return {"n": len(trades), "expectancy_r": float(r.mean()), "peor_r": float(r.min())}


def main() -> int:
    universo = cargar_diseno()
    print(f"Universo recortado a <= {CORTE_FUNDING} (limite real de cobertura de funding)")
    cfg = get_market("cripto").config()

    base_trades = {nombre: correr_estrategia(nombre, universo, cfg, veto=None) for nombre in ESTRATEGIAS}
    base_todas = pd.concat(base_trades.values(), ignore_index=True)
    base_dias_simult = dias_stop_simultaneos(base_todas)
    print(f"\nSIN FILTRO -- dias con >=2 stops simultaneos (ambas estrategias, todo el universo): "
          f"{base_dias_simult}")
    for nombre, t in base_trades.items():
        b = resumen(t)
        print(f"  {nombre:24s} n={b['n']:3d}  E[R]={b['expectancy_r']:+.3f}  peor={b['peor_r']:+.2f}")

    for pct in PERCENTILES:
        amplitud = amplitud_aglomeracion(universo, lookback=VENTANA, percentile=pct)
        print(f"\n{'='*100}\npercentil individual={pct:.0%}  "
              f"(amplitud maxima observada: {amplitud.max():.1%}, "
              f"media: {amplitud.mean():.1%})\n{'='*100}")

        filas = []
        for umbral in UMBRALES:
            veto = veto_amplitud_mercado(amplitud, umbral)
            dias_vetados = int(veto.sum())
            trozos_todas = []
            for nombre in ESTRATEGIAS:
                t = correr_estrategia(nombre, universo, cfg, veto=veto)
                trozos_todas.append(t)
                base = resumen(base_trades[nombre])
                r = resumen(t)
                if base["n"] == 0:
                    continue
                retencion = r["n"] / base["n"] if r["n"] else 0.0
                caida_er = ((base["expectancy_r"] - r["expectancy_r"]) / abs(base["expectancy_r"])
                           if r["n"] else 1.0)
                filas.append({
                    "umbral": umbral, "estrategia": nombre, "dias_vetados": dias_vetados,
                    "n": r["n"], "retencion": round(retencion, 3),
                    "E[R]": round(r["expectancy_r"], 3) if r["n"] else float("nan"),
                    "caida_ER": round(caida_er, 3),
                    "peor_r": round(r["peor_r"], 3) if r["n"] else float("nan"),
                    "cumple_muestra_y_ER": retencion >= MIN_RETENCION and caida_er <= MAX_CAIDA_ER,
                })
            todas = pd.concat(trozos_todas, ignore_index=True) if trozos_todas else pd.DataFrame()
            dias_simult = dias_stop_simultaneos(todas)
            for f in filas[-len(ESTRATEGIAS):]:
                f["dias_stop_simult"] = dias_simult
                f["mejora_dias_simult"] = base_dias_simult - dias_simult

        tabla = pd.DataFrame(filas)
        print(tabla.to_string(index=False))

        cumple = tabla[tabla["cumple_muestra_y_ER"] & (tabla["mejora_dias_simult"] > 0)]
        n_estrategias_ok = cumple.groupby("umbral")["estrategia"].nunique()
        umbrales_ambas = n_estrategias_ok[n_estrategias_ok == len(ESTRATEGIAS)].index.tolist()
        print(f"\n  Umbrales donde AMBAS estrategias cumplen "
              f"(retencion>={MIN_RETENCION:.0%}, caida E[R]<={MAX_CAIDA_ER:.0%}, "
              f"mejora dias de stop simultaneo): {umbrales_ambas if umbrales_ambas else 'ninguno'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
