#!/usr/bin/env python3
"""¿La diferencia entre trades vetados y conservados es real o es ruido?

La rejilla de `calibrate_event_filter.py` dice que los trades cuya entrada
cae en la ventana de un evento rinden peor. Con ~120 operaciones vetadas eso
podria ser perfectamente casualidad, y una media aislada no distingue una
cosa de la otra.

Aqui se contrasta con dos herramientas que no dependen de la normalidad de
los retornos -los R-multiples no lo son, tienen cola izquierda gorda y tope
a la derecha-:

  Welch     t de dos muestras sin suponer varianzas iguales.
  Permutar  se baraja 20.000 veces la etiqueta "vetado" entre TODOS los
            trades y se mira cuantas veces el azar produce una diferencia
            tan grande como la observada. No supone ninguna distribucion.

    python scripts/significancia_filtro_eventos.py [--ventana V3]
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.markets import get_market  # noqa: E402
from shortbot.risk_filters import ventana_eventos  # noqa: E402

from calibrate_event_filter import (  # noqa: E402
    CALENDARIO,
    ESTRATEGIAS,
    VENTANAS,
    cargar_universo,
    correr_estrategia,
)

PERMUTACIONES = 20_000


def permutacion(r: np.ndarray, dentro: np.ndarray, semilla: int = 20260903) -> tuple[float, float]:
    """Devuelve (diferencia observada, p) barajando la etiqueta."""
    obs = r[dentro].mean() - r[~dentro].mean()
    rng = np.random.default_rng(semilla)
    n_dentro = int(dentro.sum())
    extremos = 0
    for _ in range(PERMUTACIONES):
        idx = rng.permutation(len(r))
        d = r[idx[:n_dentro]].mean() - r[idx[n_dentro:]].mean()
        if abs(d) >= abs(obs):
            extremos += 1
    return float(obs), (extremos + 1) / (PERMUTACIONES + 1)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ventana", default="V3", help="prefijo de la ventana (V0..V4)")
    p.add_argument("--conjunto", choices=["diseno", "reserva"], default="diseno")
    args = p.parse_args()

    etiqueta, antes, despues = next(v for v in VENTANAS if v[0].startswith(args.ventana))
    fechas = list(pd.read_csv(CALENDARIO)["fecha"])
    universo = cargar_universo(args.conjunto)
    cfg = get_market("cripto").config()

    indice = universo[next(iter(universo))].index
    for df in universo.values():
        indice = indice.union(df.index)
    dias_ventana = set(indice[ventana_eventos(indice, fechas, antes, despues)])

    print(f"Ventana {etiqueta} | conjunto '{args.conjunto}' | {PERMUTACIONES:,} permutaciones\n")
    todas = []
    for nombre in ESTRATEGIAS:
        trades = correr_estrategia(nombre, universo, cfg, None)
        trades = trades.dropna(subset=["r_multiple"])
        todas.append(trades)
        analizar(nombre, trades, dias_ventana)
    analizar("AMBAS (agregado)", pd.concat(todas, ignore_index=True), dias_ventana)
    return 0


def analizar(nombre: str, trades: pd.DataFrame, dias_ventana: set) -> None:
    dentro = trades["entry_date"].isin(dias_ventana).to_numpy()
    r = trades["r_multiple"].to_numpy(float)
    if dentro.sum() < 2 or (~dentro).sum() < 2:
        print(f"{nombre}: muestra insuficiente"); return

    a, b = r[dentro], r[~dentro]
    # Welch a mano: sin scipy, que no esta en requirements.
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    t = (a.mean() - b.mean()) / se
    obs, pval = permutacion(r, dentro)

    print(f"{nombre}")
    print(f"  vetados     n={len(a):4d}  E[R]={a.mean():+.3f}  desv={a.std(ddof=1):.3f}")
    print(f"  conservados n={len(b):4d}  E[R]={b.mean():+.3f}  desv={b.std(ddof=1):.3f}")
    print(f"  diferencia  {obs:+.3f} R   t de Welch = {t:+.2f}   p (permutacion) = {pval:.4f}")
    print(f"  -> {'diferencia real' if pval < 0.05 else 'CABE EN EL RUIDO'}\n")


if __name__ == "__main__":
    raise SystemExit(main())
