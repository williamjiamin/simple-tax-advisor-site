"""One default-on gate with an exact disabled passthrough."""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import TypeVar

T = TypeVar("T")
KILL_SWITCH = "TAX_RESEARCH_DISABLED"


def enabled(settings: Mapping | None = None, environment: Mapping | None = None) -> bool:
    settings = {} if settings is None else settings
    environment = os.environ if environment is None else environment
    setting = settings.get("tax_research/enabled", True)
    if type(setting) is not bool:
        raise ValueError("tax_research/enabled must be boolean")
    killed = str(environment.get(KILL_SWITCH, "")).strip().lower() in {"1", "true", "yes", "on"}
    return setting and not killed


def augment(previous: T, build: Callable[[T], T], *, settings: Mapping | None = None,
            environment: Mapping | None = None) -> T:
    """Return the original object without invoking the feature when disabled."""
    if not enabled(settings, environment):
        return previous
    return build(previous)
