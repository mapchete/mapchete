from pydantic import NonNegativeInt

from mapchete.tile import BufferedTile


class ProcessTile(BufferedTile):
    """Special class indicating a process tile."""


class PixelBuffer(NonNegativeInt):
    """Special class indicating current process tile pixelbuffer."""
