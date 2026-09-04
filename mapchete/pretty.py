def pretty_bytes(count: float, round_value: int = 2, decimal: bool = False) -> str:
    """Return human readable bytes."""
    out = ""

    if decimal:
        measurements = ["bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
        divisor = 1000.0
    else:
        measurements = [
            "bytes",
            "KiB",
            "MiB",
            "GiB",
            "TiB",
            "PiB",
            "EiB",
            "ZiB",
            "YiB",
        ]
        divisor = 1024.0

    for measurement in measurements:
        out = f"{round(count, round_value)} {measurement}"
        if count < divisor:
            break
        count /= divisor

    return out


def pretty_seconds(elapsed_seconds: float, round_value: int = 3) -> str:
    """Return human readable seconds."""
    minutes, seconds = divmod(elapsed_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        if hours > 1000:
            return f"{pretty_number(hours, round_value=0)} hours"
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{round(seconds, round_value)}s"


def pretty_number(number: float, round_value: int = 2) -> str:
    """Return human readable, rounded number."""
    out = ""

    for unit in ["", " thousand", " million", " billion", " trillion", " quadrillion"]:
        out = f"{round(number, round_value)}{unit}"
        if number < 1000.0:
            break
        number /= 1000.0
    return out
