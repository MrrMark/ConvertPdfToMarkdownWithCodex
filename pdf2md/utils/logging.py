from __future__ import annotations

import logging


def configure_logging(*, verbose: bool, debug: bool) -> None:
    """Configure package logging once per CLI invocation."""
    level = logging.WARNING
    if verbose:
        level = logging.INFO
    if debug:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
