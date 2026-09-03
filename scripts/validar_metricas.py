#!/usr/bin/env python3
"""Valida los datos de interes abierto ANTES de calibrar nada con ellos.

Las reglas las fijo `docs/12` seccion 4, antes de ver un solo dato. Aqui solo
se ejecutan. El orden importa: si se mirara primero el resultado de la
estrategia y despues se decidiera que activos "tienen datos de calidad", la
seleccion de activos se convertiria en un parametro mas de la estrategia, y
uno invisible.

Tres comprobaciones:

  COBERTURA   un activo entra solo si tiene metricas en >=80% de los dias en
              que tiene precio. Los que no llegan se excluyen y se listan.

  HUECOS      tramos de mas de 5 dias sin dato. No se interpolan: inventar
              interes abierto seria inventar la señal. Esos dias simplemente
              no generan entrada.

  CEROS       un interes abierto de exactamente cero no es un valor, es la
              ausencia del dato -o un contrato suspendido. Se cuenta aparte
              porque leerlo como valor real produce una caida del -100%, que
              es justo la señal extrema que busca la estrategia.

  SALTOS      variaciones diarias por encima de ±50%. El interes abierto puede
              saltar por un cambio de contrato o de metodo de Binance, no por
              mercado. Si los saltos aparecen agrupados en una fecha comun a
              muchos activos, es artefacto y esa fecha se excluye del universo
              entero -no del activo suelto, porque el problema no es del
              activo.

    python scripts/validar_metricas.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.data import cargar_open_interest  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")
METRICAS = os.path.join(RAIZ, "data", "metricas")

MIN_COBERTURA = 0.80
HUECO_MAXIMO = 5
SALTO_MAXIMO = 0.50
# Una fecha se considera artefacto si el salto aparece en al menos esta
# fraccion de los activos que ese dia tienen dato.
FRACCION_ARTEFACTO = 0.30


def cargar(simbolo: str) -> pd.DataFrame | None:
    ruta = os.path.join(METRICAS, f"{simbolo}_metrics_1d.csv")
    if not os.path.exists(ruta):
        return None
    d = pd.read_csv(ruta, parse_dates=["fecha"]).set_index("fecha").sort_index()
    return d if "sum_open_interest_cierre" in d.columns else None


def main() -> int:
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    simbolos = split["diseno"] + split["reserva"]

    filas, series = [], {}
    for s in simbolos:
        m = cargar(s)
        if m is None:
            filas.append({"simbolo": s, "estado": "SIN DATOS", "cobertura": 0.0,
                          "dias": 0, "huecos": 0, "ceros": 0, "saltos": 0})
            continue
        precio = pd.read_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"),
                             index_col=0, parse_dates=True)
        # La cobertura se mide contra los dias en que el activo TIENE precio y
        # el archivo de metricas ya existia: penalizar a un activo por no tener
        # interes abierto antes de que Binance lo publicara mediria la fecha de
        # lanzamiento del archivo, no la calidad del dato.
        comun = precio.loc[max(precio.index.min(), m.index.min()):]
        cobertura = len(m.reindex(comun.index).dropna(subset=["sum_open_interest_cierre"])) / max(len(comun), 1)

        ruta_m = os.path.join(METRICAS, f"{s}_metrics_1d.csv")
        oi = cargar_open_interest(ruta_m)      # los ceros ya son ausencia
        ceros = int(oi.isna().sum())
        faltan = comun.index.difference(m.index)
        huecos = 0
        if len(faltan):
            grupos = (faltan.to_series().diff().dt.days.fillna(1) > 1).cumsum()
            huecos = int((faltan.to_series().groupby(grupos).size() > HUECO_MAXIMO).sum())

        cambio = oi.pct_change()
        saltos = cambio[cambio.abs() > SALTO_MAXIMO]
        series[s] = saltos.index

        filas.append({"simbolo": s, "estado": "ok" if cobertura >= MIN_COBERTURA else "EXCLUIDO",
                      "cobertura": round(cobertura, 3), "dias": len(m),
                      "huecos": huecos, "ceros": ceros, "saltos": len(saltos)})

    t = pd.DataFrame(filas).sort_values(["estado", "cobertura"])
    print(t.to_string(index=False))

    ok = t[t["estado"] == "ok"]["simbolo"].tolist()
    excluidos = t[t["estado"] != "ok"]["simbolo"].tolist()
    print(f"\nCobertura >= {MIN_COBERTURA:.0%}: {len(ok)} activos entran, {len(excluidos)} fuera")
    if excluidos:
        print(f"  excluidos: {', '.join(excluidos)}")

    # Saltos agrupados en una misma fecha = artefacto de Binance, no mercado.
    conteo = pd.Series([f for s in ok for f in series.get(s, [])]).value_counts()
    if len(conteo):
        sospechosas = conteo[conteo >= max(2, int(len(ok) * FRACCION_ARTEFACTO))]
        print(f"\nSaltos de OI > ±{SALTO_MAXIMO:.0%}: {int(conteo.sum())} en total")
        if len(sospechosas):
            print(f"  FECHAS ARTEFACTO (>={FRACCION_ARTEFACTO:.0%} de los activos el mismo dia), "
                  f"se excluyen del universo:")
            for f, n in sospechosas.items():
                print(f"    {f.date()}  {n} activos")
        else:
            print("  ninguna fecha concentra saltos: son movimientos de mercado, no artefactos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
