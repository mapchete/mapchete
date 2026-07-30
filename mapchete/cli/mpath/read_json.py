import json
import click

from mapchete.cli import options
from mapchete.path import MPath


@click.command(help="Print contents of file as JSON.")
@options.arg_path
@options.opt_src_fs_opts
@click.option("--indent", "-i", type=click.INT, default=4)
@options.opt_debug
def read_json(path: MPath, debug: bool = False, indent: int = 4, **_):
    try:
        click.echo(json.dumps(path.read_json(), indent=indent))
    except Exception as exc:  # pragma: no cover
        if debug:
            raise
        raise click.ClickException(str(exc))
