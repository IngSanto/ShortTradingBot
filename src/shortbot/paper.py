"""Motor de paper trading con estado persistente.

Simula la operativa hacia delante, barra a barra, guardando el estado en disco
entre ejecuciones. La diferencia con el backtest no es el codigo -reutiliza sus
mismas reglas de salida, y es deliberado: si divergieran, comparar paper contra
backtest no significaria nada- sino que aqui **solo se procesan barras nuevas**
y cada decision queda registrada con la fecha en que se tomo.

Eso es lo que hace la puerta 4 distinta de las anteriores: no se puede acelerar
ni rehacer. Una operacion registrada ayer no se puede reinterpretar hoy.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, ShortBacktester
from .strategies.base import Strategy


@dataclass
class PosicionPapel:
    estrategia: str
    simbolo: str
    fecha_senal: str
    fecha_entrada: str
    precio_entrada: float
    cantidad: float
    stop: float
    objetivo: float
    max_barras: int
    barras: int = 0
    riesgo: float = 0.0
    # -1 corto, +1 largo. Va en la POSICION y no en la configuracion porque
    # una misma cartera puede llevar las dos a la vez; el valor por defecto
    # mantiene validos los estados guardados antes de que esto existiera.
    direccion: int = -1


@dataclass
class OperacionPapel:
    estrategia: str
    simbolo: str
    fecha_senal: str
    fecha_entrada: str
    fecha_salida: str
    precio_entrada: float
    precio_salida: float
    cantidad: float
    barras: int
    motivo: str
    comisiones: float
    carry: float
    pnl: float
    r_multiple: float


@dataclass
class EstadoPapel:
    creado: str
    equity_inicial: float
    equity: float
    ultima_barra: dict[str, str] = field(default_factory=dict)
    abiertas: list[dict] = field(default_factory=list)
    cerradas: list[dict] = field(default_factory=list)
    pendientes: list[dict] = field(default_factory=list)
    # Una foto diaria de equity/operaciones para poder dibujar una curva real.
    # `equity` por sí solo es un escalar: sin este historial no hay forma de
    # saber cómo se llegó hasta ahí.
    historial: list[dict] = field(default_factory=list)

    @classmethod
    def cargar(cls, path: str, equity_inicial: float = 100_000.0) -> "EstadoPapel":
        if os.path.exists(path):
            datos = json.load(open(path))
            datos.setdefault("historial", [])
            return cls(**datos)
        return cls(creado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   equity_inicial=equity_inicial, equity=equity_inicial)

    def registrar_snapshot(self, fecha: str, precios: dict[str, float] | None = None) -> None:
        """Añade (o reemplaza, si ya corrió hoy) la foto del día en curso.

        `equity` es solo lo REALIZADO: se actualiza al cerrar una posición. Es
        lo correcto para dimensionar -no se arriesga sobre beneficio que aún no
        se ha cobrado- pero como curva miente: no se mueve mientras hay
        posiciones abiertas perdiendo y salta el día que cierran. Medir
        volatilidad, drawdown o correlación sobre esa escalera da números que
        no corresponden al valor real de la cuenta.

        Por eso se guarda además `equity_mercado`, que suma el no realizado de
        lo que sigue abierto. Es la cifra que un broker mostraría, y la única
        con la que las métricas de riesgo significan algo.
        """
        no_realizado = 0.0
        if precios:
            for d in self.abiertas:
                px = precios.get(d["simbolo"])
                if px is None:
                    continue
                # En corto se gana cuando el precio baja: de ahí el signo.
                direccion = int(d.get("direccion", -1))
                no_realizado += direccion * (px - d["precio_entrada"]) * d["cantidad"]
        punto = {
            "fecha": fecha,
            "equity": self.equity,
            "equity_mercado": self.equity + no_realizado,
            "no_realizado": no_realizado,
            "operaciones_cerradas": len(self.cerradas),
            "operaciones_abiertas": len(self.abiertas),
        }
        if self.historial and self.historial[-1]["fecha"] == fecha:
            self.historial[-1] = punto
        else:
            self.historial.append(punto)

    def guardar(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(asdict(self), open(path, "w"), indent=2, ensure_ascii=False, default=str)


class PaperBroker:
    """Aplica las reglas del backtest sobre barras que llegan una a una."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self._motor = ShortBacktester(self.config)

    # ------------------------------------------------------------------ #

    def procesar(
        self,
        estado: EstadoPapel,
        estrategia: Strategy,
        simbolo: str,
        df: pd.DataFrame,
        veto: Optional[pd.Series] = None,
    ) -> list[str]:
        """Avanza el estado con las barras nuevas de un activo. Devuelve el log.

        `veto` es un filtro de riesgo ya alineado con `df.index`: True en las
        filas de SEÑAL cuya entrada resultante debe bloquearse. Se aplica aqui
        y no dentro de la estrategia porque un filtro no es parte de la
        hipotesis -veta entradas, nunca las genera- y tiene que poder
        activarse o quitarse sin tocar la estrategia.
        """
        cfg = self.config
        log: list[str] = []
        clave = f"{estrategia.name}|{simbolo}"

        senales = estrategia.generate_signals(df)
        ultima = estado.ultima_barra.get(clave)
        nuevas = df.index if ultima is None else df.index[df.index > pd.Timestamp(ultima)]
        if len(nuevas) == 0:
            return log

        if veto is not None:
            bloquear = veto.reindex(senales.index).fillna(False)
            # Se informa solo de lo que ocurre en las barras NUEVAS: contar
            # sobre todo el historico repetiria la misma cifra cada dia y
            # convertiria el registro diario en ruido.
            recien = (senales["entry"] & bloquear).reindex(nuevas).fillna(False)
            if recien.any():
                log.append(f"{clave}: {int(recien.sum())} señal(es) vetadas hoy "
                           f"por el filtro de eventos macro")
            senales = senales.copy()
            senales["entry"] = senales["entry"] & ~bloquear

        # La primera vez no se opera el historico entero: seria un backtest
        # disfrazado de paper. Solo se marca desde donde empieza a contar.
        if ultima is None:
            estado.ultima_barra[clave] = str(df.index[-1])
            log.append(f"{clave}: arranque, marcado en {df.index[-1].date()}")
            return log

        for ts in nuevas:
            i = df.index.get_loc(ts)
            # El orden dentro de la barra importa y tiene que ser el MISMO que
            # el del backtest: primero se abre la entrada pendiente (solo si no
            # hay posicion), luego se gestionan las salidas, y al final se
            # registran las senales nuevas. Al reves se podria cerrar y reabrir
            # en la misma barra, que el backtest no permite, y las dos curvas
            # dejarian de ser comparables.
            self._entradas_pendientes(estado, clave, df, i, log)
            self._salidas(estado, clave, df, i, log)
            self._nuevas_senales(estado, clave, senales, df, i, log)
            estado.ultima_barra[clave] = str(ts)
        return log

    # ------------------------------------------------------------------ #

    def _salidas(self, estado, clave, df, i, log):
        cfg = self.config
        quedan = []
        for d in estado.abiertas:
            if f"{d['estrategia']}|{d['simbolo']}" != clave:
                quedan.append(d); continue
            pos = PosicionPapel(**d)
            pos.barras += 1

            # Mismo orden de prioridad que el backtest: hueco > stop > objetivo
            # > tiempo. Lo unico que cambia con la direccion es que extremo de
            # la barra toca cada nivel: en corto el stop esta arriba y lo toca
            # el maximo; en largo esta abajo y lo toca el minimo.
            o, h, l, c = (float(df["open"].iloc[i]), float(df["high"].iloc[i]),
                          float(df["low"].iloc[i]), float(df["close"].iloc[i]))
            corto = pos.direccion < 0
            salida, motivo = None, ""
            if pos.barras > 1 and ((o >= pos.stop) if corto else (o <= pos.stop)):
                salida, motivo = o, "gap_stop"
            elif pos.barras > 1 and ((o <= pos.objetivo) if corto else (o >= pos.objetivo)):
                salida, motivo = o, "gap_target"
            elif (h >= pos.stop) if corto else (l <= pos.stop):
                salida, motivo = pos.stop, "stop"
            elif (l <= pos.objetivo) if corto else (h >= pos.objetivo):
                salida, motivo = pos.objetivo, "target"
            elif pos.barras >= pos.max_barras:
                salida, motivo = c, "time"

            if salida is None:
                quedan.append(asdict(pos)); continue

            coste = cfg.costs.side_cost
            comisiones = (pos.precio_entrada + salida) * pos.cantidad * coste
            # El prestamo solo lo paga quien vende algo que no tiene.
            carry = (cfg.costs.borrow_per_period * pos.precio_entrada * pos.cantidad * pos.barras
                     if pos.direccion < 0 else 0.0)
            pnl = pos.direccion * (salida - pos.precio_entrada) * pos.cantidad - comisiones - carry
            estado.equity += pnl
            estado.cerradas.append(asdict(OperacionPapel(
                estrategia=pos.estrategia, simbolo=pos.simbolo,
                fecha_senal=pos.fecha_senal, fecha_entrada=pos.fecha_entrada,
                fecha_salida=str(df.index[i]), precio_entrada=pos.precio_entrada,
                precio_salida=salida, cantidad=pos.cantidad, barras=pos.barras,
                motivo=motivo, comisiones=comisiones, carry=carry, pnl=pnl,
                r_multiple=pnl / pos.riesgo if pos.riesgo > 0 else float("nan"))))
            log.append(f"  CIERRE {pos.simbolo} {motivo} a {salida:.4f} "
                       f"-> {pnl:+.2f} ({pnl / pos.riesgo:+.2f}R)")
        estado.abiertas = quedan

    def _entradas_pendientes(self, estado, clave, df, i, log):
        cfg = self.config
        quedan = []
        abiertos = {f"{d['estrategia']}|{d['simbolo']}" for d in estado.abiertas}
        for p in estado.pendientes:
            if f"{p['estrategia']}|{p['simbolo']}" != clave:
                quedan.append(p); continue
            if p.get("espera", 0) > 0:
                p["espera"] -= 1; quedan.append(p); continue
            if clave in abiertos:
                log.append(f"  descartada {p['simbolo']}: ya hay posicion abierta")
                continue

            apertura = float(df["open"].iloc[i])
            riesgo_unidad = p["stop_atr"] * p["atr"]
            if apertura <= 0 or riesgo_unidad <= 0:
                continue
            cantidad = min((estado.equity * cfg.risk_per_trade) / riesgo_unidad,
                           (estado.equity * cfg.max_notional_pct) / apertura)
            if cantidad <= 0:
                continue
            d = int(p.get("direccion", -1))
            estado.abiertas.append(asdict(PosicionPapel(
                estrategia=p["estrategia"], simbolo=p["simbolo"],
                fecha_senal=p["fecha_senal"], fecha_entrada=str(df.index[i]),
                precio_entrada=apertura, cantidad=cantidad,
                stop=apertura - d * p["stop_atr"] * p["atr"],
                objetivo=apertura + d * p["target_atr"] * p["atr"],
                max_barras=p["max_bars"], barras=0,
                riesgo=cantidad * riesgo_unidad, direccion=d)))
            log.append(f"  ENTRADA {p['simbolo']} corto a {apertura:.4f} "
                       f"(stop {apertura + p['stop_atr'] * p['atr']:.4f})")
        estado.pendientes = quedan

    def _nuevas_senales(self, estado, clave, senales, df, i, log, direccion=-1):
        cfg = self.config
        fila = senales.iloc[i]
        if not bool(fila.get("entry", False)):
            return
        atr = float(fila.get("atr", np.nan))
        if not np.isfinite(atr) or atr <= 0:
            return
        estrategia, simbolo = clave.split("|")
        if any(f"{d['estrategia']}|{d['simbolo']}" == clave for d in estado.abiertas):
            return
        if any(f"{p['estrategia']}|{p['simbolo']}" == clave for p in estado.pendientes):
            return
        estado.pendientes.append({
            "estrategia": estrategia, "simbolo": simbolo,
            "fecha_senal": str(df.index[i]), "atr": atr,
            "stop_atr": float(fila.get("stop_atr", cfg.default_stop_atr)),
            "target_atr": float(fila.get("target_atr", cfg.default_target_atr)),
            "max_bars": int(fila.get("max_bars", cfg.default_max_bars)),
            "espera": cfg.entry_delay_bars,
            "direccion": int(direccion),
        })
        log.append(f"  SEÑAL {simbolo} el {df.index[i].date()} "
                   f"-> entrada en la proxima apertura")


def resumen(estado: EstadoPapel) -> dict[str, Any]:
    """Metricas del paper trading, comparables con las del backtest."""
    ops = pd.DataFrame(estado.cerradas)
    base = {
        "equity": estado.equity,
        "retorno": estado.equity / estado.equity_inicial - 1,
        "abiertas": len(estado.abiertas),
        "pendientes": len(estado.pendientes),
        "operaciones": len(ops),
    }
    if ops.empty:
        return base
    r = ops["r_multiple"].dropna()
    ganadoras = ops[ops["pnl"] > 0]
    perdidas = float(-ops.loc[ops["pnl"] <= 0, "pnl"].sum())
    base.update({
        "expectancy_r": float(r.mean()) if len(r) else float("nan"),
        "acierto": float(len(ganadoras) / len(ops)),
        "profit_factor": float(ganadoras["pnl"].sum() / perdidas) if perdidas > 0 else float("inf"),
        "peor_r": float(r.min()) if len(r) else float("nan"),
        "costes": float((ops["comisiones"] + ops["carry"]).sum()),
    })
    return base
