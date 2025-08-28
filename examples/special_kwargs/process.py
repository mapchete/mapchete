from mapchete import Empty, ProcessTile, PixelBuffer
from mapchete.formats.protocols import RasterInput
from mapchete.tile import BufferedTile


def execute(dem: RasterInput, process_tile: ProcessTile, pixelbuffer: PixelBuffer):
    assert isinstance(process_tile, BufferedTile)
    assert pixelbuffer == 0
    raise Empty
