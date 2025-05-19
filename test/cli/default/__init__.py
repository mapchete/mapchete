import logging

from click.testing import CliRunner

from mapchete.cli.mapchete import main

logger = logging.getLogger(__name__)


def run_cli(args, expected_exit_code=0, output_contains=None, raise_exc=True, cli=main):
    result = CliRunner(env=dict(MAPCHETE_TEST="TRUE")).invoke(
        cli, list(map(str, args)), catch_exceptions=True, standalone_mode=True
    )
    if output_contains:
        assert output_contains in result.output or output_contains in str(
            result.exception
        )
    if raise_exc and result.exception:
        logger.error(result.output or result.exception)
        raise result.exception
        # raise ClickException(result.output or result.exception)
    assert result.exit_code == expected_exit_code
    return result
