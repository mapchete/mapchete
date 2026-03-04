from __future__ import annotations

from itertools import chain
import logging
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple, Union, Generator
import warnings

from fiona import Collection
from rasterio.crs import CRS
from retry import retry
from shapely import GeometryCollection, prepare, unary_union
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree
from mapchete.bounds import Bounds
from mapchete.errors import NoCRSError, NoGeoError
from mapchete.geometry.filter import is_type
from mapchete.geometry.reproject import reproject_geometry
from mapchete.geometry.shape import to_shape
from mapchete.geometry.types import GeometryTypeLike
from mapchete.grid import Grid
from mapchete.io.vector.open import fiona_open
from mapchete.io.vector.read import read_vector_window, reprojected_features
from mapchete.io.vector.types import FeatureCollectionProtocol
from mapchete.protocols import GridProtocol
from mapchete.settings import IORetrySettings
from mapchete.timer import Timer
from mapchete.types import BoundsLike, CRSLike, MPathLike, GeoJSONLikeFeature, Geometry


logger = logging.getLogger(__name__)
IndexType = Literal["rtree", "strtree"]


class FakeIndex:
    """Provides a fake spatial index in case rtree is not installed."""

    _items: List[Tuple[int, Bounds]]

    def __init__(self):
        self._items = []

    def insert(self, id: int, bounds: BoundsLike):
        self._items.append((id, Bounds.from_inp(bounds)))

    def intersection(self, bounds: BoundsLike) -> List[int]:
        return [id for id, i_bounds in self._items if i_bounds.intersects(bounds)]


class STRtreeIndex:
    """Wrapper around shapely.strtree.STRtree."""

    _ids: List[int]
    _bounds: List[Bounds]
    _tree: STRtree

    def __init__(self):
        self._ids = []
        self._bounds = []
        self._tree = None

    def tree(self) -> STRtree:
        if self._tree is None:
            logger.debug("build STRtree index before first use ...")
            self._tree = STRtree([bounds.geometry for bounds in self._bounds])
            # empty bounds list because we don't need it anymore
            self._bounds = []

        return self._tree

    def insert(self, id: int, bounds: BoundsLike):
        self._ids.append(id)
        self._bounds.append(Bounds.from_inp(bounds))

    def intersection(self, bounds: BoundsLike) -> List[int]:
        return [
            self._ids[_id]
            for _id in self.tree().query(
                Bounds.from_inp(bounds).geometry, predicate="intersects"
            )
        ]


