"""Errors and Warnings."""


class MapcheteProcessImportError(ImportError):
    """Raised when a module of a mapchete process cannot be imported."""


class MapcheteProcessSyntaxError(SyntaxError):
    """Raised when mapchete process file cannot be imported."""


class MapcheteProcessException(Exception):
    """Raised when a mapchete process execution fails."""


class MapcheteTaskFailed(Exception):
    """Raised when a task fails."""


class MapcheteProcessOutputError(ValueError):
    """Raised when a mapchete process output is invalid."""


class MapcheteConfigError(ValueError):
    """Raised when a mapchete process configuration is invalid."""


class MapcheteDriverError(Exception):
    """Raised on input or output driver errors."""


class MapcheteEmptyInputTile(Exception):
    """Generic exception raised by a driver if input tile is empty."""


class MapcheteNodataTile(Exception):
    """Indicates an empty tile."""


class Empty(MapcheteNodataTile):
    """Short alias for MapcheteNodataTile."""


class GeometryTypeError(TypeError):
    """Raised when geometry type does not fit."""


class MapcheteIOError(IOError):
    """Raised when mapchete cannot read a file."""


class JobCancelledError(Exception):
    """Raised when Job gets cancelled."""


class NoTaskGeometry(TypeError):
    """Raised when Task has no assigned geo information."""


class ReprojectionFailed(RuntimeError):
    """Raised when geometry cannot be reprojected."""


class NoGeoError(AttributeError):
    """Raised when object does not contain geographic information."""


class NoCRSError(AttributeError):
    """Raised when object does not contain a CRS."""


def _is_frozen_exc(exc: Exception) -> bool:
    """Return True if the exception type does not support attribute assignment.

    Cython extension types (e.g. rasterio._err.CPLE_AppDefinedError) typically
    raise AttributeError when you try to set arbitrary attributes, which causes
    tblib/dask unpickling to fail in distributed environments.
    """
    _watcher = "_clean_exception_probe"
    try:
        setattr(exc, _watcher, None)
        delattr(exc, _watcher)
        return False
    except (AttributeError, TypeError):
        return True


def clean_exception(exc: Exception) -> Exception:
    """Sanitize an exception chain so it can be safely pickled by tblib/dask.

    Replaces any exception whose type does not support attribute assignment
    (e.g. Cython extension types) with an equivalent ``RuntimeError``, then
    recurses into ``__cause__`` and ``__context__`` to clean the full chain.
    """
    if exc is None:
        return None

    try:
        safe_exc = (
            RuntimeError(f"{type(exc).__name__}: {exc}") if _is_frozen_exc(exc) else exc
        )
        for attr in ("__cause__", "__context__"):
            if (chained := getattr(exc, attr, None)) is not None:
                try:
                    setattr(safe_exc, attr, clean_exception(chained))
                except AttributeError:
                    pass
        return safe_exc
    except Exception:
        # last-resort fallback if reconstruction itself fails
        return Exception(str(exc))
