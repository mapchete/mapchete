import json

from mapchete.enums import Concurrency
from mapchete.stac.tiled_assets import TILED_ASSETS_VERSION
from mapchete.zoom_levels import ZoomLevels
import pytest
import rasterio
from packaging import version
from shapely.geometry import box, shape

from mapchete import MPath
from mapchete.commands import execute
from mapchete.io import rasterio_open
from mapchete.geometry import reproject_geometry
from mapchete.stac import (
    STACTA,
)
from mapchete.tile import BufferedTilePyramid


@pytest.mark.parametrize(
    "grid,wkss", [("geodetic", "WorldCRS84Quad"), ("mercator", "WebMercatorQuad")]
)
def test_wkss(grid, wkss):
    tp = BufferedTilePyramid(grid)
    item = STACTA.from_tile_pyramid(
        tile_pyramid=tp, id="foo", zoom_levels=ZoomLevels(0, 6)
    ).to_item()
    assert item.id == "foo"
    assert item.geometry
    item_geometry = reproject_geometry(
        shape(item.geometry), src_crs="EPSG:4326", dst_crs=tp.crs
    )
    assert item_geometry.difference(box(*tp.bounds)).area < 5
    assert item.datetime
    assert (
        f"https://stac-extensions.github.io/tiled-assets/{TILED_ASSETS_VERSION}/schema.json"
        in item.stac_extensions
    )
    assert "bands" in item.extra_fields["asset_templates"]
    assert "tiles:tile_matrix_links" in item.properties
    assert "tiles:tile_matrix_sets" in item.properties
    assert wkss in item.properties["tiles:tile_matrix_sets"]


def test_custom_datetime():
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
        item_metadata=dict(start_datetime="2021-01-01 00:00:00"),
    ).to_item()
    assert str(item.datetime) == "2021-01-01 00:00:00"


def test_custom_tilematrix():
    tp = BufferedTilePyramid(
        grid=dict(
            shape=[117, 9],
            bounds=[145980, 0, 883260, 9584640.0],
            is_global=False,
            epsg=32630,
        ),  # type: ignore
        metatiling=4,
    )
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=tp,
        zoom_levels=ZoomLevels(0, 6),
        item_metadata=dict(start_datetime="2021-01-01 00:00:00"),
    ).to_item()
    assert item.datetime
    assert str(item.datetime) == "2021-01-01 00:00:00"
    assert "custom" in item.properties["tiles:tile_matrix_sets"]


def test_tiled_asset_path():
    # default: create absolute path from item basepath
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 0),
    ).to_item(self_href="foo/bar.json", relative_paths=True)
    basepath = item.to_dict()["asset_templates"]["bands"]["href"]
    assert basepath == "{TileMatrix}/{TileRow}/{TileCol}.tif"

    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 0),
    ).to_item(self_href="foo/bar.json", relative_paths=False)
    basepath = item.to_dict()["asset_templates"]["bands"]["href"]
    assert basepath == str(MPath.cwd() / "foo" / "{TileMatrix}/{TileRow}/{TileCol}.tif")

    # use alternative asset basepath
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 0),
    ).to_item(
        self_href="foo/bar.json",
        asset_basepath="s3://bar/",
    )
    basepath = item.to_dict()["asset_templates"]["bands"]["href"]
    assert basepath.startswith("s3://bar/")

    # create relative path
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 0),
    ).to_item(relative_paths=True)
    # native pystac to_dict() translates paths to absolutes and should, I have no idea why this worked before without failing
    # basepath = item.to_dict()["asset_templates"]["bands"]["href"]
    item.make_asset_hrefs_relative()
    # This needs the custom wrapper to work properly, for now
    basepath = item.to_dict()["asset_templates"]["bands"]["href"]
    assert basepath == "{TileMatrix}/{TileRow}/{TileCol}.tif"


def test_tiled_asset_eo_bands_metadata():
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
        item_metadata={"eo:bands": {"foo": "bar"}},
    ).to_item(self_href="foo/bar.json")
    assert (
        "https://stac-extensions.github.io/eo/v1.1.0/schema.json"
        in item.to_dict()["stac_extensions"]
    )
    assert "eo:bands" in item.to_dict()["asset_templates"]["bands"]


def test_create_stac_item_errors():
    tp = BufferedTilePyramid("geodetic")
    # no item_id
    with pytest.raises(TypeError):
        STACTA.from_tile_pyramid(
            tile_pyramid=tp,  # type: ignore
            zoom_levels=ZoomLevels(0, 6),
        )

    # no zoom_level
    with pytest.raises(TypeError):
        STACTA.from_tile_pyramid(
            id="foo",  # type: ignore
            tile_pyramid=tp,
        )

    # no tile_pyramid
    with pytest.raises(TypeError):
        STACTA.from_tile_pyramid(
            id="foo",  # type: ignore
            zoom_levels=ZoomLevels(0, 6),
        )


