import logging
from typing import Optional

import click
import click_spinner
import tqdm

from mapchete.cli import options
from mapchete.enums import Concurrency
from mapchete.executor import get_executor
from mapchete.path import MPath


logger = logging.getLogger(__name__)


@click.command(help="Remove path.")
@options.arg_path
@options.opt_src_fs_opts
@options.opt_recursive
@options.opt_force
@options.opt_verbose
@options.opt_workers
@click.option(
    "--count",
    is_flag=True,
    help="Count all files from source path. WARNING: this will trigger more requests on S3.",
)
def rm(
    path: MPath,
    recursive: bool = False,
    force: bool = False,
    verbose: bool = True,
    count: bool = False,
    debug: bool = False,
    workers: Optional[int] = None,
    **_,
):
    if force or click.confirm(f"do you really want to permanently delete {str(path)}?"):
        try:
            if path.is_directory():
                if recursive is False:  # pragma: no cover
                    raise click.UsageError(
                        "--recursive flag has to be active if path is a directory"
                    )

                with get_executor(
                    concurrency=Concurrency.none
                    if workers == 1
                    else Concurrency.threads,
                    max_workers=workers,
                ) as executor:
                    if count:
                        click.echo("counting pages ...")
                        with click_spinner.Spinner(disable=debug):
                            pages = list(path.paginate())
                        click.echo(f"found {len(pages)} pages")
                    else:
                        pages = path.paginate()
                    deleted = 0
                    with tqdm.tqdm(
                        total=len(pages) if isinstance(pages, list) else None,
                        desc="pages",
                    ) as pbar:
                        for page in pages:
                            pbar.total = (pbar.total or 0) + 1
                            pbar.refresh()

                            if verbose:  # pragma: no cover
                                tqdm.tqdm.write(f"found {len(page)} files")
                            logger.debug("found %s files", len(page))

                            for future in tqdm.tqdm(
                                executor.as_completed(
                                    rm_file,
                                    page,
                                    max_submitted_tasks=workers * 10,
                                ),
                                disable=debug,
                                total=len(page),
                                desc="files",
                                leave=False,
                            ):
                                future.raise_if_failed()
                                if verbose:
                                    msg = future.result()
                                    tqdm.tqdm.write(msg)

                            deleted += len(page)
                            pbar.update()

                # finally delete folder after all its contents have been deleted
                path.rm(recursive=True)
                click.echo(f"{deleted} files deleted")

            else:
                msg = rm_file(path)
                if verbose:  # pragma: no cover
                    tqdm.tqdm.write(msg)

        except Exception as exc:  # pragma: no cover
            raise click.ClickException(str(exc))


def rm_file(file: MPath) -> str:
    try:
        file.rm()
        msg = f"[OK] {str(file)}: deleted"
        logger.debug(msg)
        return msg
    except Exception as exc:  # pragma: no cover
        logger.exception(exc)
        raise
