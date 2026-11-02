"""Immutable per-operation settings for shared core callers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoreConfig:
    engine: str = "thainer"
    finetuned_model_dir: str | None = field(default=None, repr=False)
    allow_remote: bool = True
    tner_api_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls, prefix: str = "AIGUARD", allow_remote: bool = True) -> CoreConfig:
        engine = os.environ.get(f"{prefix}_NER_ENGINE", "thainer")
        return cls(
            engine=engine,
            finetuned_model_dir=os.environ.get(f"{prefix}_FINETUNED_MODEL_DIR"),
            allow_remote=allow_remote,
            tner_api_key=(
                os.environ.get("AIFORTHAI_API_KEY", "") if allow_remote and engine == "tner" else ""
            ),
        )


def resolve_config(config: CoreConfig | None = None) -> CoreConfig:
    return CoreConfig.from_env() if config is None else config


@dataclass(frozen=True)
class AuditConfig:
    stdout: bool = False

    @classmethod
    def from_env(cls, prefix: str = "AIGUARD") -> AuditConfig:
        return cls(stdout=os.environ.get(f"{prefix}_AUDIT_STDOUT") == "1")
