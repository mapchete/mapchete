"""Remove tiles from Tile Directory."""

from itertools import chain, islice
import logging
from typing import List, Optional, Union, Dict, Any, Generator, Iterable

from rasterio.crs import CRS
from shapely.geometry.base import BaseGeometry

import mapchete
from mapchete.commands.observer import ObserverProtocol, Observers
from mapchete.io import tiles_exist
from mapchete.path import MPath
from mapchete.types import MPathLike, Progress, BoundsLike

logger = logging.getLogger(__name__)


def rm(
    tiledir: Optional[MPathLike] = None,
    paths: Optional[Iterable[MPath]] = None,
    zoom: Optional[Union[int, List[int]]] = None,
    area: Union[BaseGeometry, str, dict] = None,
    area_crs: Union[CRS, str] = None,
    bounds: Optional[BoundsLike] = None,
    bounds_crs: Union[CRS, str] = None,
    workers: Optional[int] = None,
    fs_opts: Optional[Dict[str, Any]] = None,
    observers: Optional[List[ObserverProtocol]] = None,
    s3_delete_chunksize: int = 1000,
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
    if paths is None and tiledir:
        if zoom is None:  # pragma: no cover
            raise ValueError("zoom level(s) required")
        paths = gen_existing_paths(
            tiledir=MPath.from_inp(tiledir, storage_options=fs_opts),
            zoom=zoom,
            area=area,
            area_crs=area_crs,
            bounds=bounds,
            bounds_crs=bounds_crs,
            workers=workers,
        )
    else:  # pragma: no cover
        raise ValueError("either tiledir or paths have to be provided")

    try:
        # this only works for lists
        total = len(paths)
        all_observers.notify(progress=Progress(total=total))
        logger.debug("got %s path(s)", len(paths))
    except TypeError:
        # we don't know the length of a generator in advance
        total = None

    # create an iterator to have a common interface for lists and generators
    paths_iter = iter(paths)
    # determine the filesystem by getting the first path
    try:
        first_path = next(paths_iter)
    except StopIteration:
        # this happends if the list or generator does not have any item
        logger.debug("no paths to delete")
        return

    fs = first_path.fs
    # append first_path to other paths again
    all_paths = chain((first_path,), paths_iter)

    # s3fs enables multiple paths as input, so let's use this:
    if "s3" in fs.protocol:
        tiles_counter = 0
        while chunk := tuple(islice(all_paths, s3_delete_chunksize)):
            all_observers.notify(
                progress=Progress(
                    current=tiles_counter, total=total or tiles_counter + len(chunk)
                )
            )
            # this actually deletes the files
            fs.rm(chunk)
            for path in chunk:
                tiles_counter += 1
                msg = f"deleted {path}"
                logger.debug(msg)
                all_observers.notify(message=msg)
            all_observers.notify(progress=Progress(current=tiles_counter))

    # otherwise, just iterate through the paths
    else:
        for tiles_counter, path in enumerate(all_paths, 1):
            path.rm()
            msg = f"deleted {path}"
            logger.debug(msg)
            all_observers.notify(
                progress=Progress(current=tiles_counter, total=total or tiles_counter),
                message=msg,
            )

    all_observers.notify(message=f"{tiles_counter} tiles deleted")


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
