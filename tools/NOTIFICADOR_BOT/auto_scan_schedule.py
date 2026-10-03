"""Horario seguro del auto-escáner de Bolsa."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    return current + timedelta(days=(weekday - current.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


class _NyseCalendar:
    timezone = ZoneInfo("America/New_York")

    def holidays(self, year: int) -> set[date]:
        holidays = {
            _observed(date(year, 1, 1)), _nth_weekday(year, 1, 0, 3),
            _nth_weekday(year, 2, 0, 3), _easter(year) - timedelta(days=2),
            _last_weekday(year, 5, 0), _observed(date(year, 7, 4)),
            _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 11, 3, 4),
            _observed(date(year, 12, 25)),
        }
        if year >= 2022:
            holidays.add(_observed(date(year, 6, 19)))
        return holidays

    def is_session(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays(day.year)

    def is_half_session(self, day: date) -> bool:
        thanksgiving = _nth_weekday(day.year, 11, 3, 4)
        return self.is_session(day) and day in {
            thanksgiving + timedelta(days=1), date(day.year, 12, 24), date(day.year, 7, 3)
        }

    def next_session(self, after: date) -> date:
        candidate = after + timedelta(days=1)
        while not self.is_session(candidate):
            candidate += timedelta(days=1)
        return candidate


def _aware(value: datetime) -> datetime:
    return value.astimezone() if value.tzinfo is None else value


def nyse_market_is_open(now: datetime | None = None) -> bool:
    """True sólo durante la sesión principal oficial de NYSE."""
    calendar = _NyseCalendar()
    current = _aware(now or datetime.now(timezone.utc)).astimezone(calendar.timezone)
    if not calendar.is_session(current.date()):
        return False
    close_at = time(13, 0) if calendar.is_half_session(current.date()) else time(16, 0)
    return time(9, 30) <= current.time().replace(tzinfo=None) < close_at


def auto_scan_due(now: datetime, last_started: datetime | None,
                  interval_minutes: int = 60) -> bool:
    """Evita duplicados y nunca genera muestras fuera de sesión."""
    if not nyse_market_is_open(now):
        return False
    if last_started is None:
        return True
    current = _aware(now).astimezone(timezone.utc)
    previous = _aware(last_started).astimezone(timezone.utc)
    return current - previous >= timedelta(minutes=max(5, interval_minutes))


def next_nyse_open(now: datetime | None = None) -> datetime:
    calendar = _NyseCalendar()
    current = _aware(now or datetime.now(timezone.utc)).astimezone(calendar.timezone)
    today_open = datetime.combine(current.date(), time(9, 30), calendar.timezone)
    if calendar.is_session(current.date()) and current < today_open:
        return today_open.astimezone(timezone.utc)
    next_day = calendar.next_session(current.date())
    return datetime.combine(next_day, time(9, 30), calendar.timezone).astimezone(timezone.utc)
