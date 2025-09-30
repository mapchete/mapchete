from contextlib import contextmanager
from importlib.util import find_spec
import logging
from tempfile import NamedTemporaryFile
from typing import Generator, List, Union

import fiona
from fiona.io import MemoryFile
from shapely.geometry import mapping

from mapchete.geometry.filter import filter_by_geometry_type
from mapchete.geometry.shape import to_shape
from mapchete.geometry.types import get_geometry_type
from mapchete.io.vector.types import VectorFileSchema
from mapchete.path import MPath
from mapchete.tile import BufferedTile
from mapchete.types import MPathLike, GeoJSONLikeFeature


logger = logging.getLogger(__name__)


@contextmanager
def FionaRemoteMemoryWriter(
    path: MPathLike, *args, **kwargs
) -> Generator[fiona.Collection, None, None]:
    """
    Write to a fiona-supported remote file using an in-memory file.

    Parameters
    ----------
    path : str or MPath
        Path to write to.
    args : list
        Arguments to be passed on to fiona.open()
    kwargs : dict
        Keyword arguments to be passed on to fiona.open()

    Returns
    -------
    fiona.Collection
    """
    path = MPath.from_inp(path)
    logger.debug("open FionaRemoteMemoryWriter for path %s", path)

    with MemoryFile() as memfile:
        with memfile.open(*args, **kwargs) as sink:
            yield sink

        logger.debug("upload fiona MemoryFile to %s", path)
        path.write_content(memfile.getbuffer(), mode="wb")

        logger.debug("close fiona MemoryFile")


@contextmanager
def FionaRemoteTempFileWriter(
    path: MPathLike, *args, **kwargs
) -> Generator[fiona.Collection, None, None]:
    """
    Write to a temporary file and upload it to remote storage on closing.

    Parameters
    ----------
    path : str or MPath
        Path to write to.
    args : list
        Arguments to be passed on to fiona.open()
    kwargs : dict
        Keyword arguments to be passed on to fiona.open()

    Returns
    -------
    fiona.Collection
    """
    path = MPath.from_inp(path)
    logger.debug("open FionaRemoteTempFileWriter for path %s", path)
    with NamedTemporaryFile(suffix=path.suffix) as tempfile:
        with fiona.open(tempfile.name, "w", *args, **kwargs) as dataset:
            yield dataset

        logger.debug("upload TempFile %s to %s", tempfile.name, path)
        MPath.from_inp(tempfile.name).cp(path)

        logger.debug("close and remove tempfile")


@contextmanager
def fiona_write(
    path: MPathLike, mode: str = "w", in_memory: bool = True, *args, **kwargs
) -> Generator[fiona.Collection, None, None]:
    """
    Wrap fiona.open() but handle bucket upload if path is remote.

    Parameters
    ----------
    path : str or MPath
        Path to write to.
    mode : str
        One of the fiona.open() modes.
    fs : fsspec.FileSystem
        Target filesystem.
    in_memory : bool
        On remote output store an in-memory file instead of writing to a tempfile.
    args : list
        Arguments to be passed on to fiona.open()
    kwargs : dict
        Keyword arguments to be passed on to fiona.open()

    Returns
    -------
    FionaRemoteWriter if target is remote, otherwise return fiona.open().
    """
    path = MPath.from_inp(path)

    try:
        if path.is_remote():
            if "s3" in path.protocols and not find_spec("boto3"):  # pragma: no cover
                raise ImportError("please install [s3] extra to write remote files")
            with FionaRemoteWriter(path, in_memory=in_memory, *args, **kwargs) as dst:
                yield dst
        else:
            with path.fio_env() as env:
                logger.debug("writing %s with GDAL options %s", str(path), env.options)
                path.parent.makedirs(exist_ok=True)
                with fiona.open(str(path), mode=mode, *args, **kwargs) as dst:
                    yield dst
    except Exception as exc:  # pragma: no cover
        logger.exception(exc)
        logger.debug("remove %s ...", str(path))
        path.rm(ignore_errors=True)
        raise


class FionaRemoteWriter:
    def __new__(
        cls, path, *args, in_memory=True, **kwargs
    ) -> Union[FionaRemoteMemoryWriter, FionaRemoteTempFileWriter]:
        if in_memory:
            return FionaRemoteMemoryWriter(path, *args, **kwargs)
        else:
            return FionaRemoteTempFileWriter(path, *args, **kwargs)


def write_vector_window(
    in_data: List[GeoJSONLikeFeature],
    out_schema: VectorFileSchema,
    out_tile: BufferedTile,
    out_path: MPathLike,
    out_driver: str = "GeoJSON",
    allow_multipart_geometries: bool = True,
    **kwargs,
):
    """
    Write features to file.

    Parameters
    ----------
    in_data : features
    out_driver : string
    out_schema : dictionary
        output schema for fiona
    out_tile : ``BufferedTile``
        tile used for output extent
    out_path : string
        output path for file
    """
    # Delete existing file.
    out_path = MPath.from_inp(out_path)
    out_path.rm(ignore_errors=True)
    out_features = []
    for feature in in_data:
        try:
            # clip feature geometry to tile bounding box and append for writing
            for out_geom in filter_by_geometry_type(
                to_shape(feature["geometry"]).intersection(out_tile.bbox),
                get_geometry_type(out_schema["geometry"]),
                singlepart_equivalent_matches=allow_multipart_geometries,
            ):
                if out_geom.is_empty:
                    continue

                out_features.append(
                    {"geometry": mapping(out_geom), "properties": feature["properties"]}
                )
        except Exception as e:
            logger.warning("failed to prepare geometry for writing: %s", e)
            continue

    # write if there are output features
    if out_features:
        try:
            with fiona_write(
                out_path,
                schema=out_schema,
                driver=out_driver,
                crs=out_tile.crs.to_dict(),
            ) as dst:
                logger.debug((out_tile.id, "write tile", out_path))
                dst.writerecords(out_features)
        except Exception as e:
            logger.error("error while writing file %s: %s", out_path, e)
            raise

    else:
        logger.debug((out_tile.id, "nothing to write", out_path))
