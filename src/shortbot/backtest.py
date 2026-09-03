"""Motor de backtesting *short-only*, barra a barra.

Decisiones de diseno pensadas para no enganarnos a nosotros mismos:

1. **Sin lookahead.** La senal se calcula con el cierre de la barra ``t`` y la
   entrada se ejecuta en la *apertura* de la barra ``t+1``.
2. **Los huecos se pagan.** Si la apertura ya supera el stop (el escenario tipico
   de un short squeeze), el fill es a esa apertura, no al stop. Es la diferencia
   entre un backtest honesto y uno que promete lo que no puede cumplir.
3. **Si en la misma barra tocan stop y objetivo, gana el stop.** Suposicion
   conservadora: sin datos intrabarra no sabemos el orden.
4. **El corto cuesta dinero cada dia.** Se cobran comision, slippage y coste de
   prestamo (borrow en acciones / funding en perpetuos) por tiempo en mercado.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class CostModel:
    """Costes de operar en corto.

    ``borrow_annual_pct`` es el coste anualizado de tomar prestado el activo
    (acciones) o el funding medio pagado (perpetuos cripto). Un 3% es normal en
    un valor liquido; un small cap 'hard to borrow' puede superar el 50%.
    """

    commission_bps: float = 2.0
    slippage_bps: float = 5.0
    borrow_annual_pct: float = 3.0
    periods_per_year: int = 252

    @property
    def side_cost(self) -> float:
        """Coste por lado, en fraccion del precio."""
        return (self.commission_bps + self.slippage_bps) / 10_000.0

    @property
    def borrow_per_period(self) -> float:
        return (self.borrow_annual_pct / 100.0) / self.periods_per_year


@dataclass
class BacktestConfig:
    initial_equity: float = 100_000.0
    risk_per_trade: float = 0.01      # fraccion del equity arriesgada hasta el stop
    max_notional_pct: float = 1.0     # tope de exposicion nocional sobre el equity
    default_stop_atr: float = 2.0
    default_target_atr: float = 3.0
    default_max_bars: int = 10
    # Barras EXTRA de retraso entre la senal y la ejecucion. 0 = comportamiento
    # normal (senal al cierre de t, entrada en la apertura de t+1). Subirlo
    # simula llegar tarde: feed con retraso, revision manual, ejecucion diferida.
    entry_delay_bars: int = 0
    # -1 = corto (por defecto: es lo unico que el proyecto ha operado hasta
    # ahora, y el valor por defecto garantiza que nada cambie de conducta).
    # +1 = largo. Cambia donde va el stop, que lado del rango lo toca y el
    # signo del P&L; el carry por prestamo solo existe en corto.
    direccion: int = -1
    costs: CostModel = field(default_factory=CostModel)

    @property
    def es_largo(self) -> bool:
        return self.direccion > 0


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    qty: float
    bars_held: int
    reason: str
    gross_pnl: float
    fees: float
    borrow_cost: float
    pnl: float
    r_multiple: float


class _Position:
    """Estado de la posicion corta abierta."""

    __slots__ = ("entry_idx", "entry_price", "qty", "stop", "target",
                 "max_bars", "bars_held", "risk_amount", "entry_fee")

    def __init__(self, entry_idx, entry_price, qty, stop, target, max_bars,
                 risk_amount, entry_fee):
        self.entry_idx = entry_idx
        self.entry_price = entry_price
        self.qty = qty
        self.stop = stop
        self.target = target
        self.max_bars = max_bars
        self.bars_held = 0
        self.risk_amount = risk_amount
        self.entry_fee = entry_fee


class ShortBacktester:
    """Ejecuta una serie de senales de venta en corto sobre un unico activo."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(self, df: pd.DataFrame, signals: pd.DataFrame) -> "BacktestResult":
        """``df``: OHLC(V) con indice temporal ordenado.

        ``signals``: DataFrame alineado con ``entry`` (bool) y ``atr``
        (obligatoria, es la unidad de riesgo). Opcionales: ``stop_atr``,
        ``target_atr``, ``max_bars`` y ``exit`` (salida discrecional).
        """
        cfg = self.config
        missing = {"open", "high", "low", "close"} - set(df.columns)
        if missing:
            raise ValueError(f"Faltan columnas OHLC: {sorted(missing)}")
        if "atr" not in signals.columns:
            raise ValueError("La estrategia debe aportar 'atr' para dimensionar el riesgo.")

        sig = signals.reindex(df.index)
        n = len(df)
        opens = df["open"].to_numpy(float)
        highs = df["high"].to_numpy(float)
        lows = df["low"].to_numpy(float)
        closes = df["close"].to_numpy(float)

        entry_arr = _col(sig, "entry", False, n).astype(bool)
        exit_arr = _col(sig, "exit", False, n).astype(bool)
        stop_arr = _col(sig, "stop_atr", cfg.default_stop_atr, n).astype(float)
        target_arr = _col(sig, "target_atr", cfg.default_target_atr, n).astype(float)
        maxbars_arr = _col(sig, "max_bars", cfg.default_max_bars, n).astype(float)
        atr_arr = sig["atr"].to_numpy(float)

        side_cost = cfg.costs.side_cost
        borrow_rate = cfg.costs.borrow_per_period

        equity = cfg.initial_equity
        trades: list[Trade] = []
        equity_curve = np.full(n, np.nan)
        exposure = np.zeros(n)

        pos: Optional[_Position] = None
        pending: Optional[dict] = None

        for i in range(n):
            # --- 1) Ejecutar la entrada pendiente en la apertura de esta barra ---
            if pending is not None and pos is None:
                if pending["espera"] > 0:
                    pending["espera"] -= 1
                else:
                    pos = self._open_position(i, opens[i], pending, equity, side_cost)
                    pending = None

            # --- 2) Gestionar la posicion viva dentro de la barra ---
            if pos is not None:
                pos.bars_held += 1
                exit_px, reason = self._resolve_exit(pos, i, opens, highs, lows, closes,
                                                     exit_arr, cfg.direccion)
                if exit_px is not None:
                    equity, trade = self._close_position(
                        pos, i, df.index, exit_px, reason, equity, side_cost,
                        borrow_rate, cfg.direccion
                    )
                    trades.append(trade)
                    pos = None

            # --- 3) Marcar equity (mark-to-market) y exposicion ---
            if pos is not None:
                equity_curve[i] = equity + cfg.direccion * (closes[i] - pos.entry_price) * pos.qty
                exposure[i] = (pos.qty * closes[i]) / max(equity, 1e-9)
            else:
                equity_curve[i] = equity

            # --- 4) Senal de entrada: se ejecutara en la apertura siguiente ---
            if (
                entry_arr[i]
                and pos is None
                and pending is None
                and i + 1 < n
                and np.isfinite(atr_arr[i])
                and atr_arr[i] > 0
            ):
                pending = {
                    "atr": atr_arr[i],
                    "stop_atr": stop_arr[i],
                    "target_atr": target_arr[i],
                    "max_bars": int(maxbars_arr[i]) if maxbars_arr[i] > 0 else 10**9,
                    "espera": cfg.entry_delay_bars,
                }

        return BacktestResult(
            equity_curve=pd.Series(equity_curve, index=df.index),
            trades=pd.DataFrame([asdict(t) for t in trades]),
            exposure=pd.Series(exposure, index=df.index),
            config=cfg,
        )

    # ------------------------------------------------------------------ #

    def _open_position(self, i, open_px, pending, equity, side_cost) -> Optional[_Position]:
        cfg = self.config
        risk_per_unit = pending["stop_atr"] * pending["atr"]
        if not np.isfinite(risk_per_unit) or risk_per_unit <= 0:
            return None
        # Un precio no positivo no es un error de datos (el WTI cerro a -37,63
        # el 20-04-2020), pero el dimensionamiento por nocional pierde sentido:
        # dividir por un precio negativo daria una cantidad negativa, es decir,
        # un largo encubierto. Preferimos no operar esa barra.
        if not np.isfinite(open_px) or open_px <= 0:
            return None
        qty = (equity * cfg.risk_per_trade) / risk_per_unit
        qty = min(qty, (equity * cfg.max_notional_pct) / open_px)
        if qty <= 0:
            return None
        d = cfg.direccion
        return _Position(
            entry_idx=i,
            entry_price=open_px,
            qty=qty,
            # El stop siempre va en contra de la posicion y el objetivo a
            # favor: con d=-1 sale el corto de siempre; con d=+1 se invierten.
            stop=open_px - d * pending["stop_atr"] * pending["atr"],
            target=open_px + d * pending["target_atr"] * pending["atr"],
            max_bars=pending["max_bars"],
            risk_amount=qty * risk_per_unit,
            entry_fee=open_px * qty * side_cost,
        )

    @staticmethod
    def _resolve_exit(pos, i, opens, highs, lows, closes, exit_arr, direccion=-1):
        """Prioridad: hueco > stop > objetivo > senal > tiempo.

        El orden de prioridad es el mismo en las dos direcciones; lo unico que
        cambia es que extremo de la barra toca cada nivel. En corto el stop
        esta arriba (lo toca el maximo) y en largo abajo (lo toca el minimo).
        """
        corto = direccion < 0
        if pos.bars_held > 1:                      # huecos solo tras la barra de entrada
            if (opens[i] >= pos.stop) if corto else (opens[i] <= pos.stop):
                return opens[i], "gap_stop"
            if (opens[i] <= pos.target) if corto else (opens[i] >= pos.target):
                return opens[i], "gap_target"
        if (highs[i] >= pos.stop) if corto else (lows[i] <= pos.stop):
            return pos.stop, "stop"
        if (lows[i] <= pos.target) if corto else (highs[i] >= pos.target):
            return pos.target, "target"
        if exit_arr[i]:
            return closes[i], "signal"
        if pos.bars_held >= pos.max_bars:
            return closes[i], "time"
        return None, ""

    @staticmethod
    def _close_position(pos, i, index, exit_px, reason, equity, side_cost,
                        borrow_rate, direccion=-1):
        exit_fee = exit_px * pos.qty * side_cost
        fees = pos.entry_fee + exit_fee
        gross = direccion * (exit_px - pos.entry_price) * pos.qty
        # El coste de prestamo solo lo paga quien vende algo que no tiene.
        borrow_cost = (borrow_rate * pos.entry_price * pos.qty * pos.bars_held
                       if direccion < 0 else 0.0)
        pnl = gross - fees - borrow_cost
        return equity + pnl, Trade(
            entry_date=index[pos.entry_idx],
            exit_date=index[i],
            entry_price=pos.entry_price,
            exit_price=exit_px,
            qty=pos.qty,
            bars_held=pos.bars_held,
            reason=reason,
            gross_pnl=gross,
            fees=fees,
            borrow_cost=borrow_cost,
            pnl=pnl,
            r_multiple=pnl / pos.risk_amount if pos.risk_amount > 0 else np.nan,
        )


def _col(sig: pd.DataFrame, name: str, default, n: int) -> np.ndarray:
    if name in sig.columns:
        return sig[name].fillna(default).to_numpy()
    return np.full(n, default)


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    exposure: pd.Series
    config: BacktestConfig

    @property
    def returns(self) -> pd.Series:
        return self.equity_curve.pct_change().fillna(0.0)
