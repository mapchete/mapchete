from __future__ import annotations

import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field
from pyproj import CRS
from pystac import Asset, Item, get_stac_version
from shapely.geometry import mapping

from mapchete.bounds import Bounds
from mapchete.errors import ReprojectionFailed
from mapchete.io.vector import reproject_geometry
from mapchete.path import MPath, MPathLike
from mapchete.tile import BufferedTilePyramid
from mapchete.types import CRSLike
from mapchete.zoom_levels import ZoomLevels

TILED_ASSETS_VERSION = "v1.0.0"
EO_VERSION = "v1.1.0"
OUT_PIXEL_SIZE = 0.28e-3
UNIT_TO_METER = {"mercator": 1, "geodetic": 111319.4907932732}


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


def _scale(grid, pixel_x_size, default_unit_to_meter=1):
    return (
        UNIT_TO_METER.get(grid, default_unit_to_meter) * pixel_x_size / OUT_PIXEL_SIZE
    )


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


class TiledAsset(BaseModel):
    name: str
    tile_matrix_set: TileMatrixSet
    tile_matrix_link: dict
    asset_kwargs: dict = {}

    @staticmethod
    def from_item(
        item: Item,
        asset_name: Optional[str] = None,
        tile_matrix_set_name: Optional[str] = None,
    ) -> TiledAsset:
        asset_templates = item.extra_fields.get("asset_templates", {})
        if not asset_templates:
            raise ValueError("STAC item does not contain tiled-assets!")

        tile_matrix_sets = [
            TileMatrixSet(**definition)
            for definition in item.properties["tiles:tile_matrix_sets"].values()
        ]
        if len(asset_templates) == 1:
            for name, asset_kwargs in asset_templates.items():
                tile_matrix_set = tile_matrix_sets[0]
                return TiledAsset(
                    name=name,
                    tile_matrix_set=tile_matrix_set,
                    tile_matrix_link=item.properties["tiles:tile_matrix_links"][
                        tile_matrix_set.identifier
                    ],
                    asset_kwargs=asset_kwargs,
                )
        if asset_name is None:
            raise ValueError(
                "multiple asset templates found, please specify a tiled-asset name"
            )
        for name, asset_kwargs in asset_templates.items():
            if name == asset_name:
                tile_matrix_set = [
                    vv
                    for vv in tile_matrix_sets
                    if vv.identifier == tile_matrix_set_name
                ][0]
                return TiledAsset(
                    name=asset_name,
                    tile_matrix_set=tile_matrix_set,
                    tile_matrix_link=item.properties["tiles:tile_matrix_links"][
                        tile_matrix_set.identifier
                    ],
                    asset_kwargs=asset_kwargs,
                )
        raise KeyError(f"no tiled-asset with name '{asset_name}' found in item")

    @staticmethod
    def from_path(path: MPath) -> TiledAsset:
        return TiledAsset.from_item(
            Item.from_dict((path.parent / path.parent.name + ".json").read_json())
        )

    def to_asset(self, item_href: str, asset_name: Optional[str] = None) -> Asset:
        asset_kwargs = self.asset_kwargs
        asset_kwargs["media_type"] = asset_kwargs.pop("type")
        asset_kwargs.pop("href")
        return Asset(
            href=f"STACTA:{item_href}:{asset_name or self.name}:{self.tile_matrix_set.identifier}",
            **asset_kwargs,
        )


