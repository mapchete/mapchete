"""CLI to format drivers."""

import click

from mapchete.settings import MapcheteOptions, IORetrySettings, GDALHTTPOptions


@click.command(help="List all possible environment settings.")
def show_env():
    """List all possible environment settings."""
    for setting_model in [MapcheteOptions, IORetrySettings, GDALHTTPOptions]:
        env_prefix = setting_model.model_config.get("env_prefix", "")
        for key, value in setting_model().model_dump().items():
            click.echo(f"{env_prefix}{key.upper()}: {value}")
