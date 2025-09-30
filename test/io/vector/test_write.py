from fiona.errors import DriverError
import pytest

from mapchete.io.vector import fiona_open, write_vector_window, fiona_write
from mapchete.tile import BufferedTilePyramid


def test_write_vector_window_errors(landpoly):
    with fiona_open(str(landpoly)) as src:
        feature = next(iter(src))
    with pytest.raises((DriverError, ValueError, TypeError)):
        write_vector_window(
            in_data=["invalid", feature],  # type: ignore
            out_tile=BufferedTilePyramid("geodetic").tile(0, 0, 0),
            out_path="/invalid_path",
            out_schema=dict(geometry="Polygon", properties=dict()),  # type: ignore
        )


def test_fiona_write_errors(landpoly, mp_s3_tmpdir):
    test_file = mp_s3_tmpdir / "test.fgb"
    with fiona_open(landpoly) as src:
        feature = next(iter(src))

        with pytest.raises(ZeroDivisionError):
            with fiona_write(test_file, **src.meta) as dst:
                dst.write(feature)
                # force error
                1 / 0  # type: ignore

    # check that file was not created
    with pytest.raises(FileNotFoundError):
        with fiona_open(test_file) as src:
            pass
