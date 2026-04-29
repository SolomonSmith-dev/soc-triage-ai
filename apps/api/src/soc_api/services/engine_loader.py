"""Singleton triage engine loader. Used by the lifespan hook in main.py."""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triage_engine.triage import SOCTriage

logger = logging.getLogger(__name__)

_engine: "SOCTriage | None" = None


def get_engine() -> "SOCTriage":
    global _engine
    if _engine is None:
        from triage_engine.triage import SOCTriage
        logger.info("Loading SOCTriage engine (this takes ~30s)...")
        _engine = SOCTriage()
        logger.info("SOCTriage engine ready.")
    return _engine


def is_loaded() -> bool:
    return _engine is not None
