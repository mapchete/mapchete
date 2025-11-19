from __future__ import annotations

import logging
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel
from pyproj import CRS

from mapchete.bounds import Bounds
from mapchete.tile import BufferedTilePyramid
from mapchete.types import CRSLike
from mapchete.zoom_levels import ZoomLevels

OUT_PIXEL_SIZE = 0.28e-3
UNIT_TO_METER = {"mercator": 1, "geodetic": 111319.4907932732}

logger = logging.getLogger(__name__)


def crs_to_authority(crs: CRSLike) -> Tuple[str, str]:
    crs = CRS.from_user_input(crs)
    if crs.to_authority() is None:  # pragma: no cover
        # try with pyproj
        crs = CRS.from_string(crs.to_string())
        if crs.to_authority() is None:
            raise ValueError("cannot convert CRS to authority")
        else:
            authority, code = crs.to_authority()
    else:
        authority, code = crs.to_authority()
    return authority, code


def crs_to_uri(crs: CRSLike, version: int = 0) -> str:
    authority, code = crs_to_authority(crs)
    return f"http://www.opengis.net/def/crs/{authority}/{version}/{code}"


def crs_to_urn(crs: CRSLike) -> str:
    authority, code = crs_to_authority(crs)
    return f"urn:ogc:def:crs:{authority}::{code}"


def _scale(grid, pixel_x_size, default_unit_to_meter=1):
    return (
        UNIT_TO_METER.get(grid, default_unit_to_meter) * pixel_x_size / OUT_PIXEL_SIZE
    )


class BoundingBox(BaseModel):
    type: Literal["BoundingBoxType"] = "BoundingBoxType"
    crs: str
    lowerCorner: List[float]
    upperCorner: List[float]

    @staticmethod
    def from_bounds(bounds: Bounds) -> BoundingBox:
        if bounds.crs is None:
            raise ValueError("bounds.crs must be set")
        return BoundingBox(
            crs=crs_to_uri(bounds.crs),
            upperCorner=[bounds.left, bounds.top],
            lowerCorner=[bounds.right, bounds.bottom],
        )


class TileMatrix(BaseModel):
    type: Literal["TileMatrixType"] = "TileMatrixType"
    identifier: str
    scaleDenominator: float
    topLeftCorner: List[float]
    tileWidth: int
    tileHeight: int
    matrixWidth: int
    matrixHeight: int


