#!/usr/bin/env python
"""Test custom Mapchete errors."""

from copy import deepcopy

import pytest

import mapchete
from mapchete import errors
from mapchete.config import MapcheteConfig, validate_values
from mapchete.executor import Executor
from mapchete.tile import BufferedTilePyramid


def test_mapchete_init():
    """Raise TypeError if not MapcheteConfig object is passed."""
    with pytest.raises(TypeError):
        mapchete.Mapchete("wrong_type")


def test_config_modes(example_mapchete):
    """Assert process mode is handled correctly."""
    # invalid mode
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(example_mapchete.dict, mode="invalid")


def test_execute(example_mapchete):
    """Mapchete execute() errors."""
    # in readonly mode
    with mapchete.open(example_mapchete.dict, mode="readonly") as mp:
        with pytest.raises(AttributeError):
            mp.execute_tile(next(mp.get_process_tiles()))
    # wrong tile type
    with mapchete.open(example_mapchete.dict) as mp:
        with pytest.raises(TypeError):
            mp.execute_tile("invalid")


def test_read(example_mapchete):
    """Mapchete read() errors."""
    # in memory mode
    with mapchete.open(example_mapchete.dict, mode="memory") as mp:
        with pytest.raises(ValueError):
            mp.read(next(mp.get_process_tiles()))
    # wrong tile type
    with mapchete.open(example_mapchete.dict) as mp:
        with pytest.raises(TypeError):
            mp.read("invalid")


def test_write(cleantopo_tl):
    """Test write function when passing an invalid process_tile."""
    with mapchete.open(cleantopo_tl.dict) as mp:
        # process and save
        with pytest.raises(TypeError):
            mp.write("invalid tile", None)


def test_get_raw_output(example_mapchete):
    """Mapchete get_raw_output() errors."""
    with mapchete.open(example_mapchete.dict) as mp:
        # wrong tile type
        with pytest.raises(TypeError):
            mp.get_raw_output("invalid")
        # not matching CRSes
        tile = BufferedTilePyramid("mercator").tile(7, 1, 1)
        with pytest.raises(NotImplementedError):
            mp.get_raw_output(tile)


def test_process_tile_write(example_mapchete):
    """Raise DeprecationWarning on MapcheteProcess.write()."""
    config = MapcheteConfig(example_mapchete.dict)
    tile = BufferedTilePyramid("mercator").tile(7, 1, 1)
    user_process = mapchete.MapcheteProcess(
        tile=tile,
        params=config.params_at_zoom(tile.zoom),
        input=config.get_inputs_for_tile(tile),
    )
    with pytest.raises(DeprecationWarning):
        user_process.write("data")


def test_process_tile_open(example_mapchete):
    """Raise ValueError on MapcheteProcess.open()."""
    config = MapcheteConfig(example_mapchete.dict)
    tile = BufferedTilePyramid("mercator").tile(7, 1, 1)
    user_process = mapchete.MapcheteProcess(
        tile=tile,
        params=config.params_at_zoom(tile.zoom),
        input=config.get_inputs_for_tile(tile),
    )
    with pytest.raises(ValueError):
        user_process.open("nonexisting_id")


def test_process_tile_read(example_mapchete):
    """Raise ValueError on MapcheteProcess.open()."""
    config = MapcheteConfig(example_mapchete.dict)
    tile = BufferedTilePyramid("mercator").tile(7, 1, 1)
    user_process = mapchete.MapcheteProcess(
        tile=tile,
        params=config.params_at_zoom(tile.zoom),
        input=config.get_inputs_for_tile(tile),
    )
    with pytest.raises(DeprecationWarning):
        user_process.read()


def test_metatiles(example_mapchete):
    """Assert metatile sizes are checked."""
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config["pyramid"].update(metatiling=1)
        config["output"].update(metatiling=2)
        MapcheteConfig(config)


def test_no_cli_input_file(example_mapchete):
    """Assert input file from command line is checked."""
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config.update(input="from_command_line")
        MapcheteConfig(config)


def test_wrong_bounds(example_mapchete):
    """Wrong bounds number raises error."""
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(example_mapchete.dict, bounds=[2, 3])
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(dict(example_mapchete.dict, bounds=[2, 3]))


def test_empty_input_files(example_mapchete):
    """Assert empty input files raises error."""
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        del config["input"]
        MapcheteConfig(config)


def test_mandatory_params(example_mapchete):
    """Check availability of mandatory parameters."""
    for param in ["process", "input", "output"]:
        with pytest.raises(errors.MapcheteConfigError):
            config = deepcopy(example_mapchete.dict)
            del config[param]
            MapcheteConfig(config)
    # invalid path
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config.update(process="invalid/path.py")
        MapcheteConfig(config).process

    # no config dir given
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config.pop("config_dir")
        MapcheteConfig(config).process


