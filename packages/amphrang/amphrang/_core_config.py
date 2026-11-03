"""Resolve SDK settings without changing root callers or allowing remote NER."""

from pii_redactor.config import AuditConfig, CoreConfig


def sdk_core_config() -> CoreConfig:
    return CoreConfig.from_env(prefix="AMPHRANG", allow_remote=False)


def sdk_audit_config() -> AuditConfig:
    return AuditConfig.from_env(prefix="AMPHRANG")
