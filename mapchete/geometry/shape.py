from typing import Any
from shapely.geometry import shape

from mapchete.geometry.repair import repair as repair_geom
from mapchete.types import GeoInterface, Geometry


def to_shape(geometry: Any, repair: bool = False) -> Geometry:
    """
    Convert geometry to shapely geometry if necessary.

    Parameters
    ----------
    geom : shapely geometry or GeoJSON mapping

    Returns
    -------
    shapely geometry
    """
    try:
        if isinstance(geometry, Geometry):
            pass
        elif isinstance(geometry, dict) and geometry.get("geometry"):
            geometry = shape(geometry["geometry"])
        elif (
            isinstance(geometry, GeoInterface)
            and isinstance(geometry.__geo_interface__, dict)
            and geometry.__geo_interface__.get("geometry")
        ):
            geometry = shape(geometry.__geo_interface__["geometry"])
        else:
            geometry = shape(geometry)  # type: ignore

        return repair_geom(geometry) if repair else geometry

    except Exception:  # pragma: no cover
        raise TypeError(f"invalid geometry type: {type(geometry)}")
