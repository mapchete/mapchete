import logging
from typing import Optional

import click

import mapchete
from mapchete.bounds import Bounds
from mapchete.cli import options
from mapchete.config.parse import raw_conf, raw_conf_output_pyramid
from mapchete.formats import read_output_metadata
from mapchete.formats.base import OutputSTACMixin
from mapchete.io import MPath
from mapchete.stac.tiled_assets import STACTA
from mapchete.types import CRSLike
from mapchete.zoom_levels import ZoomLevels

logger = logging.getLogger(__name__)


@click.group(help="Tools to handle STAC metadata.")
def stac():
    pass


@stac.command(help="Create STAC item metadata.")
@options.arg_input
@click.option("--item-id", "-i", type=click.STRING, help="Unique item ID.")
@click.option(
    "--item-metadata",
    "-m",
    type=click.Path(path_type=MPath),
    help="Optional additional item metadata to be appended. Must be a YAML file.",
)
@options.opt_zoom
@click.option(
    "--item-path",
    "-p",
    type=click.Path(path_type=MPath),
    help="Path of output STAC item.",
)
@click.option(
    "--asset-basepath",
    type=click.Path(path_type=MPath),
    help="Alternative asset basepath.",
)
@click.option("--relative-paths", is_flag=True, help="Use relative paths.")
@click.option(
    "--indent",
    type=click.INT,
    default=4,
    help="Indentation for output JSON. (default: 4)",
)
@options.opt_bounds
@options.opt_bounds_crs
@options.opt_force
@options.opt_debug
def create_item(
    input_,
    item_id: str,
    item_metadata: Optional[MPath] = None,
    asset_basepath: Optional[MPath] = None,
    zoom: Optional[ZoomLevels] = None,
    bounds: Optional[Bounds] = None,
    bounds_crs: Optional[CRSLike] = None,
    item_path: Optional[MPath] = None,
    relative_paths: bool = False,
    indent: int = 4,
    force: bool = False,
    **kwargs,
):
    (
        tile_pyramid,
        default_basepath,
        default_id,
        default_bounds,
        default_bounds_crs,
        default_zoom,
        default_item_metadata,
        band_asset_template,
    ) = output_info(input_)

    if relative_paths is False:
        default_basepath = default_basepath.absolute_path()

    if zoom:
        zoom_levels = zoom
    elif default_zoom:
        zoom_levels = default_zoom
    else:  # pragma: no cover
        raise ValueError("zoom must be set")

    if item_metadata:  # pragma: no cover
        metadata = item_metadata.read_yaml()
    else:
        metadata = default_item_metadata or {}

    if default_id in ["./", "."] and not relative_paths:  # pragma: no cover
        item_id = str(default_basepath.name)
    elif default_id in ["./", "."] and relative_paths:  # pragma: no cover
        item_id = default_basepath.absolute_path().name
    else:
        item_id = item_id or metadata.get("id", default_id)

    logger.debug("use item ID %s", item_id)
    item_path = item_path or MPath.from_inp(default_basepath) / f"{item_id}.json"
    if bounds:
        item_bounds = Bounds.from_inp(bounds, crs=bounds_crs or default_bounds_crs)
    elif default_bounds:
        item_bounds = Bounds.from_inp(default_bounds, crs=default_bounds_crs)
    else:
        item_bounds = None
    item = STACTA.from_tile_pyramid(
        id=item_id,
        tile_pyramid=tile_pyramid,
        zoom_levels=zoom_levels,
        asset_template=band_asset_template,
        bounds=item_bounds,
        item_metadata=metadata,
    ).to_item(
        self_href=item_path,
        relative_paths=relative_paths,
        asset_basepath=asset_basepath,
    )
    logger.debug("item_path: %s", item_path)
    click.echo(item.to_dict())
    if force or click.confirm(f"Write output to {item_path}?", abort=True):
        item_path.write_json(item.to_dict())


def output_info(inp):
    path = MPath.from_inp(inp)
    if path.suffix == ".mapchete":
        conf = raw_conf(path)
        default_basepath = MPath.from_inp(conf["output"])
        return (
            raw_conf_output_pyramid(conf),
            default_basepath,
            default_basepath.name,
            conf.get("bounds"),
            conf.get("bounds_crs"),
            conf.get("zoom_levels"),
            conf["output"].get("stac"),
            conf["output"].get("tile_path_schema", "{zoom}/{row}/{col}.{extension}"),
        )

    output_metadata = read_output_metadata(path / "metadata.json")
    return (
        output_metadata["pyramid"],
        path,
        path.name,
        None,
        None,
        None,
        None,
        output_metadata.get("tile_path_schema", "{zoom}/{row}/{col}.{extension}"),
    )


@stac.command(name="create-prototype-files", help="Create STAC item prototype files.")
@options.arg_input
@options.opt_force
@options.opt_debug
def prototype_files(
    input_,
    force=None,
    **kwargs,
):
    with mapchete.open(input_, mode="readonly") as mp:
        output = mp.config.output
        if isinstance(output, OutputSTACMixin):
            output.create_prototype_files()
        else:  # pragma: no cover
            click.echo("output does not support STACTA")