def test_update_stac():
    stacta_item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 5),
    )
    item = stacta_item.to_item(self_href="foo/bar.json")
    assert (
        len(item.properties["tiles:tile_matrix_sets"]["WorldCRS84Quad"]["tileMatrix"])
        == 6
    )
    stacta_item.extend(zoom_levels=ZoomLevels(6, 7))
    new_item = stacta_item.to_item()
    assert (
        len(
            new_item.properties["tiles:tile_matrix_sets"]["WorldCRS84Quad"][
                "tileMatrix"
            ]
        )
        == 8
    )


def test_update_stac_errors():
    stacta_item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
    )
    with pytest.raises(TypeError):
        stacta_item.extend(tile_pyramid=BufferedTilePyramid("geodetic", metatiling=4))  # type: ignore


def test_tile_pyramid_from_item():
    for metatiling in [1, 2, 4, 8, 16, 64]:
        tp = BufferedTilePyramid("geodetic", metatiling=metatiling)  # type: ignore
        item = STACTA.from_tile_pyramid(
            id="foo",
            tile_pyramid=tp,
            zoom_levels=ZoomLevels(0, 6),
        ).to_item()
        assert tp == STACTA.from_item(item).tile_pyramid


def test_tile_pyramid_from_item_no_tilesets_error():
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
    ).to_item()
    # remove properties including tiled assets information
    item.properties = {}

    with pytest.raises(AttributeError):
        STACTA.from_item(item).tile_pyramid


def test_tile_pyramid_from_item_no_known_wkss_error(custom_grid_json):
    with open(custom_grid_json) as src:
        grid_def = json.loads(src.read())
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid(**grid_def),
        zoom_levels=ZoomLevels(0, 3),
    ).to_item()

    with pytest.raises(ValueError):
        STACTA.from_item(item)


def test_zoom_levels_from_item_errors():
    item = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
    ).to_item()
    # remove properties including tiled assets information
    item.properties = {}
    with pytest.raises(AttributeError):
        STACTA.from_item(item).zoom_levels


@pytest.mark.skipif(
    version.parse(rasterio.__gdal_version__) < version.parse("3.3.0"),
    reason="required STACTA driver is only available in GDAL>=3.3.0",
)
def test_create_prototype_file(cleantopo_br):
    # create sparse tiledirectory with no tiles at row/col 0/0
    execute(cleantopo_br.dict, zoom=[3], concurrency=Concurrency.none)

    stac_path = cleantopo_br.mp().config.output.stac_path
    assert stac_path.exists()

    with rasterio_open(stac_path):
        pass


@pytest.mark.skipif(
    version.parse(rasterio.__gdal_version__) < version.parse("3.3.0"),
    reason="required STACTA driver is only available in GDAL>=3.3.0",
)
def test_create_prototype_file_exists(cleantopo_tl):
    # create sparse tiledirectory with no tiles at row/col 0/0
    execute(cleantopo_tl.dict)

    # read STACTA with rasterio and expect an exception
    stac_path = cleantopo_tl.mp().config.output.stac_path
    assert stac_path.exists()

    # create prototype file and assert reading is possible
    cleantopo_tl.mp().config.output.create_prototype_files()
    with rasterio_open(stac_path):
        pass


def test_stacta_equal():
    first = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
        item_metadata=dict(start_datetime="2021-01-01 00:00:00"),
    )
    second = STACTA.from_tile_pyramid(
        id="foo",
        tile_pyramid=BufferedTilePyramid("geodetic"),
        zoom_levels=ZoomLevels(0, 6),
        item_metadata=dict(start_datetime="2021-01-01 00:00:00"),
    )
    assert first == second

    second.extend(zoom_levels=[7, 8])
    assert first != second


def test_stacta_item(stacta):
    stacta_item = STACTA.from_file(stacta)
    assert stacta_item
    assert not shape(stacta_item).is_empty


def test_tile_paths(stacta):
    stacta = STACTA.from_file(stacta)
    path = stacta.get_tile_path(stacta.tile_pyramid.tile(0, 0, 0))
    assert path.is_absolute()
    item = stacta.to_item()
    item.set_self_href(None)
    stacta = STACTA.from_item(item)
    path = stacta.get_tile_path(stacta.tile_pyramid.tile(0, 0, 0))
    assert not path.is_absolute()
