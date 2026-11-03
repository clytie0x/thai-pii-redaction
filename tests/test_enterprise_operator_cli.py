"""Offline operators do not need unrelated staff authentication secrets."""

from types import SimpleNamespace
from uuid import UUID

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
pytest.importorskip("authlib", reason="optional enterprise identity dependency")

from app.enterprise import operations as cli
from app.enterprise.settings import Settings

ORG = UUID("b5186bb1-3431-4330-9b39-f365db8d4813")


def test_offline_checkpoint_uses_no_staff_or_subject_oidc_configuration(monkeypatch, capsys):
    store = SimpleNamespace(organization_id=ORG)
    calls = []

    def forbidden_settings():
        raise AssertionError("offline operator must not read staff secrets")

    def profile_checkpoint(organization):
        assert organization == ORG
        witness = SimpleNamespace(check=lambda actual, **kwargs: calls.append((actual, kwargs)))
        return SimpleNamespace(), witness

    monkeypatch.setattr(Settings, "from_env", forbidden_settings)
    monkeypatch.setattr(cli, "_store", lambda *_args: store)
    monkeypatch.setattr(cli, "load_profile_checkpoint", profile_checkpoint)
    assert cli.main(["checkpoint-verify"]) == 0
    assert calls == [(store, {"publish": False})]
    assert '"state": "verified"' in capsys.readouterr().out


def test_reconciliation_requires_a_separate_runtime_database_reference():
    with pytest.raises(SystemExit) as error:
        cli.main(["restore-reconcile", "--source-db-file", "synthetic-source.key"])
    assert error.value.code == 2