class IndexedFeatures(FeatureCollectionProtocol):
    """
    Behaves like a mapping of GeoJSON-like objects but has a filter() method.

    Parameters
    ----------
    features : iterable
        Features to be indexed
    index : string
        Spatial index to use. Can either be "rtree" (if installed) or None.
    """

    crs: Optional[CRSLike]
    bounds: Optional[Bounds]
    _items: Dict[int, Any]

    def __init__(
        self,
        features: Iterable[Any],
        index: Optional[IndexType] = "strtree",
        allow_non_geo_objects: bool = False,
        crs: Optional[CRSLike] = None,
    ):
        if index == "strtree":
            self._index = STRtreeIndex()
        elif index == "rtree":
            try:
                import rtree

                self._index = rtree.index.Index()
            except ImportError:  # pragma: no cover
                warnings.warn("rtree not installed, falling back to STRtree.")
                self._index = STRtreeIndex()
        else:
            self._index = FakeIndex()
        self.crs = crs or getattr(features, "crs", None)
        self._items = {}
        self._non_geo_items = set()
        self.bounds = None
        with Timer() as duration:
            for counter, feature in enumerate(features):
                if isinstance(feature, tuple):
                    id_, feature = feature
                else:
                    try:
                        id_ = object_id(feature)
                    except TypeError:
                        # use feature position in interable as ID
                        id_ = counter
                self._items[id_] = feature
                try:
                    try:
                        bounds = object_bounds(feature, dst_crs=crs)
                    except NoCRSError:  # pragma: no cover
                        bounds = object_bounds(feature)
                except NoGeoError:
                    if allow_non_geo_objects:
                        bounds = None
                    else:
                        raise
                if bounds is None:
                    self._non_geo_items.add(id_)
                else:
                    self._update_bounds(bounds)
                    self._index.insert(id_, bounds)
                if counter % 100 == 0:
                    logger.debug("%s features read after %s", counter, duration)

    def __repr__(self):  # pragma: no cover
        return f"IndexedFeatures(features={len(self)}, index={self._index.__repr__()}, bounds={self.bounds})"

    def __len__(self):
        return len(self._items)

    def __str__(self):  # pragma: no cover
        return "IndexedFeatures([%s])" % (", ".join([str(f) for f in self]))

    def __getitem__(self, key: int):
        try:
            return self._items[hash(key)]
        except KeyError:
            raise KeyError(f"no feature with id {key} exists")

    def __iter__(self):
        return iter(self._items.values())

    def items(self):
        return self._items.items()

    def keys(self) -> Iterable[int]:
        return self._items.keys()

    def values(self) -> Iterable[Any]:
        return self._items.values()

    def filter(
        self,
        bounds: Optional[BoundsLike] = None,
        bbox: Optional[BoundsLike] = None,
        target_geometry_type: Optional[
            Union[GeometryTypeLike, Tuple[GeometryTypeLike]]
        ] = None,
    ) -> List[Any]:
        """
        Return features intersecting with bounds.

        Parameters
        ----------
        bounds : list or tuple
            Bounding coordinates (left, bottom, right, top).

        Returns
        -------
        features : list
            List of features.
        """
        filter_bounds = bounds or bbox
        out_features = self.values()
        if filter_bounds:
            bounds = Bounds.from_inp(filter_bounds)
            out_features = (
                self._items[id_]
                for id_ in chain(self._index.intersection(bounds), self._non_geo_items)
            )
        if target_geometry_type is not None:
            out_features = (
                feature
                for feature in out_features
                if is_type(object_geometry(feature), target_geometry_type)
            )
        return list(out_features)

    def intersects(self, geometry: BaseGeometry) -> bool:
        """Check if geometry intersects with any of the features."""
        for feature in self.filter(bounds=geometry.bounds):
            try:
                if object_geometry(feature).intersects(geometry):
                    return True
            except NoGeoError:
                continue
        return False

    def read(
        self,
        grid: Optional[Union[Grid, GridProtocol]] = None,
        target_geometry_type: Optional[
            Union[GeometryTypeLike, Tuple[GeometryTypeLike]]
        ] = None,
    ) -> List[GeoJSONLikeFeature]:
        if grid:
            return list(
                reprojected_features(
                    self, grid=grid, target_geometry_type=target_geometry_type
                )
            )
        return self.filter(target_geometry_type=target_geometry_type)

    def read_union_geometry(
        self,
        bounds: Optional[BoundsLike] = None,
        clip: bool = False,
        target_geometry_type: Optional[
            Union[GeometryTypeLike, Tuple[GeometryTypeLike]]
        ] = None,
    ) -> Geometry:
        geoms = list(
            self.generate_geometries(
                bounds=bounds, clip=clip, target_geometry_type=target_geometry_type
            )
        )
        if geoms:
            logger.debug("creating union geometry ...")
            with Timer() as duration:
                union = unary_union(geoms)
            logger.debug("union geometry created in %s", duration)
            return union
        return GeometryCollection()

    def read_geometry_collection(
        self,
        bounds: Optional[BoundsLike] = None,
        clip: bool = False,
        target_geometry_type: Optional[
            Union[GeometryTypeLike, Tuple[GeometryTypeLike]]
        ] = None,
    ) -> GeometryCollection:
        with Timer() as duration:
            geom_collection = GeometryCollection(
                list(
                    self.generate_geometries(
                        bounds=bounds,
                        clip=clip,
                        target_geometry_type=target_geometry_type,
                    )
                )
            )
        logger.debug("geometry collection created in %s", duration)
        return geom_collection

    def generate_geometries(
        self,
        bounds: Optional[BoundsLike] = None,
        clip: bool = False,
        target_geometry_type: Optional[
            Union[GeometryTypeLike, Tuple[GeometryTypeLike]]
        ] = None,
    ) -> Generator[Geometry, None, None]:
        if bounds and clip:
            bounds_geom = to_shape(Bounds.from_inp(bounds))
            prepare(bounds_geom)
            for feature in self.filter(
                bounds=bounds, target_geometry_type=target_geometry_type
            ):
                geom = bounds_geom.intersection(to_shape(feature))
                if not geom.is_empty:
                    yield geom
        else:
            for feature in self.filter(
                bounds=bounds, target_geometry_type=target_geometry_type
            ):
                yield to_shape(feature)

    def _update_bounds(self, bounds: BoundsLike):
        bounds = Bounds.from_inp(bounds)
        if self.bounds is None:
            self.bounds = bounds
        else:
            self.bounds += bounds

    @staticmethod
    def from_fiona(
        src: Collection,
        index: Optional[IndexType] = "strtree",
    ) -> IndexedFeatures:
        return IndexedFeatures(src, index=index, crs=src.crs)

    @staticmethod
    def from_file(
        path: MPathLike,
        grid: Optional[Union[Grid, GridProtocol]] = None,
        index: Optional[IndexType] = "strtree",
        **kwargs,
    ) -> IndexedFeatures:
        logger.debug(f"reading {str(path)} into memory")
        if grid:
            return IndexedFeatures(
                features=read_vector_window(path, grid=Grid.from_obj(grid), **kwargs),
                index=index,
                crs=grid.crs,
            )

        @retry(logger=logger, **dict(IORetrySettings()))
        def _read_vector():
            with fiona_open(path, "r") as src:
                return IndexedFeatures.from_fiona(src, index=index)

        return _read_vector()


