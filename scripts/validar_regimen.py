#!/usr/bin/env python3
"""Valida el peso dinamico por regimen pre-registrado en docs/17.

Cuatro pruebas, fijadas antes de ejecutar:

  MESETA    el efecto tiene que aparecer en al menos 3 de 5 longitudes de
            media. Si solo vive en 200 dias, es un punto ajustado.
  COSTES    cada cambio de regimen mueve capital entre dos botes: 0,20% de lo
            movido, del lado pesimista.
  PERIODOS  tiene que ganar al mejor peso fijo en el periodo completo Y en
            2022-2026, no solo en el agregado.
  NULA      la que decide. Se compara contra 200 regimenes ALEATORIOS con la
            misma frecuencia de cambio. Si un regimen inventado rinde
            parecido, lo que funciona es cambiar de peso periodicamente, no
            saber cuando hacerlo -y entonces la media movil no aporta nada.

    python scripts/validar_regimen.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from nucleo_cobertura import retornos_bot, retornos_nucleo  # noqa: E402

MEDIAS = [100, 150, 200, 250, 300]
PARES = [(0.8, 0.2), (0.7, 0.3), (0.6, 0.4)]
COSTE_CAMBIO = 0.002      # 0,20% del capital movido
N_NULAS = 200
DIAS_ANIO = 365
CORTE = "2022-01-01"


def aplicar(nucleo: pd.Series, bot: pd.Series, w: pd.Series) -> pd.Series:
    """Retornos de la mezcla, cobrando el coste cuando el peso cambia."""
    r = w * nucleo + (1 - w) * bot
    movido = w.diff().abs().fillna(0.0) * 2      # sale de un bote y entra en otro
    return r - movido * COSTE_CAMBIO


def metricas(r: pd.Series) -> dict:
    r = r.clip(lower=-0.95)
    eq = (1 + r).cumprod()
    años = (r.index[-1] - r.index[0]).days / 365.25
    return {"CAGR": eq.iloc[-1] ** (1 / años) - 1 if eq.iloc[-1] > 0 else -1.0,
            "DD": ((eq - eq.cummax()) / eq.cummax()).min(),
            "sharpe": r.mean() / r.std() * np.sqrt(DIAS_ANIO) if r.std() > 0 else np.nan}


def main() -> int:
    bot = retornos_bot()
    nucleo = retornos_nucleo()
    c = bot.index.intersection(nucleo.index)
    bot, nucleo = bot.loc[c], nucleo.loc[c]
    precio = (1 + nucleo).cumprod()

    fijo = aplicar(nucleo, bot, pd.Series(0.5, index=c))
    ref_total, ref_reciente = metricas(fijo), metricas(fijo.loc[CORTE:])
    print(f"REFERENCIA - peso fijo 50/50 (con costes)")
    print(f"  completo   CAGR {ref_total['CAGR']:+7.1%}  Sharpe {ref_total['sharpe']:5.2f}")
    print(f"  2022-2026  CAGR {ref_reciente['CAGR']:+7.1%}  Sharpe {ref_reciente['sharpe']:5.2f}\n")

    filas = []
    for M in MEDIAS:
        alcista = (precio > precio.rolling(M).mean()).shift(1).fillna(False)
        cambios = int(alcista.ne(alcista.shift()).sum())
        por_año = cambios / ((c[-1] - c[0]).days / 365.25)
        for wa, wb in PARES:
            w = pd.Series(np.where(alcista, wa, wb), index=c)
            r = aplicar(nucleo, bot, w)
            mt, mr = metricas(r), metricas(r.loc[CORTE:])
            filas.append({
                "media": f"{M}d", "pesos": f"{wa:.0%}/{wb:.0%}",
                "cambios/año": round(por_año, 1),
                "CAGR": f"{mt['CAGR']:+.1%}", "Sharpe": round(mt["sharpe"], 2),
                "CAGR_2022+": f"{mr['CAGR']:+.1%}", "Sharpe_2022+": round(mr["sharpe"], 2),
                "bate_fijo": (mt["sharpe"] > ref_total["sharpe"]
                              and mr["sharpe"] > ref_reciente["sharpe"]),
            })
    t = pd.DataFrame(filas)
    print(t.to_string(index=False))

    # --- Condiciones 1, 2 y 4 ------------------------------------------- #
    medias_ok = t[t["bate_fijo"]].groupby("media").size()
    print(f"\nCondicion 1-2 (bate al fijo en los DOS periodos): "
          f"{len(medias_ok)} de {len(MEDIAS)} longitudes de media")
    print(f"Condicion meseta (>=3 de 5): "
          f"{'CUMPLE' if len(medias_ok) >= 3 else 'NO CUMPLE'}")
    rot = t["cambios/año"].max()
    print(f"Condicion 4 (rotacion < 12/año): max {rot:.1f} -> "
          f"{'CUMPLE' if rot < 12 else 'NO CUMPLE'}")

    # --- Condicion 3: prueba nula --------------------------------------- #
    print(f"\nPRUEBA NULA -- {N_NULAS} regimenes aleatorios con la misma frecuencia")
    rng = np.random.default_rng(20260904)
    for M in MEDIAS:
        alcista = (precio > precio.rolling(M).mean()).shift(1).fillna(False)
        p_cambio = alcista.ne(alcista.shift()).mean()
        wa, wb = 0.7, 0.3
        real = metricas(aplicar(nucleo, bot, pd.Series(np.where(alcista, wa, wb), index=c)))["sharpe"]

        nulos = []
        for _ in range(N_NULAS):
            # Cadena con la misma probabilidad de cambio: mismo numero de
            # giros, momentos distintos. Aisla "cuando" de "cuantas veces".
            cambia = rng.random(len(c)) < p_cambio
            estado = np.logical_xor.accumulate(cambia)
            if rng.random() < 0.5:
                estado = ~estado
            nulos.append(metricas(aplicar(nucleo, bot,
                                          pd.Series(np.where(estado, wa, wb), index=c)))["sharpe"])
        p95 = float(np.percentile(nulos, 95))
        pct = float((np.array(nulos) < real).mean())
        print(f"  media {M:3d}d  real {real:5.2f}  |  aleatorio: mediana "
              f"{np.median(nulos):5.2f}  p95 {p95:5.2f}  |  real supera al "
              f"{pct:.1%} de los nulos  -> {'PASA' if real > p95 else 'NO PASA'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
