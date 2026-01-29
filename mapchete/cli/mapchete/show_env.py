"""CLI to format drivers."""

from enum import Enum
from typing import Literal

import click

from mapchete.settings import MapcheteOptions, IORetrySettings, GDALHTTPOptions


@click.command(help="List all possible environment settings.")
def show_env():
    """List all possible environment settings."""
    for setting_model in [MapcheteOptions, IORetrySettings, GDALHTTPOptions]:
        env_prefix = setting_model.model_config.get("env_prefix", "")
        for field_name, field_info in setting_model.model_fields.items():
            if field_name == "exceptions":
                click.echo(
                    f"{env_prefix}{field_name.upper()} (not able to be set via environment!)"
                )
                continue
            # field_info contains metadata like annotation (type) and default
            annotation = field_info.annotation
            default_value = field_info.default

            # Check for Literal
            if hasattr(annotation, "__origin__") and annotation.__origin__ is Literal:
                options_str = f" ({', '.join(annotation.__args__)})"

            # Check for Enum
            elif isinstance(annotation, type) and issubclass(annotation, Enum):
                options_str = (
                    f" ({', '.join([str(member.value) for member in annotation])})"
                )
                default_value = field_info.default.name
            else:
                options_str = ""

            click.echo(
                f"{env_prefix}{field_name.upper()}{options_str}: {default_value}"
            )
