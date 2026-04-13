from __future__ import annotations

from types import TracebackType
from typing import (
    Any,
    Callable,
    Generator,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    TYPE_CHECKING,
)

import numpy as np
import numpy.ma as ma
from pydantic import NonNegativeInt
from shapely.geometry.base import BaseGeometry

from mapchete.path import MPath
from mapchete.protocols import GridProtocol
from mapchete.tile import BufferedTile, BufferedTilePyramid
from mapchete.types import (
    BandIndexes,
    BoundsLike,
    CRSLike,
    ResamplingLike,
    GeoJSONLikeFeature,
)

if TYPE_CHECKING:
    from mapchete.processing import MapcheteProcess


class InputTileProtocol(GridProtocol):  # pragma: no cover
    preprocessing_tasks_results: dict
    input_key: str
    tile: BufferedTile

    def read(self, **kwargs) -> Any:
        """Read from input."""
        ...

    def is_empty(self, **kwargs) -> bool:
        """Checks if input is empty here."""
        ...

    def set_preprocessing_task_result(self, task_key: str, result: Any) -> None: ...

    def __enter__(self) -> InputTileProtocol:
        """Required for 'with' statement."""
        return self

    def __exit__(self, *args) -> None:
        """Clean up."""


class RasterInput(InputTileProtocol):  # pragma: no cover
    def read(
        self,
        indexes: Optional[BandIndexes] = None,
        resampling: Optional[ResamplingLike] = None,
        **kwargs,
    ) -> ma.MaskedArray:
        """Read resampled array from input."""
        ...


class VectorInput(InputTileProtocol):  # pragma: no cover
    def read(
        self, validity_check: bool = True, clip_to_crs_bounds: bool = False, **kwargs
    ) -> List[GeoJSONLikeFeature]:
        """Read reprojected and clipped vector features from input."""
        ...

    def read_generator(
        self, validity_check: bool = True, clip_to_crs_bounds: bool = False, **kwargs
    ) -> Generator[GeoJSONLikeFeature, None, None]:
        """Generate reprojected and clipped vector features from input."""
        ...

    def read_union_geometry(
        self,
        validity_check: bool = True,
        clip_to_crs_bounds: bool = False,
        pixelbuffer: int = 0,
        **kwargs,
    ) -> BaseGeometry:
        """Read union of reprojected and clipped vector features."""
        ...

    def read_as_raster_mask(
        self,
        all_touched: bool = False,
        invert: bool = False,
        validity_check: bool = True,
        clip_to_crs_bounds: bool = False,
        pixelbuffer: int = 0,
        band_count: Optional[int] = None,
    ) -> np.ndarray:
        """Read rasterized vector input."""
        ...


RasterInputGroup = List[Tuple[str, RasterInput]]
VectorInputGroup = List[Tuple[str, VectorInput]]


class InputDataProtocol(Protocol):  # pragma: no cover
    input_key: str
    pyramid: BufferedTilePyramid
    pixelbuffer: int = 0
    crs: CRSLike
    preprocessing_tasks: dict = {}
    preprocessing_tasks_results: dict = {}

    def open(self, tile: BufferedTile, **kwargs) -> InputTileProtocol:
        """Return an input instance for a given process tile."""
        ...

    def bbox(self, out_crs: Optional[CRSLike] = None) -> BaseGeometry:
        """Return geometry of input bounding box."""
        ...

    def exists(self) -> bool:
        """Check whether data exists."""
        ...

    def cleanup(self) -> None:
        """Optional cleanup code after processing."""
        ...

    def add_preprocessing_task(
        self,
        func: Callable,
        fargs: Optional[tuple] = None,
        fkwargs: Optional[dict] = None,
        key: Optional[str] = None,
        geometry: Optional[BaseGeometry] = None,
        bounds: Optional[BoundsLike] = None,
    ) -> None: ...

    def get_preprocessing_task_result(self, task_key: str) -> Any: ...

    def set_preprocessing_task_result(self, task_key: str, result: Any) -> None: ...

    def preprocessing_task_finished(self, task_key: str) -> bool: ...


class OutputDataReaderProtocol(Protocol):  # pragma: no cover
    """Minimum interface for any output reader class."""

    pixelbuffer: NonNegativeInt
    pyramid: BufferedTilePyramid
    crs: CRSLike

    def tiles_exist(
        self,
        process_tile: Optional[BufferedTile] = None,
        output_tile: Optional[BufferedTile] = None,
    ) -> bool: ...

    def extract_subset(
        self, input_data_tiles: List[Tuple[BufferedTile, Any]], out_tile: BufferedTile
    ) -> Any: ...

    def read(self, output_tile: BufferedTile) -> Any: ...

    def empty(self, process_tile: BufferedTile) -> Any: ...

    def open(
        self,
        tile: BufferedTile,
        process: "MapcheteProcess",
    ) -> InputTileProtocol: ...

    def for_web(self, data: Any) -> Any: ...


class FileSystemOutputDataReaderProtocol(Protocol):  # pragma: no cover
    """Minimum interface for any filesystem storage based output reader class."""

    def get_path(self, tile: BufferedTile) -> MPath: ...

    # STAC functionality #
    ######################

    @property
    def stac_path(self) -> MPath: ...

    @property
    def stac_item_id(self) -> str: ...

    @property
    def stac_item_metadata(self) -> dict: ...

    @property
    def stac_asset_type(self) -> str: ...


class OutputDataWriterProtocol(OutputDataReaderProtocol):  # pragma: no cover
    use_stac: bool = False

    def write(self, process_tile: BufferedTile, data: Any) -> None: ...

    def output_is_valid(self, process_data: Any) -> bool: ...

    def output_cleaned(self, process_data: Any) -> Any: ...

    def streamline_output(self, process_data: Any) -> Any: ...

    def close(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None: ...


class RasterOutputProtocol(Protocol):  # pragma: no cover
    """Common interface for raster output format drivers."""

    def profile(self, tile: Optional[BufferedTile] = None) -> dict:
        """Create a metadata dictionary for rasterio."""
        ...

    def empty(self, process_tile: BufferedTile) -> ma.MaskedArray:
        """Return empty data as masked array."""
        ...

    def for_web(self, data: Any) -> Tuple[Any, str]:
        """Convert data to web output, returning (data, MIME type)."""
        ...


class VectorOutputProtocol(Protocol):  # pragma: no cover
    """Common interface for vector output format drivers."""

    def empty(self, process_tile: Optional[BufferedTile] = None) -> list:
        """Return empty data as empty list."""
        ...

    def for_web(self, data: Any) -> Tuple[Any, str]:
        """Convert data to web output, returning (data, MIME type)."""
        ...


class OutputConfigValidation(Protocol):  # pragma: no cover
    """Protocol for output drivers that support config validation."""

    def is_valid_with_config(self, config: dict) -> bool:
        """Check if output format is valid with other process parameters."""
        ...


class STACOutputProtocol(Protocol):  # pragma: no cover
    """Protocol for output drivers that support STAC metadata."""

    @property
    def stac_path(self) -> MPath:
        """Return path to STAC JSON file."""
        ...

    @property
    def stac_item_id(self) -> str:
        """Return STAC item ID."""
        ...

    @property
    def stac_item_metadata(self) -> dict:
        """Return custom STAC metadata."""
        ...

    @property
    def stac_asset_type(self) -> str:
        """Return asset MIME type."""
        ...
