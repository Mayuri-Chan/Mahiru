from time import time
from typing import Union

def readable_time(seconds):
	now = time()
	seconds = now-seconds
	day = seconds // 86400
	seconds %= 86400
	hour = seconds // 3600
	seconds %= 3600
	minutes = seconds // 60
	seconds %= 60

	return "%02dd:%02dh:%02dm:%02ds" % (day, hour, minutes, seconds)

def usec() -> int:
    """Returns the current time in microseconds since the Unix epoch."""

    return int(time() * 1000000)

def format_duration_us(t_us: Union[int, float]) -> str:
    """Formats the given microsecond duration as a string."""

    t_us = int(t_us)

    t_ms = t_us / 1000
    t_s = t_ms / 1000
    t_m = t_s / 60
    t_h = t_m / 60
    t_d = t_h / 24

    if t_d >= 1:
        rem_h = t_h % 24
        return "%dd %dh" % (t_d, rem_h)

    if t_h >= 1:
        rem_m = t_m % 60
        return "%dh %dm" % (t_h, rem_m)

    if t_m >= 1:
        rem_s = t_s % 60
        return "%dm %ds" % (t_m, rem_s)

    if t_s >= 1:
        return "%d sec" % t_s

    if t_ms >= 1:
        return "%d ms" % t_ms

    return "%d μs" % t_us