class STACTAItem(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    stac_version: str = get_stac_version()
    assets: Dict[str, Any] = Field(default_factory=dict)

    _tile_pyramid: BufferedTilePyramid = PrivateAttr()
    _zoom_levels: ZoomLevels = PrivateAttr()
    _bounds: Optional[Bounds] = PrivateAttr()
    _item_metadata: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _asset_template: str = PrivateAttr(default="{zoom}/{row}/{col}.tif")
    _mime_type: str = PrivateAttr(default="image/tiff; application=geotiff")
    _asset_template_name: str = PrivateAttr(default="bands")

    # allows for updating values
    model_config = ConfigDict(validate_assignment=True)

    @computed_field
    def geometry(self) -> Dict[str, Any]:
        return mapping(self._stacta_bounds.latlon_geometry())

    @computed_field
    def bbox(self) -> List[float]:
        return self._stacta_bounds.latlon()

    @computed_field
    def stac_extensions(self) -> List[str]:
        stac_extensions = [
            f"https://stac-extensions.github.io/tiled-assets/{TILED_ASSETS_VERSION}/schema.json",
        ]
        if "eo:bands" in self._item_metadata:
            stac_extensions.append(
                f"https://stac-extensions.github.io/eo/{EO_VERSION}/schema.json"
            )
        return stac_extensions

    @computed_field
    def properties(self) -> Dict[str, Any]:
        out = {
            **self._item_metadata.get("properties", {}),
            "datetime": (
                self._item_metadata.get("properties", {}).get("start_datetime")
                or self._item_metadata.get("properties", {}).get("end_datetime")
                or str(datetime.datetime.now(datetime.timezone.utc))
            ),
            "collection": self.id,
            "tiles:tile_matrix_links": {
                self._tile_matrix_set.identifier: self._tile_matrix_links
            },
            "tiles:tile_matrix_sets": {
                self._tile_matrix_set.identifier: self._tile_matrix_set
            },
        }
        eo_bands = self._item_metadata.get("eo:bands", None)
        if eo_bands:
            out["eo:bands"] = eo_bands
        return out

    @computed_field
    def asset_templates(self) -> Dict[str, Any]:
        out = {
            self._asset_template_name: {
                "href": self._asset_template,
                "type": self._mime_type,
            }
        }
        eo_bands = self._item_metadata.get("eo:bands", None)
        if eo_bands:
            out[self._asset_template_name]["eo:bands"] = self._item_metadata["eo:bands"]

        return out

    @computed_field
    def links(self) -> List[Dict[str, Any]]:
        return self._item_metadata.get("links", [])

    @property
    def _stacta_bounds(self) -> Bounds:
        return Bounds.from_inp(
            self._bounds or self._tile_pyramid.bounds,
            crs=getattr(self._bounds, "crs", None) or self._tile_pyramid.crs,
        )

    @property
    def __geo_interface__(self) -> Dict[str, Any]:
        return self.geometry()

    @property
    def _tile_matrix_set(self) -> TileMatrixSet:
        return TileMatrixSet.from_tile_pyramid(
            tile_pyramid=self._tile_pyramid, zoom_levels=self._zoom_levels
        )

    @property
    def _tile_matrix_links(self):
        tp_bbox = reproject_geometry(
            self._stacta_bounds.geometry,
            src_crs=self._stacta_bounds.crs,
            dst_crs=self._tile_pyramid.crs,
        )
        left, bottom, right, top = tp_bbox.bounds
        left = self._tile_pyramid.left if left < self._tile_pyramid.left else left
        bottom = (
            self._tile_pyramid.bottom if bottom < self._tile_pyramid.bottom else bottom
        )
        right = self._tile_pyramid.right if right > self._tile_pyramid.right else right
        top = self._tile_pyramid.top if top > self._tile_pyramid.top else top
        return {
            "url": f"#{self._tile_matrix_set.identifier}",
            "limits": {
                str(zoom): {
                    "min_tile_col": self._tile_pyramid.tile_from_xy(
                        left, top, zoom, on_edge_use="rb"
                    ).col,
                    "max_tile_col": self._tile_pyramid.tile_from_xy(
                        right, bottom, zoom, on_edge_use="lt"
                    ).col,
                    "min_tile_row": self._tile_pyramid.tile_from_xy(
                        left, top, zoom, on_edge_use="rb"
                    ).row,
                    "max_tile_row": self._tile_pyramid.tile_from_xy(
                        right, bottom, zoom, on_edge_use="lt"
                    ).row,
                }
                for zoom in self._zoom_levels
            },
        }

    @staticmethod
    def from_tile_pyramid(
        id: str,
        tile_pyramid: BufferedTilePyramid,
        zoom_levels: ZoomLevels,
        asset_template: str = "{zoom}/{row}/{col}.tif",
        bounds: Optional[Bounds] = None,
        item_metadata: Optional[Dict[str, Any]] = None,
        mime_type: str = "image/tiff; application=geotiff",
        asset_template_name: str = "bands",
    ) -> STACTAItem:
        stacta_item = STACTAItem(
            id=id,
        )
        stacta_item._tile_pyramid = tile_pyramid
        stacta_item._zoom_levels = zoom_levels
        stacta_item._asset_template = (
            asset_template.replace("{zoom}", "{TileMatrix}")
            .replace("{row}", "{TileRow}")
            .replace("{col}", "{TileCol}")
            .replace("{extension}", "tif")
        )
        stacta_item._bounds = bounds
        stacta_item._item_metadata = item_metadata or {}
        stacta_item._mime_type = mime_type
        stacta_item._asset_template_name = asset_template_name
        return stacta_item
        stacta_bounds = Bounds.from_inp(
            bounds or tile_pyramid.bounds,
            crs=getattr(bounds, "crs", None) or tile_pyramid.crs,
        )
        item_metadata = item_metadata or {}
        # item_metadata = _cleanup_datetime(item_metadata or {})
        timestamp = (
            item_metadata.get("properties", {}).get("start_datetime")
            or item_metadata.get("properties", {}).get("end_datetime")
            or str(datetime.datetime.now(datetime.timezone.utc))
        )

        # thumbnail_href = thumbnail_href or "0/0/0.tif"
        # thumbnail_type = thumbnail_type or "image/tiff; application=geotiff"

        # replace zoom, row and col names with STAC tiled-assets definition
        asset_template = (
            asset_template.replace("{zoom}", "{TileMatrix}")
            .replace("{row}", "{TileRow}")
            .replace("{col}", "{TileCol}")
            .replace("{extension}", "tif")
        )

        # bounds in tilepyramid CRS
        tp_bbox = reproject_geometry(
            stacta_bounds.geometry, src_crs=stacta_bounds.crs, dst_crs=tile_pyramid.crs
        )

        # make sure bounds are not outside tile pyramid bounds
        left, bottom, right, top = tp_bbox.bounds
        left = tile_pyramid.left if left < tile_pyramid.left else left
        bottom = tile_pyramid.bottom if bottom < tile_pyramid.bottom else bottom
        right = tile_pyramid.right if right > tile_pyramid.right else right
        top = tile_pyramid.top if top > tile_pyramid.top else top

        try:
            # bounds in lat/lon
            geometry_4326 = stacta_bounds.latlon_geometry()
        except ReprojectionFailed as exc:  # pragma: no cover
            raise ReprojectionFailed(
                f"cannot reproject geometry to EPSG:4326 required by STAC: {str(exc)}"
            )
        tile_matrix_set = TileMatrixSet.from_tile_pyramid(
            tile_pyramid=tile_pyramid, zoom_levels=zoom_levels
        )
        # tiles:tile_matrix_links object:
        tile_matrix_links = {
            "url": f"#{tile_matrix_set.identifier}",
            "limits": {
                str(zoom): {
                    "min_tile_col": tile_pyramid.tile_from_xy(
                        left, top, zoom, on_edge_use="rb"
                    ).col,
                    "max_tile_col": tile_pyramid.tile_from_xy(
                        right, bottom, zoom, on_edge_use="lt"
                    ).col,
                    "min_tile_row": tile_pyramid.tile_from_xy(
                        left, top, zoom, on_edge_use="rb"
                    ).row,
                    "max_tile_row": tile_pyramid.tile_from_xy(
                        right, bottom, zoom, on_edge_use="lt"
                    ).row,
                }
                for zoom in zoom_levels
            },
        }

        stac_extensions = [
            f"https://stac-extensions.github.io/tiled-assets/{TILED_ASSETS_VERSION}/schema.json",
        ]
        if "eo:bands" in item_metadata:
            stac_extensions.append(
                f"https://stac-extensions.github.io/eo/{EO_VERSION}/schema.json"
            )

        out = {
            "stac_version": get_stac_version(),
            "stac_extensions": stac_extensions,
            "id": id,
            "type": "Feature",
            "bbox": stacta_bounds.latlon(),
            "geometry": mapping(geometry_4326),
            "properties": {
                **item_metadata.get("properties", {}),
                "datetime": timestamp,
                "collection": id,
                "tiles:tile_matrix_links": {
                    tile_matrix_set.identifier: tile_matrix_links
                },
                "tiles:tile_matrix_sets": {tile_matrix_set.identifier: tile_matrix_set},
            },
            "asset_templates": {
                asset_template_name: {
                    "href": asset_template,
                    "type": mime_type,
                    "eo:bands": item_metadata.get("eo:bands", None),
                }
            },
            "links": item_metadata.get("links", []),
        }
        if "eo:bands" in item_metadata:
            out["asset_templates"][asset_template_name]

        return STACTAItem(**out)

    @staticmethod
    def from_file(path: MPathLike) -> STACTAItem:
        return STACTAItem.model_validate(MPath.from_inp(path).read_json())

    def update(self, **kwargs: Any) -> None:
        """
        Updates the model in place using the provided keyword arguments.
        Validates assignment due to model_config.
        """
        for field, value in kwargs.items():
            setattr(self, field, value)

    def write(
        self,
        path: MPathLike,
        indent: int = 4,
        asset_basepath: Optional[MPathLike] = None,
        relative_paths: bool = True,
    ):
        MPath.from_inp(path).write_json(
            self.to_item(
                self_href=path,
                asset_basepath=asset_basepath,
                relative_paths=relative_paths,
            ).to_dict(),
            indent=indent,
        )

    def to_item(
        self,
        self_href: Optional[MPathLike] = None,
        asset_basepath: Optional[MPathLike] = None,
        relative_paths: bool = True,
    ) -> Item:
        model_params = self.model_dump(exclude_none=True)

        if not relative_paths or asset_basepath:
            # add basepath to all asset templates
            if asset_basepath:
                basepath = MPath.from_inp(asset_basepath).absolute_path()
            elif self_href:
                basepath = MPath.from_inp(self_href).absolute_path().parent
            else:
                raise ValueError("either asset_basepath or self_href must be set")
            asset_templates = {}
            for asset_template_name, band_asset_template in model_params[
                "asset_templates"
            ].items():
                band_asset_template["href"] = str(
                    basepath / band_asset_template["href"]
                )
                asset_templates[asset_template_name] = band_asset_template
            model_params.update(asset_templates=asset_templates)

        item = Item.from_dict(model_params)
        if self_href:
            item.set_self_href(str(self_href))

        return item
