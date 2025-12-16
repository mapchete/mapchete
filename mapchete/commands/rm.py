"""Remove tiles from Tile Directory."""

import logging
from typing import List, Optional, Union, Dict, Any

from rasterio.crs import CRS
from shapely.geometry.base import BaseGeometry

import mapchete
from mapchete.commands.observer import ObserverProtocol, Observers
from mapchete.io import tiles_exist
from mapchete.path import MPath
from mapchete.types import MPathLike, Progress, BoundsLike
from mapchete.tile import BufferedTile

logger = logging.getLogger(__name__)


def rm(
    tiledir: Optional[MPathLike] = None,
    paths: Optional[List[MPath]] = None,
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

    if tiledir:
        if zoom is None:  # pragma: no cover
            raise ValueError("zoom level(s) required")
        tiledir = MPath.from_inp(tiledir, storage_options=fs_opts)
        paths = existing_paths(
            tiledir=tiledir,
            zoom=zoom,
            area=area,
            area_crs=area_crs,
            bounds=bounds,
            bounds_crs=bounds_crs,
            workers=workers,
        )
    elif isinstance(paths, list):
        pass
    else:  # pragma: no cover
        raise ValueError(
            "either a tile directory or a list of paths has to be provided"
        )

    if not paths:
        logger.debug("no paths to delete")
        return

    all_observers.notify(progress=Progress(total=len(paths)))
    logger.debug("got %s path(s)", len(paths))

    # s3fs enables multiple paths as input, so let's use this:
    if "s3" in paths[0].protocols:
        paths[0].fs.rm(paths)
        for ii, path in enumerate(paths, 1):
            msg = f"deleted {path}"
            logger.debug(msg)
            all_observers.notify(
                progress=Progress(current=ii, total=len(paths)), message=msg
            )

    # otherwise, just iterate through the paths
    else:
        for ii, path in enumerate(paths, 1):
            path.rm()
            msg = f"deleted {path}"
            logger.debug(msg)
            all_observers.notify(
                progress=Progress(current=ii, total=len(paths)), message=msg
            )

    all_observers.notify(message=f"{len(paths)} tiles deleted")


def existing_paths(
    tiledir: MPathLike,
    zoom: Optional[Union[int, List[int]]] = None,
    area: Union[BaseGeometry, str, dict] = None,
    area_crs: Union[CRS, str] = None,
    bounds: Optional[BoundsLike] = None,
    bounds_crs: Union[CRS, str] = None,
    workers: Optional[int] = None,
) -> List[MPath]:
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
        tiles: Dict[Union[int, List[int], None], List[BufferedTile]] = {}
        for zoom in mp.config.init_zoom_levels:
            tiles[zoom] = []
            # check which source tiles exist
            logger.debug("looking for existing source tiles in zoom %s...", zoom)
            for tile, exists in tiles_exist(
                config=mp.config,
                output_tiles=(
                    tile_
                    for tile_ in tp.tiles_from_geom(mp.config.area_at_zoom(zoom), zoom)
                    # this is required to omit tiles touching the config area
                    if mp.config.area_at_zoom(zoom).intersection(tile_.bbox).area
                ),
                workers=workers,
            ):
                if exists:
                    tiles[zoom].append(tile)

        return [
            mp.config.output_reader.get_path(tile)
            for zoom_tiles in tiles.values()
            for tile in zoom_tiles
        ]
