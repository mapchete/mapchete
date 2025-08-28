from pydantic import NonNegativeFloat, NonNegativeInt

from mapchete.path import MPath
from mapchete.tile import BufferedTile
from mapchete.types import NodataVal


ProcessTile = BufferedTile
PixelBuffer = NonNegativeInt
OutputNodataValue = NodataVal
OutputPath = MPath
Buffer = NonNegativeFloat
