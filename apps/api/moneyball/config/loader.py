from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent


@lru_cache
def load_config(name: str) -> dict:
    """Loads and caches a YAML config file from moneyball/config/, e.g.
    load_config("afl_model") -> afl_model.yaml as a dict."""
    path = CONFIG_DIR / f"{name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def config_hash(config: dict) -> str:
    """Stable hash of a config dict, stored on model_versions.config_hash so
    two model runs can be verified to have used identical parameters."""
    canonical = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_afl_config() -> dict:
    return load_config("afl_model")