class TileMatrixSet(BaseModel):
    type: Literal["TileMatrixSetType"] = "TileMatrixSetType"
    identifier: str
    supportedCRS: str
    tileMatrix: List[TileMatrix]
    boundingBox: BoundingBox
    title: Optional[str] = None
    wellKnownScaleSet: Optional[str] = None
    url: Optional[str] = None

    @staticmethod
    def from_tile_pyramid(
        tile_pyramid: BufferedTilePyramid, zoom_levels: ZoomLevels = ZoomLevels(0, 20)
    ) -> TileMatrixSet:
        grid = tile_pyramid.grid.type
        match grid:
            case "geodetic":
                return TileMatrixSet(
                    identifier="WorldCRS84Quad",
                    title="CRS84 for the World",
                    supportedCRS="http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    url="http://schemas.opengis.net/tms/1.0/json/examples/WorldCRS84Quad.json",
                    wellKnownScaleSet="http://www.opengis.net/def/wkss/OGC/1.0/GoogleCRS84Quad",
                    boundingBox=BoundingBox.from_bounds(
                        Bounds.from_inp(tile_pyramid.bounds, crs=tile_pyramid.crs)
                    ),
                    tileMatrix=[
                        TileMatrix(
                            identifier=str(zoom),
                            scaleDenominator=_scale(
                                grid,
                                tile_pyramid.pixel_x_size(zoom),
                            ),
                            topLeftCorner=[
                                tile_pyramid.bounds.left,
                                tile_pyramid.bounds.top,
                            ],
                            tileWidth=tile_pyramid.tile_width(zoom),
                            tileHeight=tile_pyramid.tile_height(zoom),
                            matrixWidth=tile_pyramid.matrix_width(zoom),
                            matrixHeight=tile_pyramid.matrix_height(zoom),
                        )
                        for zoom in zoom_levels
                    ],
                )
            case "mercator":
                return TileMatrixSet(
                    identifier="WebMercatorQuad",
                    title="Google Maps Compatible for the World",
                    supportedCRS="http://www.opengis.net/def/crs/EPSG/0/3857",
                    url="http://schemas.opengis.net/tms/1.0/json/examples/WebMercatorQuad.json",
                    wellKnownScaleSet="http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible",
                    boundingBox=BoundingBox.from_bounds(
                        Bounds.from_inp(tile_pyramid.bounds, crs=tile_pyramid.crs)
                    ),
                    tileMatrix=[
                        TileMatrix(
                            identifier=str(zoom),
                            scaleDenominator=_scale(
                                grid,
                                tile_pyramid.pixel_x_size(zoom),
                            ),
                            topLeftCorner=[
                                tile_pyramid.bounds.left,
                                tile_pyramid.bounds.top,
                            ],
                            tileWidth=tile_pyramid.tile_width(zoom),
                            tileHeight=tile_pyramid.tile_height(zoom),
                            matrixWidth=tile_pyramid.matrix_width(zoom),
                            matrixHeight=tile_pyramid.matrix_height(zoom),
                        )
                        for zoom in zoom_levels
                    ],
                )
            case _:
                return TileMatrixSet(
                    identifier="custom",
                    supportedCRS=crs_to_urn(tile_pyramid.crs),
                    boundingBox=BoundingBox.from_bounds(
                        Bounds.from_inp(tile_pyramid.bounds, crs=tile_pyramid.crs)
                    ),
                    tileMatrix=[
                        TileMatrix(
                            identifier=str(zoom),
                            scaleDenominator=_scale(
                                grid,
                                tile_pyramid.pixel_x_size(zoom),
                            ),
                            topLeftCorner=[
                                tile_pyramid.bounds.left,
                                tile_pyramid.bounds.top,
                            ],
                            tileWidth=tile_pyramid.tile_width(zoom),
                            tileHeight=tile_pyramid.tile_height(zoom),
                            matrixWidth=tile_pyramid.matrix_width(zoom),
                            matrixHeight=tile_pyramid.matrix_height(zoom),
                        )
                        for zoom in zoom_levels
                    ],
                )

    def to_tile_pyramid(self) -> BufferedTilePyramid:
        match self.wellKnownScaleSet:
            case "http://www.opengis.net/def/wkss/OGC/1.0/GoogleCRS84Quad":
                grid = "geodetic"
            case "http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible":
                grid = "mercator"
            case _:
                raise ValueError("cannot create tile pyramid from unknown scale set")

        # find out metatiling
        metatiling_opts = [2**x for x in range(10)]
        matching_metatiling_opts = []
        for metatiling in metatiling_opts:
            tp = BufferedTilePyramid(grid, metatiling=metatiling)
            for tile_matrix in self.tileMatrix:
                zoom = int(tile_matrix.identifier)
                if (
                    tile_matrix.matrixWidth == tp.matrix_width(zoom)
                    and tile_matrix.matrixHeight == tp.matrix_height(zoom)
                    and tile_matrix.tileWidth == tp.tile_width(zoom)
                    and tile_matrix.tileHeight == tp.tile_height(zoom)
                ):
                    continue
                else:
                    break
            else:
                matching_metatiling_opts.append(metatiling)
        logger.debug("possible metatiling settings: %s", matching_metatiling_opts)
        if len(matching_metatiling_opts) == 0:  # pragma: no cover
            raise ValueError("cannot determine metatiling setting")
        elif len(matching_metatiling_opts) == 1:
            metatiling = matching_metatiling_opts[0]
        else:  # pragma: no cover
            metatiling = sorted(matching_metatiling_opts)[0]
            logger.warning(
                "multiple possible metatiling settings found, chosing %s", metatiling
            )

        # TODO find out pixelbuffer

        return BufferedTilePyramid(grid, metatiling=metatiling)

    def to_zoom_levels(self) -> ZoomLevels:
        return ZoomLevels(
            [int(tile_matrix.identifier) for tile_matrix in self.tileMatrix]
        )
