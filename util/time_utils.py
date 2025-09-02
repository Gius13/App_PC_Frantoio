from datetime import datetime, date
from typing import Any

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Rome")
except Exception:
    from datetime import timezone, timedelta as _td
    TZ = timezone(_td(hours=2))

def fmt_ts(ts_ms: Any) -> str:
        """Converte timestamp (ms) -> 'HH:MM' (solo ora, fuso Europe/Rome)."""
        if ts_ms is None or isinstance(ts_ms, dict):
            return ""
        try:
            ts = int(float(ts_ms))
        except Exception:
            return ""
        return datetime.fromtimestamp(ts / 1000, TZ).strftime("%H:%M")

def day_bounds_ts_ms(d: date):
        start = datetime(d.year, d.month, d.day, 0, 0, tzinfo=TZ)
        end   = datetime(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=TZ)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

def in_day(ts_ms: Any, d: date) -> bool:
        try:
            ts = int(float(ts_ms))
        except Exception:
            return False
        a, b = day_bounds_ts_ms(d)
        return a <= ts <= b
