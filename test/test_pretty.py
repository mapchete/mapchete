import pytest

from mapchete.pretty import pretty_bytes, pretty_seconds


@pytest.mark.parametrize(
    "bytes,string,decimal",
    [
        (2_000, "KiB", False),
        (2_000_000, "MiB", False),
        (2_000_000_000, "GiB", False),
        (2_000, "KB", True),
        (2_000_000, "MB", True),
        (2_000_000_000, "GB", True),
    ],
)
def test_pretty_bytes(bytes, string, decimal):
    assert string in pretty_bytes(bytes, decimal=decimal)


@pytest.mark.parametrize(
    "seconds,string",
    [(61, "m"), (3601, "h"), (1000000000, "thousand hours")],
)
def test_pretty_seconds(seconds, string):
    assert string in pretty_seconds(seconds)
