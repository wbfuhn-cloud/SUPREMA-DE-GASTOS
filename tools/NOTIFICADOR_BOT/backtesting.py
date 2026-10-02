"""Backtester dirigido por eventos para Inversiones IA 3.0.

Una señal emitida en t solo puede ejecutarse en la siguiente barra disponible.
El motor exige membresía histórica explícita y nunca usa la lista actual como proxy.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Callable, Iterable

import numpy as np


BACKTEST_VERSION = "1.0.0"


@dataclass(frozen=True)
class MarketBar:
    session: date
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    universe_member: bool
    split_factor: float = 1.0
    dividend: float = 0.0
    sector: str = "unknown"
    regime: str = "unknown"
    liquidity_bucket: str = "unknown"
    volatility_bucket: str = "unknown"


@dataclass(frozen=True)
class SignalEvent:
    emitted_session: date
    symbol: str
    action: str
    horizon: str
    shares: int = 0
    strategy: str = "heuristic"


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 2.0
    half_spread_bps: float = 3.0
    base_slippage_bps: float = 2.0
    impact_bps_at_max_participation: float = 15.0
    max_volume_participation: float = 0.01
    tax_rate: float = 0.0

    def execution(self, side: str, raw_price: float, shares: int, volume: float) -> dict[str, float]:
        if raw_price <= 0 or shares <= 0 or volume <= 0:
            raise ValueError("Precio, acciones y volumen deben ser positivos")
        participation = shares / volume
        if participation > self.max_volume_participation:
            raise ValueError("ORDER_NOT_FILLED_LIQUIDITY")
        impact = self.impact_bps_at_max_participation * (participation / self.max_volume_participation) ** 0.5
        friction_bps = self.half_spread_bps + self.base_slippage_bps + impact
        direction = 1.0 if side == "BUY" else -1.0
        price = raw_price * (1.0 + direction * friction_bps / 10_000.0)
        notional = price * shares
        commission = notional * self.commission_bps / 10_000.0
        return {"price": price, "notional": notional, "commission": commission,
                "spread": raw_price * shares * self.half_spread_bps / 10_000.0,
                "slippage": raw_price * shares * (self.base_slippage_bps + impact) / 10_000.0,
                "participation": participation}


class EventDrivenBacktester:
    def __init__(self, initial_cash: float = 100_000.0, costs: CostModel = CostModel()):
        self.initial_cash = float(initial_cash)
        self.costs = costs

    def run(self, bars: Iterable[MarketBar], signals: Iterable[SignalEvent]) -> dict[str, Any]:
        ordered_bars = sorted(bars, key=lambda item: (item.session, item.symbol))
        if not ordered_bars:
            raise ValueError("Backtest sin barras")
        by_session: dict[date, list[MarketBar]] = {}
        for bar in ordered_bars:
            if min(bar.open, bar.high, bar.low, bar.close, bar.volume) <= 0:
                raise ValueError("Barra inválida")
            by_session.setdefault(bar.session, []).append(bar)
        signal_map: dict[date, list[SignalEvent]] = {}
        for signal in signals:
            signal_map.setdefault(signal.emitted_session, []).append(signal)

        cash = self.initial_cash
        positions: dict[str, dict[str, Any]] = {}
        pending: list[SignalEvent] = []
        trades: list[dict[str, Any]] = []
        fills: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        equity_curve = []
        total_cost = 0.0
        turnover_notional = 0.0
        exposed_sessions = 0
        last_close: dict[str, float] = {}

        for session in sorted(by_session):
            session_bars = {bar.symbol.upper(): bar for bar in by_session[session]}
            # Acciones corporativas se aplican a posiciones existentes antes de abrir.
            for symbol, position in list(positions.items()):
                bar = session_bars.get(symbol)
                if not bar:
                    continue
                if bar.split_factor != 1.0:
                    position["shares"] *= bar.split_factor
                    position["average_cost"] /= bar.split_factor
                if bar.dividend:
                    cash += position["shares"] * bar.dividend

            remaining = []
            for signal in pending:
                symbol = signal.symbol.upper()
                bar = session_bars.get(symbol)
                if bar is None:
                    remaining.append(signal)
                    continue
                if not bar.universe_member:
                    rejected.append({"signal": asdict(signal), "reason": "NOT_HISTORICAL_UNIVERSE_MEMBER"})
                    continue
                action = signal.action.upper()
                current = positions.get(symbol)
                side = "BUY" if action == "COMPRAR" else "SELL"
                shares = signal.shares if side == "BUY" else int(current["shares"] if current else 0)
                if action == "REDUCIR" and current:
                    shares = max(1, int(current["shares"] // 2))
                if shares <= 0:
                    rejected.append({"signal": asdict(signal), "reason": "NO_EXECUTABLE_POSITION_SIZE"})
                    continue
                try:
                    execution = self.costs.execution(side, bar.open, shares, bar.volume)
                except ValueError as exc:
                    rejected.append({"signal": asdict(signal), "reason": str(exc)})
                    continue
                if side == "BUY":
                    required = execution["notional"] + execution["commission"]
                    if required > cash:
                        rejected.append({"signal": asdict(signal), "reason": "INSUFFICIENT_CASH"})
                        continue
                    cash -= required
                    if current:
                        total_shares = current["shares"] + shares
                        current["average_cost"] = (
                            current["average_cost"] * current["shares"] + required
                        ) / total_shares
                        current["shares"] = total_shares
                    else:
                        positions[symbol] = {"shares": float(shares), "average_cost": required / shares,
                                             "entry_session": session, "horizon": signal.horizon,
                                             "strategy": signal.strategy}
                else:
                    if not current:
                        rejected.append({"signal": asdict(signal), "reason": "NO_OPEN_POSITION"})
                        continue
                    shares = min(shares, int(current["shares"]))
                    proceeds = execution["notional"] - execution["commission"]
                    taxes = max(0.0, proceeds - current["average_cost"] * shares) * self.costs.tax_rate
                    proceeds -= taxes
                    cash += proceeds
                    pnl = proceeds - current["average_cost"] * shares
                    holding_days = (session - current["entry_session"]).days
                    trades.append({"symbol": symbol, "entry_session": current["entry_session"],
                                   "exit_session": session, "shares": shares, "pnl": pnl,
                                   "return": pnl / max(current["average_cost"] * shares, 1e-12),
                                   "holding_days": holding_days, "horizon": current["horizon"],
                                   "strategy": current["strategy"], "exit_action": action,
                                   "sector": bar.sector, "regime": bar.regime,
                                   "liquidity_bucket": bar.liquidity_bucket,
                                   "volatility_bucket": bar.volatility_bucket})
                    current["shares"] -= shares
                    if current["shares"] <= 0:
                        positions.pop(symbol)
                    total_cost += taxes
                friction = execution["commission"] + execution["spread"] + execution["slippage"]
                total_cost += friction
                turnover_notional += execution["notional"]
                fills.append({"session": session.isoformat(), "symbol": symbol, "side": side,
                              "shares": shares, "raw_open": bar.open, **execution,
                              "emitted_session": signal.emitted_session.isoformat()})
            pending = remaining
            pending.extend(signal_map.get(session, []))

            for symbol, bar in session_bars.items():
                last_close[symbol] = bar.close
            market_value = sum(position["shares"] * last_close.get(symbol, position["average_cost"])
                               for symbol, position in positions.items())
            equity = cash + market_value
            if positions:
                exposed_sessions += 1
            equity_curve.append({"session": session.isoformat(), "equity": equity,
                                 "cash": cash, "market_value": market_value})

        metrics = performance_metrics(equity_curve, trades, total_cost, turnover_notional,
                                      exposed_sessions, len(by_session))
        metrics["approximate_capacity"] = min(
            (bar.volume * bar.close * self.costs.max_volume_participation for bar in ordered_bars),
            default=0.0,
        )
        return {"backtest_version": BACKTEST_VERSION, "metrics": metrics, "equity_curve": equity_curve,
                "trades": trades, "fills": fills, "rejected_orders": rejected,
                "open_positions": positions, "pending_signals": [asdict(item) for item in pending]}


def performance_metrics(equity_curve: list[dict[str, Any]], trades: list[dict[str, Any]],
                        total_cost: float, turnover_notional: float,
                        exposed_sessions: int, total_sessions: int) -> dict[str, Any]:
    equity = np.asarray([row["equity"] for row in equity_curve], dtype=float)
    returns = equity[1:] / equity[:-1] - 1.0 if len(equity) > 1 else np.array([])
    total_return = float(equity[-1] / equity[0] - 1.0) if len(equity) else 0.0
    years = max(len(equity) / 252.0, 1.0 / 252.0)
    cagr = float((equity[-1] / equity[0]) ** (1.0 / years) - 1.0) if equity[0] > 0 else 0.0
    volatility = float(np.std(returns, ddof=0) * np.sqrt(252)) if len(returns) else 0.0
    mean_return = float(np.mean(returns)) if len(returns) else 0.0
    sharpe = mean_return / max(float(np.std(returns, ddof=0)), 1e-15) * np.sqrt(252) if len(returns) else 0.0
    downside = returns[returns < 0]
    sortino = mean_return / max(float(np.std(downside, ddof=0)), 1e-15) * np.sqrt(252) if len(downside) else 0.0
    peaks = np.maximum.accumulate(equity)
    drawdowns = equity / peaks - 1.0
    max_drawdown = float(np.min(drawdowns)) if len(drawdowns) else 0.0
    duration = longest_drawdown_duration(drawdowns)
    profits = [trade["pnl"] for trade in trades if trade["pnl"] > 0]
    losses = [trade["pnl"] for trade in trades if trade["pnl"] < 0]
    gross_profit, gross_loss = sum(profits), abs(sum(losses))
    top_five = sum(sorted(profits, reverse=True)[:5]) / gross_profit if gross_profit else 0.0
    precision_by_horizon = {}
    for horizon in sorted({trade["horizon"] for trade in trades}):
        subset = [trade for trade in trades if trade["horizon"] == horizon]
        precision_by_horizon[horizon] = {
            "buy_precision": sum(trade["pnl"] > 0 for trade in subset) / len(subset),
            "exit_precision": None,
            "exit_precision_reason": "requiere retorno contrafactual posterior a la salida",
        }
    return {
        "cagr": cagr, "total_return": total_return, "annualized_volatility": volatility,
        "sharpe": float(sharpe), "sortino": float(sortino), "maximum_drawdown": max_drawdown,
        "drawdown_duration_sessions": duration,
        "calmar": cagr / abs(max_drawdown) if max_drawdown else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0.0),
        "win_rate": len(profits) / len(trades) if trades else 0.0,
        "average_payoff": float(np.mean([trade["pnl"] for trade in trades])) if trades else 0.0,
        "expected_value_per_trade": float(np.mean([trade["pnl"] for trade in trades])) if trades else 0.0,
        "turnover": turnover_notional / max(float(np.mean(equity)), 1e-12),
        "exposure": exposed_sessions / max(total_sessions, 1),
        "average_holding_days": float(np.mean([trade["holding_days"] for trade in trades])) if trades else 0.0,
        "buy_precision": len(profits) / len(trades) if trades else 0.0,
        "exit_precision": None,
        "precision_by_horizon": precision_by_horizon,
        "total_cost": total_cost,
        "top_5_profit_contribution": top_five,
        "trade_count": len(trades),
    }


def longest_drawdown_duration(drawdowns: np.ndarray) -> int:
    longest = current = 0
    for value in drawdowns:
        current = current + 1 if value < 0 else 0
        longest = max(longest, current)
    return longest


def walk_forward_splits(sample_count: int, train_size: int, test_size: int,
                        *, anchored: bool, final_holdout: int) -> list[dict[str, np.ndarray]]:
    development_end = sample_count - final_holdout
    if min(train_size, test_size, final_holdout) <= 0 or development_end < train_size + test_size:
        raise ValueError("Configuración walk-forward insuficiente")
    folds = []
    test_start = train_size
    while test_start + test_size <= development_end:
        train_start = 0 if anchored else test_start - train_size
        folds.append({"train": np.arange(train_start, test_start),
                      "test": np.arange(test_start, test_start + test_size)})
        test_start += test_size
    for fold in folds:
        if np.intersect1d(fold["train"], fold["test"]).size:
            raise AssertionError("Fuga entre entrenamiento y prueba")
    return folds


def bootstrap_expected_value(trade_pnls: Iterable[float], samples: int = 5000,
                             seed: int = 42) -> dict[str, float | None]:
    values = np.asarray(list(trade_pnls), dtype=float)
    if not len(values):
        return {"mean": None, "ci95_lower": None, "ci95_upper": None}
    rng = np.random.default_rng(seed)
    means = np.mean(rng.choice(values, size=(samples, len(values)), replace=True), axis=1)
    return {"mean": float(np.mean(values)), "ci95_lower": float(np.percentile(means, 2.5)),
            "ci95_upper": float(np.percentile(means, 97.5))}


def bonferroni_threshold(experiments: int, alpha: float = 0.05) -> float:
    return alpha / max(int(experiments), 1)


def trade_metrics_by_segment(trades: Iterable[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        groups.setdefault(str(trade.get(field, "unknown")), []).append(trade)
    return {
        name: {
            "trades": len(rows),
            "expected_value": float(np.mean([row["pnl"] for row in rows])),
            "win_rate": sum(row["pnl"] > 0 for row in rows) / len(rows),
            "profit_factor": (
                sum(max(row["pnl"], 0) for row in rows)
                / max(abs(sum(min(row["pnl"], 0) for row in rows)), 1e-12)
            ),
        }
        for name, rows in groups.items()
    }


def sensitivity_summary(base_value: float, perturbed_values: Iterable[float],
                        maximum_relative_degradation: float = 0.25) -> dict[str, Any]:
    values = np.asarray(list(perturbed_values), dtype=float)
    if not len(values) or base_value <= 0:
        return {"robust": False, "worst_relative_degradation": None}
    degradation = (base_value - values) / base_value
    worst = float(np.max(degradation))
    return {"robust": bool(np.all(values > 0) and worst <= maximum_relative_degradation),
            "worst_relative_degradation": worst}


def compare_strategies(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Tabla homogénea; no selecciona ganador ni consulta el test reservado."""
    rows = []
    for name, result in results.items():
        metrics = result.get("metrics", {})
        rows.append({"strategy": name, **{key: metrics.get(key) for key in (
            "total_return", "sharpe", "maximum_drawdown", "profit_factor",
            "expected_value_per_trade", "total_cost",
        )}})
    return rows


