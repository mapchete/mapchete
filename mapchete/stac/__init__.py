from __future__ import annotations

import logging

import numpy as np
import numpy.ma as ma

from mapchete.io.raster import write_raster_window
from mapchete.stac.tiled_assets import STACTA

logger = logging.getLogger(__name__)

__all__ = ["STACTA"]


def create_prototype_files(mp):
    # for each zoom level get tile output for 0/0
    for zoom in mp.config.init_zoom_levels:
        prototype_tile = mp.config.output_pyramid.tile(zoom, 0, 0)
        tile_path = mp.config.output.get_path(prototype_tile)
        # if tile exists, skip
        if tile_path.exists():
            logger.debug("prototype tile %s already exists", tile_path)
        # if not, write empty tile
        else:
            logger.debug("creating prototype tile %s", tile_path)
            out_profile = mp.config.output.profile(prototype_tile)
            tile_path.parent.makedirs()
            write_raster_window(
                in_grid=prototype_tile,
                in_data=ma.masked_array(
                    data=np.full(
                        (out_profile["count"],) + prototype_tile.shape,
                        out_profile["nodata"],
                        dtype=out_profile["dtype"],
                    ),
                    mask=True,
                ),
                out_profile=out_profile,
                out_grid=prototype_tile,
                out_path=tile_path,
                write_empty=True,
            )
