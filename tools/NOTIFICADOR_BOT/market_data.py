"""Contrato canónico y validación de datos de mercado para Inversiones IA."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import pandas as pd


CONTRACT_VERSION = "3.0"
DEFAULT_PROVIDER = "yahoo_chart_v8"
DAILY_STALE_SECONDS = 96 * 60 * 60
INTRADAY_STALE_SECONDS = 5 * 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: Any) -> datetime:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def market_session(market_timestamp: datetime) -> str:
    eastern = market_timestamp.astimezone(ZoneInfo("America/New_York"))
    if eastern.weekday() >= 5:
        return "closed"
    minute = eastern.hour * 60 + eastern.minute
    if 570 <= minute < 960:
        return "regular"
    if 240 <= minute < 570:
        return "pre_market"
    if 960 <= minute < 1200:
        return "after_hours"
    return "closed"


def validate_ohlcv(df: pd.DataFrame) -> dict[str, Any]:
    required = ("Open", "High", "Low", "Close", "Volume")
    missing_columns = [column for column in required if column not in df.columns]
    issues: list[str] = []
    if missing_columns:
        return {
            "valid": False,
            "quality_score": 0.0,
            "completeness": 0.0,
            "issues": [f"missing_columns:{','.join(missing_columns)}"],
        }
    if df.empty:
        return {"valid": False, "quality_score": 0.0, "completeness": 0.0, "issues": ["empty"]}

    numeric = df.loc[:, required].apply(pd.to_numeric, errors="coerce")
    completeness = float(numeric.notna().sum().sum() / numeric.size)
    latest = numeric.iloc[-1]
    if latest.isna().any():
        issues.append("latest_bar_incomplete")
    if float(latest.get("Close", 0) or 0) <= 0:
        issues.append("non_positive_close")
    if float(latest.get("Volume", 0) or 0) < 0:
        issues.append("negative_volume")
    high = latest.get("High")
    low = latest.get("Low")
    open_price = latest.get("Open")
    close = latest.get("Close")
    if pd.notna(high) and pd.notna(low) and pd.notna(open_price) and pd.notna(close):
        if not (low <= open_price <= high and low <= close <= high):
            issues.append("invalid_ohlc_bounds")
    if df.index.has_duplicates:
        issues.append("duplicate_timestamps")
    if not df.index.is_monotonic_increasing:
        issues.append("timestamps_not_monotonic")

    expected_frequency_seconds = None
    gap_count = 0
    if len(df.index) >= 3 and not df.index.has_duplicates:
        utc_index = pd.DatetimeIndex(df.index)
        if utc_index.tz is None:
            utc_index = utc_index.tz_localize("UTC")
        deltas = utc_index.to_series().diff().dropna().dt.total_seconds()
        positive_deltas = deltas[deltas > 0]
        if not positive_deltas.empty:
            expected_frequency_seconds = int(positive_deltas.median())
            if 18 * 60 * 60 <= expected_frequency_seconds <= 30 * 60 * 60:
                # En velas diarias, una separación de tres o cuatro días es
                # normal por fines de semana y feriados. Antes se marcaba cada
                # fin de semana como intervalo perdido y toda la bolsa quedaba
                # artificialmente en calidad 0.90. Contamos únicamente sesiones
                # NYSE que realmente debieron existir entre dos observaciones.
                from prediction_ledger import NyseCalendar

                calendar = NyseCalendar()
                observed_dates = sorted(set(utc_index.date))
                for previous, current in zip(observed_dates, observed_dates[1:]):
                    expected = calendar.next_session(previous)
                    while expected < current:
                        gap_count += 1
                        expected = calendar.next_session(expected)
            else:
                gap_count = int((positive_deltas > expected_frequency_seconds * 1.5).sum())
            if gap_count:
                issues.append(f"missing_intervals:{gap_count}")

    penalties = {
        "latest_bar_incomplete": 0.40,
        "non_positive_close": 0.40,
        "negative_volume": 0.15,
        "invalid_ohlc_bounds": 0.30,
        "duplicate_timestamps": 0.15,
        "timestamps_not_monotonic": 0.10,
    }
    quality = completeness - sum(
        0.10 if issue.startswith("missing_intervals:") else penalties.get(issue, 0)
        for issue in issues
    )
    quality = round(max(0.0, min(1.0, quality)), 4)
    return {
        "valid": not issues and completeness >= 0.995,
        "quality_score": quality,
        "completeness": round(completeness, 4),
        "expected_frequency_seconds": expected_frequency_seconds,
        "gap_count": gap_count,
        "issues": issues,
    }


def reconcile_quotes(primary: Mapping[str, Any], secondary: Mapping[str, Any], tolerance_pct: float = 0.10) -> dict[str, Any]:
    """Compara dos cotizaciones del mismo activo sin ocultar divergencias."""
    if str(primary.get("symbol", "")).upper() != str(secondary.get("symbol", "")).upper():
        raise ValueError("No se pueden reconciliar símbolos diferentes")
    first = float(primary["price"])
    second = float(secondary["price"])
    midpoint = (abs(first) + abs(second)) / 2
    difference_pct = 0.0 if midpoint == 0 else abs(first - second) / midpoint * 100
    return {
        "consistent": difference_pct <= tolerance_pct,
        "difference_pct": round(difference_pct, 6),
        "tolerance_pct": tolerance_pct,
        "primary_provider": primary.get("provider"),
        "secondary_provider": secondary.get("provider"),
        "requires_review": difference_pct > tolerance_pct,
    }


def apply_adjusted_close(df: pd.DataFrame, adjusted_close: Any) -> pd.DataFrame:
    """Ajusta OHLC con el factor oficial de Yahoo y conserva valores crudos.

    El volumen se conserva porque el factor de `adjclose` también incorpora
    dividendos; aplicarlo al volumen produciría unidades artificiales.
    """
    adjusted = pd.Series(adjusted_close, index=df.index, dtype="float64")
    raw_close = pd.to_numeric(df["Close"], errors="coerce")
    factor = (adjusted / raw_close).replace([float("inf"), float("-inf")], pd.NA)
    factor = factor.where(factor > 0).fillna(1.0)
    result = df.copy()
    for column in ("Open", "High", "Low", "Close"):
        result[f"Raw_{column}"] = result[column]
        result[column] = pd.to_numeric(result[column], errors="coerce") * factor
    result["Adjusted_Close"] = adjusted
    result.attrs.update(df.attrs)
    result.attrs["adjusted"] = True
    return result


def quote_from_history(
    symbol: str,
    df: pd.DataFrame,
    *,
    provider: str = DEFAULT_PROVIDER,
    currency: str = "USD",
    interval: str = "1d",
    adjusted: bool = False,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    validation = validate_ohlcv(df)
    if df.empty or "Close" not in df.columns:
        raise ValueError(f"No hay precio canónico para {symbol}")
    price = pd.to_numeric(df["Close"], errors="coerce").iloc[-1]
    if pd.isna(price) or float(price) <= 0:
        raise ValueError(f"Precio inválido para {symbol}")

    market_ts = _as_utc(df.index[-1])
    received = received_at or (_as_utc(df.attrs['fetched_at_utc']) if df.attrs.get('fetched_at_utc') else utc_now())
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    freshness = max(0, int((received.astimezone(timezone.utc) - market_ts).total_seconds()))
    stale_limit = DAILY_STALE_SECONDS if interval.endswith("d") else INTRADAY_STALE_SECONDS
    is_stale = freshness > stale_limit

    quote = {
        "contract_version": CONTRACT_VERSION,
        "symbol": symbol.upper(),
        "price": round(float(price), 6),
        "currency": currency,
        "provider": provider,
        "market_timestamp": _iso_utc(market_ts),
        "received_at": _iso_utc(received),
        "interval": interval,
        "session": market_session(market_ts),
        "adjusted": bool(adjusted),
        "corporate_actions_applied": bool(adjusted),
        "corporate_action_count": int(df.attrs.get("corporate_action_count", 0)),
        "freshness_seconds": freshness,
        "is_stale": is_stale,
        "quality_score": validation["quality_score"],
        "quality_issues": validation["issues"],
    }
    return ensure_quote_contract({'Quote': quote}, received_at=received_at)


def ensure_quote_contract(result: Mapping[str, Any], received_at: datetime | None = None) -> dict[str, Any]:
    existing = result.get("Quote")
    if isinstance(existing, dict) and existing.get("contract_version") == CONTRACT_VERSION:
        quote = dict(existing)
        now = received_at or utc_now()
        try:
            from auto_scan_schedule import nyse_market_is_open
            market_ts = _as_utc(quote['market_timestamp'])
            downloaded = _as_utc(quote['received_at'])
            age = max(0, int((now - market_ts).total_seconds()))
            download_age = max(0, int((now - downloaded).total_seconds()))
            daily = str(quote.get('interval', '')).endswith('d')
            limit = DAILY_STALE_SECONDS if daily else INTRADAY_STALE_SECONDS
            quote['freshness_seconds'] = age
            quote['received_age_seconds'] = download_age
            # La fecha de una vela diaria es su apertura, no la hora de la
            # última cotización. Durante sesión el snapshot debe renovarse.
            quote['is_stale'] = age > limit or (nyse_market_is_open(now) and download_age > 900)
            quote['evaluated_at'] = _iso_utc(now)
        except (ValueError, TypeError, KeyError):
            quote['is_stale'] = True
        return quote
    received = received_at or utc_now()
    symbol = str(result.get("Ticker") or result.get("ticker") or "UNKNOWN").upper()
    price = result.get("Price", result.get("price"))
    return {
        "contract_version": CONTRACT_VERSION,
        "symbol": symbol,
        "price": float(price) if price is not None else None,
        "currency": "USD",
        "provider": "legacy_unknown",
        "market_timestamp": None,
        "received_at": _iso_utc(received),
        "interval": "unknown",
        "session": "unknown",
        "adjusted": False,
        "corporate_actions_applied": False,
        "corporate_action_count": 0,
        "freshness_seconds": None,
        "is_stale": True,
        "quality_score": 0.0,
        "quality_issues": ["legacy_missing_metadata"],
    }


def exchange_rate_contract(rate: float, received_at: datetime | None = None) -> dict[str, Any]:
    received = received_at or utc_now()
    return {
        "contract_version": CONTRACT_VERSION,
        "pair": "USD/MXN",
        "rate": round(float(rate), 6),
        "provider": "yahoo_chart_v8",
        "received_at": _iso_utc(received),
    }