def test_invalid_output_params(example_mapchete):
    """Check on invalid configuration."""
    # missing or invalid params
    for param in ["format"]:
        config = deepcopy(example_mapchete.dict)
        with pytest.raises(errors.MapcheteConfigError):
            # invalid
            config["output"][param] = "invalid"
            MapcheteConfig(config)
        with pytest.raises(errors.MapcheteConfigError):
            # missing
            config["output"].pop(param)
            MapcheteConfig(config)


def test_invalid_zoom_levels(example_mapchete):
    """Check on invalid zoom configuration."""
    # process zooms
    # no zoom levels given
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config.pop("zoom_levels")
        with pytest.deprecated_call():
            MapcheteConfig(config)
    # invalid single zoom level
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config.update(zoom_levels=-5)
        MapcheteConfig(config)
    # invalid zoom level in pair
    with pytest.raises(errors.MapcheteConfigError):
        config = deepcopy(example_mapchete.dict)
        config.update(zoom_levels=[-5, 0])
        MapcheteConfig(config)
    # min or max missing
    config = deepcopy(example_mapchete.dict)
    config.update(zoom_levels=dict(min=0))
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(config)
    config.update(zoom_levels=dict(max=5))
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(config)
    # min bigger than max
    config = deepcopy(example_mapchete.dict)
    config.update(zoom_levels=dict(min=5, max=0))

    # init zooms
    # invalid single zoom level
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(config, zoom=-5)
    # invalid zoom level in pair
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(config, zoom=[-5, 0])
    # not a subset
    with pytest.raises(errors.MapcheteConfigError):
        MapcheteConfig(config, zoom=[0, 20])


def test_zoom_dependend_functions(cleantopo_br):
    with mapchete.open(cleantopo_br.dict) as mp:
        with pytest.raises(ValueError):
            mp.config.params_at_zoom(20)
        with pytest.raises(ValueError):
            mp.config.area_at_zoom(20)


def test_validate_values():
    with pytest.raises(TypeError):
        validate_values(None, None)


def test_input_error(cleantopo_br_tiledir):
    config = deepcopy(cleantopo_br_tiledir.dict)
    config["input"].update(file1=dict(format="TileDirectory"))
    with pytest.raises(errors.MapcheteDriverError):
        MapcheteConfig(config)


def test_import_error(mp_tmpdir, cleantopo_br, import_error_py):
    """Assert import error is raised."""
    config = cleantopo_br.dict
    config.update(process=import_error_py)
    with pytest.raises(errors.MapcheteProcessImportError):
        mapchete.open(config)


def test_malformed_process(cleantopo_br, malformed_py):
    """Assert import error is raised."""
    config = cleantopo_br.dict
    config.update(process=malformed_py)
    with pytest.raises(errors.MapcheteProcessImportError):
        mapchete.open(config)


def test_process_import_error(mp_tmpdir, cleantopo_br, import_error_py):
    """Assert import error is raised."""
    config = cleantopo_br.dict
    config.update(process="not.existing.process.module")
    with pytest.raises(errors.MapcheteProcessImportError):
        mapchete.open(config)


def test_syntax_error(mp_tmpdir, cleantopo_br, syntax_error_py):
    """Assert syntax error is raised."""
    config = cleantopo_br.dict
    config.update(process=syntax_error_py)
    with pytest.raises(errors.MapcheteProcessSyntaxError):
        mapchete.open(config)


def test_process_exception(mp_tmpdir, cleantopo_br, process_error_py):
    """Assert process exception is raised."""
    config = cleantopo_br.dict
    config.update(process=process_error_py)
    with mapchete.open(config) as mp:
        with pytest.raises(AssertionError):
            mp.execute_tile((5, 0, 0))


def test_output_error(mp_tmpdir, cleantopo_br, output_error_py):
    """Assert output error is raised."""
    config = cleantopo_br.dict
    config.update(process=output_error_py)
    with mapchete.open(config) as mp:
        with pytest.raises(errors.MapcheteProcessOutputError):
            mp.execute_tile((5, 0, 0))


def _raise_error(i):
    """Helper function for test_finished_task()"""
    1 / 0


def test_finished_task():
    """Encapsulating exceptions test."""
    with pytest.raises(errors.MapcheteTaskFailed):
        next(Executor().as_completed(func=_raise_error, iterable=[0]))


def test_strip_zoom_error(files_zooms):
    with pytest.raises(errors.MapcheteConfigError):
        config = files_zooms.dict
        config["input"]["equals"]["zoom=invalid"] = "dummy1.tif"
        mapchete.open(config)


