import pytest
import numpy as np
from retry import retry

from mapchete.io.raster import read_raster_window
from mapchete.io.raster.read import _rasterio_read
from mapchete.settings import IORetrySettings
from mapchete.errors import MapcheteIOError


def test_io_retry_settings_defaults():
    settings = IORetrySettings()
    assert settings.tries == 3
    assert settings.delay == 1.0
    assert settings.backoff == 1.0
    assert isinstance(settings.exceptions, tuple)
    assert len(settings.exceptions) > 0


def test_io_retry_settings_env_vars(monkeypatch):
    monkeypatch.setenv("MAPCHETE_IO_RETRY_TRIES", "5")
    monkeypatch.setenv("MAPCHETE_IO_RETRY_DELAY", "2.0")
    monkeypatch.setenv("MAPCHETE_IO_RETRY_BACKOFF", "3.0")
    settings = IORetrySettings()
    assert settings.tries == 5
    assert settings.delay == 2.0
    assert settings.backoff == 3.0


@pytest.mark.parametrize("exception_class", IORetrySettings().exceptions)
def test_io_retry_catch_exceptions(
    exception_class, fast_io_retry_settings, retry_mock, instantiate_exception
):
    exc_instance = instantiate_exception(exception_class)
    if exc_instance is None:
        pytest.skip(f"Could not instantiate {exception_class.__name__}")

    mock_func = retry_mock(side_effect=[exc_instance, "success"])

    @retry(
        **fast_io_retry_settings.model_dump(exclude_none=True),
    )
    def wrapped_func():
        return mock_func()

    assert wrapped_func() == "success"
    assert mock_func.call_count == 2


def test_io_retry_ignore_other_exceptions(fast_io_retry_settings, retry_mock):
    mock_func = retry_mock(side_effect=[ValueError, "success"])

    @retry(
        **fast_io_retry_settings.model_dump(exclude_none=True),
    )
    def wrapped_func():
        return mock_func()

    with pytest.raises(ValueError):
        wrapped_func()
    assert mock_func.call_count == 1


def test_mapchete_io_error_wrapping_raster(mocker):
    """Verify MapcheteIOError wraps the underlying exception in read_raster_window."""
    from mapchete.grid import Grid

    grid = Grid.from_bounds(bounds=(0, 0, 10, 10), shape=(10, 10), crs="EPSG:3857")

    mock_read = mocker.patch("mapchete.io.raster.read._rasterio_read")
    cause = ConnectionError("retry exhausted")
    mock_read.side_effect = cause

    with pytest.raises(MapcheteIOError) as excinfo:
        read_raster_window("test/testdata/dummy1.tif", grid=grid, indexes=[1])

    assert "failed to read" in str(excinfo.value)
    # Check if cause is anywhere in the chain
    current = excinfo.value
    found = False
    while current:
        if current is cause:
            found = True
            break
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )
    assert found


def test_mapchete_io_error_wrapping_vector(mocker):
    """Verify MapcheteIOError wraps the underlying exception in vector reading."""
    from mapchete.grid import Grid
    from mapchete.io.vector.read import read_vector_window

    grid = Grid.from_bounds(bounds=(0, 0, 10, 10), shape=(10, 10), crs="EPSG:3857")

    mock_read = mocker.patch(
        "mapchete.io.vector.read._get_reprojected_features_from_file"
    )
    cause = ConnectionError("retry exhausted")
    mock_read.side_effect = cause

    with pytest.raises(MapcheteIOError) as excinfo:
        read_vector_window("test/testdata/fiona_test.geojson", grid=grid)

    assert "failed to read" in str(excinfo.value)
    # Check if cause is anywhere in the chain
    current = excinfo.value
    found = False
    while current:
        if current is cause:
            found = True
            break
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )
    assert found


def test_io_retry_integration_rasterio_read(mocker):
    """
    Integration test for _rasterio_read retry behavior.
    """
    from mapchete.grid import Grid

    grid = Grid.from_bounds(bounds=(0, 0, 10, 10), shape=(10, 10), crs="EPSG:3857")

    mock_open = mocker.patch("mapchete.io.raster.read.rasterio.open")
    mock_src = mocker.MagicMock()
    mock_src.indexes = [1]
    mock_src.nodata = 0
    mock_src.meta = {"dtype": "uint8"}
    mock_src.transform.is_identity = False
    mock_src.__enter__.return_value = mock_src

    # 1 failure, 1 success
    mock_open.side_effect = [ConnectionError("retry 1"), mock_src]

    mock_vrt = mocker.patch("mapchete.io.raster.read.WarpedVRT")
    vrt_instance = mock_vrt.return_value
    vrt_instance.__enter__.return_value = vrt_instance
    vrt_instance.read.return_value = np.zeros((1, 10, 10))

    _rasterio_read(input_file="test/testdata/dummy1.tif", dst_grid=grid, indexes=[1])
    assert mock_open.call_count == 2


@pytest.mark.skip(
    reason="mapchete.io.vector.read.py needs fix/update for retry logic as yield of generator does not support retry decorator, as yield does not have materilized object/function"
)
def test_io_retry_integration_fiona_read(mocker):
    """
    Integration test for _get_reprojected_features_from_file retry behavior.
    """
    from mapchete.grid import Grid

    grid = Grid.from_bounds(bounds=(0, 0, 10, 10), shape=(10, 10), crs="EPSG:3857")

    mock_src = mocker.MagicMock()
    mock_src.crs = grid.crs
    mock_src.filter.return_value = []
    mock_src.__enter__.return_value = mock_src

    from mapchete.io.vector.read import read_vector_window

    mock_open = mocker.patch("mapchete.io.vector.read.fiona.open")
    mock_open.side_effect = [ConnectionError("retry 1"), mock_src]

    # ensure it is retried
    read_vector_window("test/testdata/fiona_test.geojson", grid=grid)

    assert mock_open.call_count == 2


def test_io_retry_integration_raster_no_crs(mocker):
    """
    Integration test for read_raster_no_crs retry behavior.
    """
    from mapchete.io.raster.read import read_raster_no_crs

    mock_open = mocker.patch("mapchete.io.raster.read.rasterio.open")
    mock_src = mocker.MagicMock()
    mock_src.read.return_value = "success"
    mock_src.__enter__.return_value = mock_src

    # 1 failure, 1 success
    mock_open.side_effect = [ConnectionError("retry 1"), mock_src]

    result = read_raster_no_crs(input_file="test/testdata/dummy1.tif", indexes=[1])
    assert result == "success"
    assert mock_open.call_count == 2
