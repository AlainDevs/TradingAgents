from __future__ import annotations

from contextvars import ContextVar
import copy
from typing import Any

import tradingagents.default_config as default_config


_config_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "tradingagents_dataflow_config",
    default=None,
)


def initialize_config() -> dict[str, Any]:
    """Initialize the configuration for the current context."""
    config = _config_var.get()
    if config is None:
        config = copy.deepcopy(default_config.DEFAULT_CONFIG)
        _config_var.set(config)
    return config


def set_config(config: dict[str, Any]) -> None:
    """Set the configuration for the current context."""
    _config_var.set(copy.deepcopy(config))


def reset_config() -> None:
    """Reset the current context back to the default configuration."""
    _config_var.set(copy.deepcopy(default_config.DEFAULT_CONFIG))


def get_config() -> dict[str, Any]:
    """Get the configuration for the current context."""
    return copy.deepcopy(initialize_config())


initialize_config()
