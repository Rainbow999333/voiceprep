from __future__ import annotations

import click

from .doctor import register as register_doctor
from .export import register as register_export
from .scan import register as register_scan
from .tags import register as register_tags


@click.group()
def cli() -> None:
    """Prepare local audio files for later processing."""


register_scan(cli)
register_tags(cli)
register_export(cli)
register_doctor(cli)