def read_vector(
    path: MPathLike,
    index: Optional[IndexType] = "strtree",
) -> IndexedFeatures:
    return IndexedFeatures.from_file(path, index=index)


def read_union_geometry(
    path: MPathLike,
    bounds: Optional[BoundsLike] = None,
    clip: bool = False,
) -> Geometry:
    return IndexedFeatures.from_file(path, index=None).read_union_geometry(
        bounds=bounds, clip=clip
    )


def object_id(obj: Any) -> int:
    if hasattr(obj, "id"):
        return hash(obj.id)
    elif isinstance(obj, dict) and "id" in obj:
        return hash(obj["id"])
    else:
        try:
            return hash(obj)
        except TypeError:
            raise TypeError("object need to have an id or have to be hashable")


def object_geometry(obj: Any) -> Geometry:
    """
    Determine geometry from object if available.
    """
    try:
        if isinstance(obj, BaseGeometry):
            return obj
        elif hasattr(obj, "__geo_interface__"):
            return to_shape(obj)
        elif hasattr(obj, "geometry"):
            return to_shape(obj.geometry)
        elif hasattr(obj, "get") and obj.get("geometry"):
            return to_shape(obj["geometry"])
        elif hasattr(obj, "bounds"):
            return to_shape(Bounds.from_inp(obj.bounds))
        elif hasattr(obj, "bbox"):
            return to_shape(Bounds.from_inp(obj.bbox))
        elif hasattr(obj, "get") and obj.get("bounds"):
            return to_shape(Bounds.from_inp(obj["bounds"]))
        else:
            raise TypeError("no geometry")
    except Exception as exc:
        raise NoGeoError(f"cannot determine geometry from object: {obj}") from exc


def object_bounds(
    obj: Any, obj_crs: Optional[CRSLike] = None, dst_crs: Optional[CRSLike] = None
) -> Bounds:
    """
    Determine geographic bounds from object if available.

    If dst_crs is defined, bounds will be reprojected in case the object holds CRS information.
    """
    try:
        if hasattr(obj, "bounds"):
            bounds = Bounds.from_inp(obj.bounds)
        elif hasattr(obj, "bbox"):
            bounds = Bounds.from_inp(obj.bbox)
        elif hasattr(obj, "get") and obj.get("bounds"):
            bounds = Bounds.from_inp(obj["bounds"])
        else:
            bounds = Bounds.from_inp(object_geometry(obj).bounds)
    except Exception as exc:
        raise NoGeoError(f"cannot determine bounds from object: {obj}") from exc

    if dst_crs:
        return Bounds.from_inp(
            reproject_geometry(
                to_shape(bounds), src_crs=obj_crs or object_crs(obj), dst_crs=dst_crs
            ).bounds
        )

    return bounds


def object_crs(obj: Any) -> CRS:
    """Determine CRS from an object."""
    try:
        if hasattr(obj, "crs"):
            return CRS.from_user_input(obj.crs)
        elif hasattr(obj, "get") and obj.get("crs"):
            return CRS.from_user_input(obj["crs"])
        raise AttributeError(f"no crs attribute or key found in object: {obj}")
    except Exception as exc:
        raise NoCRSError(f"cannot determine CRS from object: {obj}") from exc