def phase8_approval(metrics: dict[str, Any], bootstrap: dict[str, Any], *,
                    benchmark_sharpe: float, profitable_fold_ratio: float,
                    double_costs_viable: bool, sensitivity_robust: bool,
                    fourier_ablation_passed: bool, historical_universe: bool,
                    final_test_untouched: bool) -> dict[str, Any]:
    checks = {
        "expected_value": metrics.get("expected_value_per_trade", 0) > 0
        and bootstrap.get("ci95_lower") is not None and bootstrap["ci95_lower"] >= 0,
        "sharpe": metrics.get("sharpe", 0) >= 1.0
        or metrics.get("sharpe", 0) >= benchmark_sharpe + 0.25,
        "drawdown": abs(metrics.get("maximum_drawdown", -1)) <= 0.15,
        "profit_factor": metrics.get("profit_factor", 0) >= 1.25,
        "profitable_folds": profitable_fold_ratio >= 0.70,
        "concentration": metrics.get("top_5_profit_contribution", 1) < 0.30,
        "double_costs": bool(double_costs_viable),
        "sensitivity": bool(sensitivity_robust),
        "fourier": bool(fourier_ablation_passed),
        "historical_universe": bool(historical_universe),
        "final_test_untouched": bool(final_test_untouched),
    }
    return {"approved": all(checks.values()), "checks": checks,
            "failed": [name for name, passed in checks.items() if not passed]}
