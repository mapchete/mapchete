from mapchete import (
    Empty,
    Tile,
    TilePixelBuffer,
    OutputNodataValue,
    TileBuffer,
    OutputPath,
    RasterInput,
)
from mapchete.path import MPath
from mapchete.tile import BufferedTile


def execute(
    dem: RasterInput,
    process_tile: Tile,
    pixelbuffer: TilePixelBuffer,
    buffer: TileBuffer,
    nodata: OutputNodataValue,
    outpath: OutputPath,
):
    # current process tile
    assert isinstance(process_tile, BufferedTile)

    # buffer in pixels around current tile
    assert pixelbuffer == 0

    # buffer in CRS units around current tile
    assert buffer == 0.0

    # assigned nodata value in case of a raster output
    assert nodata == -999

    # output path if available
    assert isinstance(outpath, MPath)

    raise Empty
