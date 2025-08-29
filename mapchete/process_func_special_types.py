from pydantic import NonNegativeFloat, NonNegativeInt

from mapchete.path import MPath
from mapchete.tile import BufferedTile
from mapchete.types import NodataVal


# properties related to current process tile
Tile = BufferedTile
TileBuffer = NonNegativeFloat
TilePixelBuffer = NonNegativeInt

# properties related to output
OutputNodataValue = NodataVal
OutputPath = MPath
