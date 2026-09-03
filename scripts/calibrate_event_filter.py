#!/usr/bin/env python3
"""Calibra el filtro de eventos macro pre-registrado en docs/10.

Corre la rejilla de 5 ventanas (V0..V4) sobre las dos estrategias aprobadas,
en el conjunto de DISENO y en el periodo completo -a diferencia de docs/07 y
docs/08, el calendario macro tiene historia publica entera, asi que aqui no
hay recorte de muestra.

Reporta las seis condiciones del criterio (docs/10, seccion 4) y los dos
diagnosticos descriptivos de la seccion 4.1, que NO seleccionan.

    python scripts/calibrate_event_filter.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.backtest import ShortBacktester  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.risk_filters import (  # noqa: E402
    aplicar_veto,
    ventana_eventos,
    veto_evento_macro,
)
from shortbot.strategies import build  # noqa: E402

# Misma definicion de riesgo de cola correlacionado que docs/08, importada y
# no recopiada: si las dos difirieran, la linea base de 110 dias dejaria de
# ser comparable entre los dos filtros.
from calibrate_aggregate_filter import dias_stop_simultaneos  # noqa: E402

# (nombre, dias_antes, dias_despues) -- docs/10, seccion 2
VENTANAS = [
    ("V0  {T}", 0, 0),
    ("V1  {T-1,T}", 1, 0),
    ("V2  {T,T+1}", 0, 1),
    ("V3  {T-1,T,T+1}", 1, 1),
    ("V4  {T-2..T+1}", 2, 1),
]

ESTRATEGIAS = ["squeeze_breakdown", "pullback_to_ema_short"]

MIN_RETENCION = 0.85   # condicion 2
MAX_CAIDA_ER = 0.15    # condicion 3
MIN_VENTANAS_OK = 3    # condicion 6: meseta, no punto

CALENDARIO = os.path.join(RAIZ, "data", "eventos", "calendario_macro.csv")

# Fechas que un sistema en vivo NO habria conocido con antelacion: la reunion
# de emergencia del 15-mar-2020 (convocada el mismo dia) y los IPC que el
# cierre del gobierno de 2025 movio o cancelo. Usarlas es un look-ahead real
# -pequeño, 3 de 132- y por eso existe la opcion de correr sin ellas.
NO_PROGRAMADOS = ["2020-03-15", "2025-10-24", "2025-12-18"]


def cargar_universo(conjunto: str) -> dict[str, pd.DataFrame]:
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    return {s: load_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"))
            for s in split[conjunto]}


def correr_estrategia(nombre: str, universo: dict, cfg, ventana: tuple | None) -> pd.DataFrame:
    trozos = []
    for simbolo, df in universo.items():
        est = build(nombre)
        sig = est.generate_signals(df, None)
        if ventana is not None:
            antes, despues, fechas = ventana
            veto = veto_evento_macro(df.index, fechas, antes, despues,
                                     retraso_entrada=cfg.entry_delay_bars)
            sig = aplicar_veto(sig, df, veto)
        res = ShortBacktester(cfg).run(df, sig)
        if not res.trades.empty:
            t = res.trades.copy()
            t["simbolo"] = simbolo
            trozos.append(t)
    return pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()


def resumen(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"n": 0, "expectancy_r": float("nan"), "peor_r": float("nan")}
    r = trades["r_multiple"].dropna()
    return {"n": len(trades), "expectancy_r": float(r.mean()), "peor_r": float(r.min())}


def particion_mecanismo(base: pd.DataFrame, fechas, antes: int, despues: int,
                        indice: pd.DatetimeIndex) -> tuple[dict, dict]:
    """Condicion 4: E[R] de los trades que el veto quitaria vs los que deja.

    Se parten los trades del backtest SIN filtro segun si su entrada cae en la
    ventana. Es la comparacion directa del mecanismo -la misma que en docs/08
    seccion 4.2, pero aqui comprometida de antemano.
    """
    if base.empty:
        return {"n": 0}, {"n": 0}
    ventana = ventana_eventos(indice, fechas, antes, despues)
    dentro = base["entry_date"].isin(set(indice[ventana]))
    return resumen(base[dentro]), resumen(base[~dentro])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conjunto", choices=["diseno", "reserva"], default="diseno",
                   help="reserva = confirmacion fuera de muestra, se corre UNA vez")
    p.add_argument("--retraso", type=int, default=None,
                   help="barras extra entre señal y entrada (el paper diario usa 1)")
    p.add_argument("--excluir-no-programados", action="store_true",
                   help=f"quita {NO_PROGRAMADOS}: eventos que no se sabian de antemano")
    args = p.parse_args()

    cal = pd.read_csv(CALENDARIO)
    if args.excluir_no_programados:
        cal = cal[~cal["fecha"].isin(NO_PROGRAMADOS)]
    fechas = list(cal["fecha"])
    print(f"Calendario: {len(fechas)} eventos ({cal['tipo'].value_counts().to_dict()}), "
          f"{cal['fecha'].min()} -> {cal['fecha'].max()}"
          f"{'  [sin los no programados]' if args.excluir_no_programados else ''}")

    universo = cargar_universo(args.conjunto)
    cfg = get_market("cripto").config()
    if args.retraso is not None:
        cfg = replace(cfg, entry_delay_bars=args.retraso)
    # Union de indices: usar el de un solo activo dejaria fuera fechas que
    # existen en otros, y la particion del mecanismo las contaria como si
    # cayeran fuera de la ventana.
    indice = universo[next(iter(universo))].index
    for df in universo.values():
        indice = indice.union(df.index)
    print(f"Conjunto '{args.conjunto}': {len(universo)} activos, periodo completo, "
          f"retraso de entrada = {cfg.entry_delay_bars}\n")

    base_trades = {n: correr_estrategia(n, universo, cfg, None) for n in ESTRATEGIAS}
    base_todas = pd.concat(base_trades.values(), ignore_index=True)
    base_dias = dias_stop_simultaneos(base_todas)
    print(f"SIN FILTRO -- dias con >=2 stops simultaneos: {base_dias}")
    for n, t in base_trades.items():
        b = resumen(t)
        print(f"  {n:24s} n={b['n']:4d}  E[R]={b['expectancy_r']:+.3f}  peor={b['peor_r']:+.2f}")

    filas, veredictos = [], {}
    for etiqueta, antes, despues in VENTANAS:
        veto_dias = int(ventana_eventos(indice, fechas, antes, despues).sum())
        trozos, cumple_ambas = [], True
        for nombre in ESTRATEGIAS:
            t = correr_estrategia(nombre, universo, cfg, (antes, despues, fechas))
            trozos.append(t)
            base, r = resumen(base_trades[nombre]), resumen(t)
            ret = r["n"] / base["n"] if base["n"] else 0.0
            caida = ((base["expectancy_r"] - r["expectancy_r"]) / abs(base["expectancy_r"])
                     if r["n"] else 1.0)
            vetados, conservados = particion_mecanismo(
                base_trades[nombre], fechas, antes, despues, indice)
            mecanismo_ok = (vetados["n"] == 0
                            or vetados["expectancy_r"] <= conservados["expectancy_r"])
            ok = ret >= MIN_RETENCION and caida <= MAX_CAIDA_ER and mecanismo_ok
            cumple_ambas &= ok
            filas.append({
                "ventana": etiqueta, "estrategia": nombre, "dias_vetados": veto_dias,
                "n": r["n"], "retencion": round(ret, 3),
                "E[R]": round(r["expectancy_r"], 3) if r["n"] else float("nan"),
                "caida_ER": round(caida, 3),
                "peor_r": round(r["peor_r"], 3) if r["n"] else float("nan"),
                "ER_vetados": round(vetados["expectancy_r"], 3) if vetados["n"] else float("nan"),
                "ER_conserv": round(conservados["expectancy_r"], 3) if conservados["n"] else float("nan"),
                "n_vetados": vetados["n"], "mecanismo_ok": mecanismo_ok, "cumple": ok,
            })
        todas = pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()
        dias = dias_stop_simultaneos(todas)
        for f in filas[-len(ESTRATEGIAS):]:
            f["dias_simult"] = dias
            f["mejora_dias"] = base_dias - dias
        veredictos[etiqueta] = cumple_ambas and dias < base_dias

    tabla = pd.DataFrame(filas)
    print("\n" + "=" * 120)
    print(tabla.to_string(index=False))

    ok = [v for v, cumple in veredictos.items() if cumple]
    print(f"\nVentanas que cumplen las condiciones 1-5: {ok if ok else 'ninguna'}")
    print(f"Condicion 6 (meseta, >= {MIN_VENTANAS_OK} de {len(VENTANAS)}): "
          f"{'CUMPLE -> ADOPTAR' if len(ok) >= MIN_VENTANAS_OK else 'NO CUMPLE -> DESCARTAR'}")

    # --- Diagnosticos descriptivos (docs/10, 4.1): NO seleccionan ---------- #
    print("\n--- Diagnosticos (descriptivos, no seleccionan) ---")
    peor5 = base_todas[base_todas["r_multiple"] <= base_todas["r_multiple"].quantile(0.05)]
    for etiqueta, antes, despues in VENTANAS:
        v = ventana_eventos(indice, fechas, antes, despues)
        dias_v = set(indice[v])
        frac_peor = peor5["entry_date"].isin(dias_v).mean()
        frac_todas = base_todas["entry_date"].isin(dias_v).mean()
        print(f"  {etiqueta:16s} cubre {v.mean():5.1%} de los dias | "
              f"peor 5% de trades dentro: {frac_peor:5.1%} | todos los trades dentro: {frac_todas:5.1%}")

    for tipo in ("fomc", "ipc"):
        sub = list(cal.loc[cal["tipo"] == tipo, "fecha"])
        v = ventana_eventos(indice, sub, 1, 1)
        dias_v = set(indice[v])
        print(f"  solo {tipo.upper():5s} (V3)   cubre {v.mean():5.1%} de los dias | "
              f"peor 5% dentro: {peor5['entry_date'].isin(dias_v).mean():5.1%} | "
              f"todos dentro: {base_todas['entry_date'].isin(dias_v).mean():5.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
