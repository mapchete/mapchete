from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import datetime
import logging
from typing import Any, Dict, List, Optional

from pystac import Item, get_stac_version
from shapely.geometry import mapping

from mapchete.bounds import Bounds
from mapchete.config.base import get_hash
from mapchete.io.vector import reproject_geometry, to_shape
from mapchete.path import MPath, MPathLike
from mapchete.stac.models import TileMatrixSet
from mapchete.tile import BufferedTilePyramid
from mapchete.types import BoundsLike, ZoomLevelsLike
from mapchete.zoom_levels import ZoomLevels

logger = logging.getLogger(__name__)

TILED_ASSETS_VERSION = "v1.0.0"
EO_VERSION = "v1.1.0"


@dataclass
class STACTA:
    id: str
    tile_pyramid: BufferedTilePyramid
    zoom_levels: ZoomLevels
    stac_version: str = get_stac_version()
    assets: Dict[str, Any] = field(default_factory=dict)
    bounds: Optional[Bounds] = None
    item_metadata: Dict[str, Any] = field(default_factory=dict)
    asset_template: str = field(default="{zoom}/{row}/{col}.tif")
    mime_type: str = field(default="image/tiff; application=geotiff")
    asset_template_name: str = field(default="bands")

    @property
    def geometry(self) -> Dict[str, Any]:
        return mapping(self._stacta_bounds.latlon_geometry())

    @property
    def bbox(self) -> List[float]:
        return list(self._stacta_bounds.latlon_geometry().bounds)

    @property
    def stac_extensions(self) -> List[str]:
        stac_extensions = [
            f"https://stac-extensions.github.io/tiled-assets/{TILED_ASSETS_VERSION}/schema.json",
        ]
        if "eo:bands" in self.item_metadata:
            stac_extensions.append(
                f"https://stac-extensions.github.io/eo/{EO_VERSION}/schema.json"
            )
        return stac_extensions

    @property
    def properties(self) -> Dict[str, Any]:
        out = {
            **self.item_metadata.get("properties", {}),
            "datetime": (
                self.item_metadata.get("properties", {}).get("start_datetime")
                or self.item_metadata.get("properties", {}).get("end_datetime")
                or str(datetime.datetime.now(datetime.timezone.utc))
            ),
            "collection": self.id,
            "tiles:tile_matrix_links": {
                self._tile_matrix_set.identifier: self._tile_matrix_links
            },
            "tiles:tile_matrix_sets": {
                self._tile_matrix_set.identifier: self._tile_matrix_set.model_dump(
                    exclude_none=True
                )
            },
        }
        eo_bands = self.item_metadata.get("eo:bands", None)
        if eo_bands:
            out["eo:bands"] = eo_bands
        return _cleanup_datetime(out)

    @property
    def asset_templates(self) -> Dict[str, Any]:
        out = {
            self.asset_template_name: {
                "href": self.asset_template,
                "type": self.mime_type,
            }
        }
        eo_bands = self.item_metadata.get("eo:bands", None)
        if eo_bands:
            out[self.asset_template_name]["eo:bands"] = self.item_metadata["eo:bands"]

        return out

    @property
    def links(self) -> List[Dict[str, Any]]:
        return self.item_metadata.get("links", [])

    @property
    def _stacta_bounds(self) -> Bounds:
        bounds = Bounds.from_inp(
            self.bounds or self.tile_pyramid.bounds,
            crs=getattr(self.bounds, "crs", None) or self.tile_pyramid.crs,
        )
        tp_bbox = reproject_geometry(
            to_shape(bounds), src_crs=bounds.crs, dst_crs=self.tile_pyramid.crs
        )
        # make sure bounds are not outside tile pyramid bounds
        left, bottom, right, top = tp_bbox.bounds
        left = self.tile_pyramid.left if left < self.tile_pyramid.left else left
        bottom = (
            self.tile_pyramid.bottom if bottom < self.tile_pyramid.bottom else bottom
        )
        right = self.tile_pyramid.right if right > self.tile_pyramid.right else right
        top = self.tile_pyramid.top if top > self.tile_pyramid.top else top

        return Bounds(left, bottom, right, top, crs=self.tile_pyramid.crs)

    @property
    def __geo_interface__(self) -> Dict[str, Any]:
        return self.geometry

    @property
    def _tile_matrix_set(self) -> TileMatrixSet:
        return TileMatrixSet.from_tile_pyramid(
            tile_pyramid=self.tile_pyramid, zoom_levels=self.zoom_levels
        )

    @property
    def _tile_matrix_links(self):
        tp_bbox = reproject_geometry(
            self._stacta_bounds.geometry,
            src_crs=self._stacta_bounds.crs,
            dst_crs=self.tile_pyramid.crs,
        )
        left, bottom, right, top = tp_bbox.bounds
        left = self.tile_pyramid.left if left < self.tile_pyramid.left else left
        bottom = (
            self.tile_pyramid.bottom if bottom < self.tile_pyramid.bottom else bottom
        )
        right = self.tile_pyramid.right if right > self.tile_pyramid.right else right
        top = self.tile_pyramid.top if top > self.tile_pyramid.top else top
        return {
            "url": f"#{self._tile_matrix_set.identifier}",
            "limits": {
                str(zoom): {
                    "min_tile_col": self.tile_pyramid.tile_from_xy(
                        left, top, zoom, on_edge_use="rb"
                    ).col,
                    "max_tile_col": self.tile_pyramid.tile_from_xy(
                        right, bottom, zoom, on_edge_use="lt"
                    ).col,
                    "min_tile_row": self.tile_pyramid.tile_from_xy(
                        left, top, zoom, on_edge_use="rb"
                    ).row,
                    "max_tile_row": self.tile_pyramid.tile_from_xy(
                        right, bottom, zoom, on_edge_use="lt"
                    ).row,
                }
                for zoom in self.zoom_levels
            },
        }

    def __eq__(self, other) -> bool:
        if not isinstance(other, STACTA):  # pragma: no cover
            raise TypeError("can only compare one STACTA instance with another")
        return get_hash(self.to_item_dict()) == get_hash(other.to_item_dict())

    @staticmethod
    def from_tile_pyramid(
        id: str,
        tile_pyramid: BufferedTilePyramid,
        zoom_levels: ZoomLevelsLike,
        asset_template: str = "{zoom}/{row}/{col}.tif",
        bounds: Optional[Bounds] = None,
        item_metadata: Optional[Dict[str, Any]] = None,
        mime_type: str = "image/tiff; application=geotiff",
        asset_template_name: str = "bands",
    ) -> STACTA:
        return STACTA(
            id=id,
            tile_pyramid=tile_pyramid,
            zoom_levels=ZoomLevels.from_inp(zoom_levels),
            asset_template=(
                asset_template.replace("{zoom}", "{TileMatrix}")
                .replace("{row}", "{TileRow}")
                .replace("{col}", "{TileCol}")
                .replace("{extension}", "tif")
            ),
            bounds=bounds,
            item_metadata=item_metadata or {},
            mime_type=mime_type,
            asset_template_name=asset_template_name,
        )

    @staticmethod
    def from_file(path: MPathLike) -> STACTA:
        return STACTA.from_item(Item.from_dict(MPath.from_inp(path).read_json()))

    @staticmethod
    def from_item(item: Item) -> STACTA:
        tile_matrix_sets = item.properties.get("tiles:tile_matrix_sets", [])
        for values in tile_matrix_sets.values():
            # TODO: account for multiple tile matrix sets
            tile_matrix_set = TileMatrixSet.model_validate(values)
            tile_pyramid = tile_matrix_set.to_tile_pyramid()
            zoom_levels = tile_matrix_set.to_zoom_levels()
            break
        else:  # pragma: no cover
            raise ValueError("no 'tiles:tile_matrix_sets' found in STAC item")
        if item.bbox is None:  # pragma: no cover
            raise ValueError("STAC Item has no bbox")
        for asset_template_name, asset_values in item.extra_fields.get(
            "asset_templates", {}
        ).items():
            asset_template = asset_values["href"]
            mime_type = asset_values["type"]
            break
        else:  # pragma: no cover
            raise ValueError("no asset_templates found in STAC item")
        return STACTA(
            id=item.id,
            tile_pyramid=tile_pyramid,
            zoom_levels=zoom_levels,
            stac_version=get_stac_version(),
            assets=item.to_dict()["assets"],
            bounds=Bounds.from_inp(item.bbox),
            item_metadata=item.properties,
            asset_template=asset_template,
            mime_type=mime_type,
            asset_template_name=asset_template_name,
        )

    def extend(
        self,
        zoom_levels: Optional[ZoomLevelsLike] = None,
        bounds: Optional[BoundsLike] = None,
    ):
        if zoom_levels:
            self.zoom_levels = self.zoom_levels.union(zoom_levels)
        if bounds:
            if self.bounds is None:
                self.bounds = Bounds.from_inp(bounds)
            else:
                self.bounds = self.bounds.union(bounds)

    def to_file(
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

    def to_item_dict(self) -> Dict[str, Any]:
        return {
            "type": "Feature",
            "stac_version": self.stac_version,
            "stac_extensions": self.stac_extensions,
            "id": self.id,
            "geometry": self.geometry,
            "bbox": self.bbox,
            "properties": self.properties,
            "links": self.links,
            "assets": self.assets,
            "asset_templates": self.asset_templates,
        }

    def to_item(
        self,
        self_href: Optional[MPathLike] = None,
        asset_basepath: Optional[MPathLike] = None,
        relative_paths: bool = True,
    ) -> Item:
        item_dict = self.to_item_dict()

        if not relative_paths or asset_basepath:
            # add basepath to all asset templates
            if asset_basepath:
                basepath = MPath.from_inp(asset_basepath).absolute_path()
            elif self_href:
                basepath = MPath.from_inp(self_href).absolute_path().parent
            else:
                raise ValueError("either asset_basepath or self_href must be set")
            asset_templates = {}
            for asset_template_name, band_asset_template in item_dict[
                "asset_templates"
            ].items():
                band_asset_template["href"] = str(
                    basepath / band_asset_template["href"]
                )
                asset_templates[asset_template_name] = band_asset_template
            item_dict.update(asset_templates=asset_templates)

        item = Item.from_dict(item_dict)
        if self_href:
            item.set_self_href(str(self_href))

        return item


def _cleanup_datetime(d):
    """Convert datetime objects in dictionary to strings."""
    return OrderedDict(
        (k, _cleanup_datetime(v))
        if isinstance(v, dict)
        else (k, str(v))
        if isinstance(v, datetime.date)
        else (k, v)
        for k, v in d.items()
    )