# ---------------------------------------------------------------------------
# Tests for errors.clean_exception / errors._is_frozen_exc
# ---------------------------------------------------------------------------
# FrozenError and NormalError are also defined in conftest.py for potential reuse.


class FrozenError(Exception):
    """Simulates a Cython/C-extension exception type that rejects attribute assignment.

    ``__slots__`` alone is insufficient on an Exception subclass in CPython
    because the base class provides ``__dict__``. Overriding ``__setattr__``
    is the correct way to reproduce the behaviour of types like
    rasterio._err.CPLE_AppDefinedError.
    """

    def __setattr__(self, name, value):
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


class NormalError(Exception):
    """Plain Python exception – arbitrary attribute assignment is allowed."""


def test_is_frozen_exc_returns_false_for_normal_exception():
    assert errors._is_frozen_exc(NormalError("oops")) is False


def test_is_frozen_exc_returns_true_for_slots_exception():
    assert errors._is_frozen_exc(FrozenError("oops")) is True


def test_clean_exception_none():
    assert errors.clean_exception(None) is None


def test_clean_exception_passthrough_for_normal_exception():
    exc = NormalError("something went wrong")
    result = errors.clean_exception(exc)
    assert result is exc


def test_clean_exception_wraps_frozen_exception():
    exc = FrozenError("gdal error detail")
    result = errors.clean_exception(exc)
    assert isinstance(result, RuntimeError)
    assert "FrozenError" in str(result)
    assert "gdal error detail" in str(result)


def test_clean_exception_preserves_cause_for_normal_exception():
    cause = NormalError("root cause")
    exc = NormalError("outer")
    exc.__cause__ = cause
    result = errors.clean_exception(exc)
    assert result.__cause__ is cause


def test_clean_exception_cleans_frozen_cause():
    frozen_cause = FrozenError("cython detail")
    exc = NormalError("wrapper")
    exc.__cause__ = frozen_cause
    result = errors.clean_exception(exc)
    assert isinstance(result.__cause__, RuntimeError)
    assert "FrozenError" in str(result.__cause__)


def test_clean_exception_cleans_context():
    frozen_ctx = FrozenError("implicit context")
    exc = NormalError("outer")
    exc.__context__ = frozen_ctx
    result = errors.clean_exception(exc)
    assert isinstance(result.__context__, RuntimeError)
    assert "FrozenError" in str(result.__context__)


def test_clean_exception_frozen_outer_survives():
    # FrozenError can't hold __cause__ (slots), so we just verify that
    # clean_exception handles a frozen exc without erroring out.
    exc = FrozenError("cython surface error")
    result = errors.clean_exception(exc)
    assert isinstance(result, RuntimeError)
    assert "FrozenError" in str(result)


def test_is_frozen_exc_type_error_branch():
    """Trigger the TypeError branch in _is_frozen_exc (line 84).

    Some C-extension types raise TypeError (not AttributeError) on setattr.
    """

    class TypeErrorOnSetattr(Exception):
        def __setattr__(self, name, value):
            raise TypeError("immutable type")

    assert errors._is_frozen_exc(TypeErrorOnSetattr("oops")) is True


def test_clean_exception_setattr_attribute_error_on_chain(monkeypatch):
    """Cover the 'except AttributeError: pass' when setting __cause__/__context__
    on safe_exc raises AttributeError (lines 106-107).

    We monkeypatch setattr inside clean_exception so that the second call
    (the one assigning to __cause__/__context__) raises AttributeError.
    """
    call_count = [0]
    _real_setattr = setattr

    def patched_setattr(obj, name, value):
        if name in ("__cause__", "__context__"):
            call_count[0] += 1
            raise AttributeError("blocked")
        _real_setattr(obj, name, value)

    cause = NormalError("cause")
    exc = NormalError("outer")
    exc.__cause__ = cause

    monkeypatch.setattr(errors, "setattr", patched_setattr, raising=False)
    import builtins
    monkeypatch.setattr(builtins, "setattr", patched_setattr)

    result = errors.clean_exception(exc)
    # Despite the blocked setattr, clean_exception must not raise
    assert result is exc


def test_clean_exception_fallback_on_internal_error():
    """Cover the last-resort 'except Exception' fallback (lines 109-111).

    We create an exception whose __str__ raises inside the outer try block
    so that RuntimeError(...) construction fails.
    """

    class StrRaisesError(Exception):
        """Frozen AND __str__ raises, so RuntimeError(f'...{exc}') explodes."""

        def __setattr__(self, name, value):
            raise AttributeError("frozen")

        def __str__(self):
            raise RuntimeError("str() failed")

    exc = StrRaisesError()
    result = errors.clean_exception(exc)
    # Falls through to the bare Exception(str(exc)) fallback
    assert isinstance(result, Exception)
