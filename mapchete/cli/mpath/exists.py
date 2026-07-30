import click

from mapchete.cli import options
from mapchete.path import MPath


@click.command(help="Check whether path exists.")
@options.arg_path
@options.opt_src_fs_opts
@options.opt_debug
def exists(path: MPath, debug: bool = False, **_):
    try:
        click.echo(path.exists())
    except Exception as exc:  # pragma: no cover
        if debug:
            raise
        raise click.ClickException(str(exc))
