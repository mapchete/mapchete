"""Remove tiles from Tile Directory."""

from itertools import chain, islice
import logging
from types import GeneratorType
from typing import List, Optional, Union, Dict, Any, Generator

from rasterio.crs import CRS
from shapely.geometry.base import BaseGeometry

import mapchete
from mapchete.commands.observer import ObserverProtocol, Observers
from mapchete.io import tiles_exist
from mapchete.path import MPath
from mapchete.types import MPathLike, Progress, BoundsLike

logger = logging.getLogger(__name__)


S3_DELETE_CHUNKSIZE = 1000


def rm(
    tiledir: Optional[MPathLike] = None,
    paths: Optional[Union[List[MPath], Generator[MPath, None, None]]] = None,
    zoom: Optional[Union[int, List[int]]] = None,
    area: Union[BaseGeometry, str, dict] = None,
    area_crs: Union[CRS, str] = None,
    bounds: Optional[BoundsLike] = None,
    bounds_crs: Union[CRS, str] = None,
    workers: Optional[int] = None,
    fs_opts: Optional[Dict[str, Any]] = None,
    observers: Optional[List[ObserverProtocol]] = None,
):
    """
    Remove tiles from TileDirectory.

    Parameters
    ----------
    tiledir : str
        TileDirectory or mapchete file.
    zoom : integer or list of integers
        Single zoom, minimum and maximum zoom or a list of zoom levels.
    area : str, dict, BaseGeometry
        Geometry to override bounds or area provided in process configuration. Can be either a
        WKT string, a GeoJSON mapping, a shapely geometry or a path to a Fiona-readable file.
    area_crs : CRS or str
        CRS of area (default: process CRS).
    bounds : tuple
        Override bounds or area provided in process configuration.
    bounds_crs : CRS or str
        CRS of area (default: process CRS).
    fs_opts : dict
        Configuration options for fsspec filesystem.
    """
    all_observers = Observers(observers)
    if isinstance(paths, (list, GeneratorType)):
        pass
    elif tiledir:
        if zoom is None:  # pragma: no cover
            raise ValueError("zoom level(s) required")
        tiledir = MPath.from_inp(tiledir, storage_options=fs_opts)
        paths = gen_existing_paths(
            tiledir=tiledir,
            zoom=zoom,
            area=area,
            area_crs=area_crs,
            bounds=bounds,
            bounds_crs=bounds_crs,
            workers=workers,
        )
    else:  # pragma: no cover
        raise ValueError(
            "either a tile directory or a list of paths has to be provided"
        )

    if isinstance(paths, list):
        total = len(paths)
        if not paths:
            logger.debug("no paths to delete")
            return
        all_observers.notify(progress=Progress(total=total))
        logger.debug("got %s path(s)", len(paths))
    else:
        total = None

    # create an iterator to have a common interface for lists and generators
    paths_iter = iter(paths)
    # determine the filesystem by getting the first path
    try:
        first_path = next(paths_iter)
    except StopIteration:
        logger.debug("no paths to delete")
        return
    fs = first_path.fs

    # s3fs enables multiple paths as input, so let's use this:
    if "s3" in fs.protocol:
        ii = 0
        while chunk := tuple(
            islice(chain((first_path,), paths_iter), S3_DELETE_CHUNKSIZE)
        ):
            all_observers.notify(
                progress=Progress(current=ii, total=total or ii + len(chunk))
            )
            # this actually deletes the files
            fs.rm(chunk)
            for path in chunk:
                ii += 1
                msg = f"deleted {path}"
                logger.debug(msg)
                all_observers.notify(message=msg)
            all_observers.notify(progress=Progress(current=ii))

    # otherwise, just iterate through the paths
    else:
        for ii, path in enumerate(chain((first_path,), paths_iter), 1):
            path.rm()
            msg = f"deleted {path}"
            logger.debug(msg)
            all_observers.notify(
                progress=Progress(current=ii, total=total or ii), message=msg
            )

    all_observers.notify(message=f"{ii} tiles deleted")


def gen_existing_paths(
    tiledir: MPathLike,
    zoom: Optional[Union[int, List[int]]] = None,
    area: Union[BaseGeometry, str, dict] = None,
    area_crs: Union[CRS, str] = None,
    bounds: Optional[BoundsLike] = None,
    bounds_crs: Union[CRS, str] = None,
    workers: Optional[int] = None,
) -> Generator[MPath, None, None]:
    with mapchete.open(
        tiledir,
        zoom=zoom,
        area=area,
        area_crs=area_crs,
        bounds=bounds,
        bounds_crs=bounds_crs,
        mode="readonly",
    ) as mp:
        tp = mp.config.output_pyramid
        for zoom in mp.config.init_zoom_levels:
            # check which source tiles exist
            logger.debug("looking for existing source tiles in zoom %s...", zoom)
            for tile, exists in tiles_exist(
                config=mp.config,
                output_tiles_batches=tp.tiles_from_geom_batches(
                    mp.config.area_at_zoom(zoom), zoom
                ),
                workers=workers,
            ):
                if exists:
                    logger.debug("yield tile %s", tile)
                    yield mp.config.output_reader.get_path(tile)


def existing_paths(
    tiledir: MPathLike,
    zoom: Optional[Union[int, List[int]]] = None,
    area: Union[BaseGeometry, str, dict] = None,
    area_crs: Union[CRS, str] = None,
    bounds: Optional[BoundsLike] = None,
    bounds_crs: Union[CRS, str] = None,
    workers: Optional[int] = None,
) -> List[MPath]:
    return [
        tile
        for tile in gen_existing_paths(
            tiledir=tiledir,
            zoom=zoom,
            area=area,
            area_crs=area_crs,
            bounds=bounds,
            bounds_crs=bounds_crs,
            workers=workers,
        )
    ]
