"""Synthetic initial activation; human/host acceptance remains separate."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance import initial_activation as module
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.evidence import SyntheticKeyProvider
from pii_redactor.governance.key_operations import verify_keys
from pii_redactor.governance.operations import (
    ProductionProfile,
    artifact_identity,
    digest,
    readiness,
    schema_identity,
)
from tests import governance_helpers as fixtures
from tests.test_audit_checkpoint import client
from tests.test_audit_checkpoint import witness as independent_witness
from tests.test_enterprise_recovery import whole_database as fresh_database
from tests.test_enterprise_runtime_role import runtime as runtime_role

database, context, witness, whole_database = (
    fixtures.database,
    fixtures.context,
    independent_witness,
    fresh_database,
)


@pytest.fixture(autouse=True)
def subsystem_source_binding(monkeypatch):
    frozen = artifact_identity()
    monkeypatch.setattr(module, "artifact_identity", lambda: frozen)
    monkeypatch.setattr("pii_redactor.governance.operations.artifact_identity", lambda: frozen)
    monkeypatch.setattr("pii_redactor.governance.backup.artifact_identity", lambda: frozen)
    monkeypatch.setitem(globals(), "artifact_identity", lambda: frozen)


def production_profile():
    return ProductionProfile.parse(
        {
            "profile": "single_organization_production_v1",
            "artifact": artifact_identity(),
            "schema": digest(schema_identity()),
            "public_origin": "https://synthetic.example.test",
            "checkpoint_max_age": 300,
            "checkpoint_max_events": 100,
            "evidence": dict.fromkeys(
                (
                    "tls_proxy",
                    "database_runtime_role",
                    "storage_acl",
                    "secret_custody",
                    "key_custody",
                    "sink_custody",
                    "backup_custody",
                    "rpo_rto_drill",
                    "capacity",
                    "idp",
                    "release_scope",
                    "image_inventory",
                    "rollback",
                ),
                "synthetic-test-reference-only",
            ),
        }
    )


@pytest.fixture
def activation(context, witness):
    # Other workers edit assets; this is an isolated DB protocol drill.
    c = context
    c.keys = SyntheticKeyProvider({(c.store.organization_id, None, "v1"): b"k" * 32})
    c.keys.active_version = "v1"
    c.checkpoint = client(witness, c.store.organization_id)
    c.profile = production_profile()
    with runtime_role(c) as (c.runtime, c.role):
        yield c


def memory_authority(c, *, store=None, runtime=None):
    return module.SyntheticActivationAuthority(
        store=store or c.store,
        runtime_store=runtime or c.runtime,
        key_provider=c.keys,
        checkpoint=c.checkpoint,
    )


def review(c, **changes):
    data = module.review_context(
        c.store,
        runtime_store=c.runtime,
        profile=c.profile,
        key_provider=c.keys,
        checkpoint=c.checkpoint,
        authority=memory_authority(c),
    )["review_template"]
    return approve_template(c, data, **changes)


def approve_template(c, data, **changes):
    now = datetime.now(UTC)
    data.update(
        {
            "decision": "approved",
            "proposer_id": str(c.ids[0]),
            "proposer_revision": 1,
            "reviewer_id": str(c.ids[1]),
            "reviewer_revision": 1,
            "proposer_evidence_ref": str(uuid4()),
            "reviewer_evidence_ref": str(uuid4()),
            "reviewed_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            **changes,
        }
    )
    return data


def physical_inputs(c, folder):
    import json
    from dataclasses import asdict

    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    from app.enterprise.capabilities import ConfiguredKeyProvider
    from pii_redactor.governance.operator_files import create_private
    from scripts.run_operations_drill import private_directory

    private_directory(folder)
    payloads = {
        "operator": {"dsn": c.store._dsn, "purpose": "synthetic_enterprise_tests"},
        "runtime": {"dsn": c.runtime._dsn, "purpose": "synthetic_enterprise_tests"},
        "managed": {
            "organization_id": str(c.store.organization_id),
            "active_version": "v1",
            "keys": [{"version": "v1", "key_hex": (b"k" * 32).hex()}],
        },
        "profile": {"profile": "single_organization_production_v1", **asdict(c.profile)},
        "checkpoint": {
            "url": c.checkpoint.url,
            "token": "synthetic-token",
            "public_key_hex": c.checkpoint.public_key.public_bytes(
                Encoding.Raw, PublicFormat.Raw
            ).hex(),
        },
    }
    for name, value in payloads.items():
        with create_private(folder / name) as stream:
            stream.write(json.dumps(value).encode())
    configured = ConfiguredKeyProvider(folder / "managed", c.store.organization_id)
    authority = module.InitialFileAuthority(
        operator_db=folder / "operator",
        runtime_db=folder / "runtime",
        profile_file=folder / "profile",
        checkpoint_file=folder / "checkpoint",
        managed_keys=folder / "managed",
    )
    template = module.review_context(
        c.store,
        runtime_store=c.runtime,
        profile=c.profile,
        key_provider=configured,
        checkpoint=c.checkpoint,
        authority=authority,
    )["review_template"]
    payloads["review"] = approve_template(c, template)
    with create_private(folder / "review") as stream:
        stream.write(json.dumps(payloads["review"]).encode())
    return payloads, configured


def file_environment(c, folder, monkeypatch):
    for env, name in (
        ("DB", "operator"),
        ("MANAGED_KEYS", "managed"),
        ("PROFILE", "profile"),
        ("CHECKPOINT", "checkpoint"),
    ):
        monkeypatch.setenv("AIGUARD_ENTERPRISE_" + env + "_FILE", str(folder / name))
    monkeypatch.setenv("AIGUARD_ENTERPRISE_ORGANIZATION_ID", str(c.store.organization_id))


def activate(c, data):
    return module.activate_initial(
        c.store,
        data,
        runtime_store=c.runtime,
        profile=c.profile,
        key_provider=c.keys,
        checkpoint=c.checkpoint,
        authority=memory_authority(c),
    )


def state(c):
    with c.store.transaction() as tx:
        return tx.execute("SELECT state,active_key_version FROM governance_operations").fetchone()


def test_initial_activation_proves_runtime_session_and_control_plane_mutation(activation):
    from app.enterprise.sessions import StaffSessions
    from pii_redactor.governance.processing_controls import ProcessingControls
    from pii_redactor.governance.registry import Registry
    from tests.test_governance_registry import activity

    c = activation
    result = activate(c, review(c))
    assert (
        result["state"] == "reconciled"
        and not result["owner_acceptance"]
        and not result["legal_clearance"]
    )
    assert (
        readiness(c.runtime, c.profile, c.checkpoint, lambda: verify_keys(c.runtime, c.keys))[
            "status"
        ]
        == "ready"
    )
    sessions = StaffSessions(c.runtime)
    attempt = sessions.begin_login("b" * 43)
    sessions.consume_login(attempt.state, "b" * 43)
    principal = sessions.resolve(sessions.issue(c.a).cookie)
    row = Registry(c.runtime).create_activity(principal, uuid4(), activity())
    assert row["revision"] == 1
    with c.runtime.transaction() as tx:
        with pytest.raises(GovernanceError, match="processing_controls_required"):
            ProcessingControls(c.runtime).require_activity(
                tx,
                {
                    "organization_id": c.store.organization_id,
                    "activity_id": row["id"],
                    "activity_revision": row["revision"],
                    "department_id": "operations",
                },
            )


def test_generated_context_is_not_approval_and_cannot_activate(activation):
    c = activation
    value = module.review_context(
        c.store,
        runtime_store=c.runtime,
        profile=c.profile,
        key_provider=c.keys,
        checkpoint=c.checkpoint,
        authority=memory_authority(c),
    )
    assert (
        value["review_template"]["decision"] == "pending_review" and not value["owner_acceptance"]
    )
    assert all(
        "subject" not in row and "issuer" not in row for row in value["authority_candidates"]
    )
    with pytest.raises(GovernanceError, match="initial_review_invalid"):
        activate(c, value["review_template"])
    assert state(c)["state"] == "quarantined"


@pytest.mark.parametrize(
    "change,error",
    [
        ({"reviewer_id": "self"}, "initial_review_invalid"),
        ({"reviewer_id": "wrong-role"}, "initial_authority_changed"),
        ({"reviewer_revision": 2}, "initial_authority_changed"),
        ({"artifact": "0" * 64}, "initial_review_scope_changed"),
        ({"schema": "0" * 64}, "initial_review_scope_changed"),
        ({"organization_id": str(uuid4())}, "initial_review_scope_changed"),
        ({"public_origin": "http://synthetic.example.test"}, "initial_review_scope_changed"),
        ({"runtime_role": "wrong_synthetic_role"}, "initial_runtime_target_mismatch"),
        ({"key_version": "v2"}, "initial_key_changed"),
    ],
)
def test_changed_scope_or_wrong_authority_never_activates(activation, change, error):
    c = activation
    values = dict(change)
    if values.get("reviewer_id") == "self":
        values["reviewer_id"] = str(c.ids[0])
    if values.get("reviewer_id") == "wrong-role":
        values["reviewer_id"] = str(c.ids[2])
    with pytest.raises(GovernanceError, match=error):
        activate(c, review(c, **values))
    assert state(c)["state"] == "quarantined"


def test_expired_review_nonempty_and_restored_database_rejected(activation):
    from pii_redactor.governance.registry import Registry
    from tests.test_governance_registry import activity

    c = activation
    now = datetime.now(UTC)
    data = review(
        c,
        reviewed_at=(now - timedelta(hours=2)).isoformat(),
        expires_at=(now - timedelta(hours=1)).isoformat(),
    )
    with pytest.raises(GovernanceError, match="initial_review_expired"):
        activate(c, data)
    data = review(c)
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET restore_id=%s", (uuid4(),))
    with pytest.raises(GovernanceError, match="initial_target_not_fresh"):
        activate(c, data)
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET restore_id=NULL")
    Registry(c.store).create_activity(c.a, uuid4(), activity())
    with pytest.raises(GovernanceError, match="initial_target_not_fresh"):
        activate(c, data)


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("member", "initial_authority_changed"),
        ("key", "initial_key_changed"),
        ("key-label", "initial_key_changed"),
        ("profile", "initial_review_scope_changed"),
        ("audit", "initial_witness_unverified"),
    ],
)
def test_changes_during_signed_witness_io_leave_quarantine(
    activation, monkeypatch, mutation, error
):
    c = activation
    data = review(c)
    original = c.checkpoint.check

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if mutation == "key":
            c.keys._keys[(c.store.organization_id, None, "v1")] = b"z" * 32
        elif mutation == "profile":
            c.profile.evidence["capacity"] = "changed-synthetic-reference"
        else:
            with c.store.transaction() as tx:
                if mutation == "member":
                    tx.execute(
                        "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
                        (c.ids[1],),
                    )
                elif mutation == "key-label":
                    tx.execute("UPDATE governance_operations SET active_key_version='v2'")
                else:
                    c.store.append_event(tx, event_code="operations.initial_prepared")
        return result

    monkeypatch.setattr(c.checkpoint, "check", changed)
    with pytest.raises(GovernanceError, match=error):
        activate(c, data)
    assert state(c)["state"] == "quarantined"


def test_witness_outage_and_review_supersession_preserve_history(activation, monkeypatch):
    c = activation
    data = review(c)
    original = c.checkpoint.check

    def unavailable(*_args, **_kwargs):
        raise GovernanceError("checkpoint_unavailable")

    monkeypatch.setattr(c.checkpoint, "check", unavailable)
    with pytest.raises(GovernanceError, match="checkpoint_unavailable"):
        activate(c, data)
    assert state(c)["state"] == "quarantined"
    successor = review(c)
    assert successor["supersedes"] == data["activation_id"]
    monkeypatch.setattr(c.checkpoint, "check", original)
    assert activate(c, successor)["state"] == "reconciled"
    with pytest.raises(GovernanceError, match="initial_activation_conflict"):
        activate(c, data)
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_initial_journal").fetchone()["n"] == 4
        )


def test_repeat_cannot_reenable_later_quarantine(activation):
    from pii_redactor.governance.operations import Operations

    c = activation
    data = review(c)
    activate(c, data)
    assert activate(c, data)["state"] == "already_activated"
    Operations(c.store).quarantine(None)
    result = activate(c, data)
    assert result["state"] == "already_activated" and result["current_state"] == "quarantined"
    assert result["status"] == "blocked"
    assert state(c)["state"] == "quarantined"


def test_released_record_cannot_authorize_a_restored_target(activation):
    c = activation
    data = review(c)
    activate(c, data)
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET state='quarantined',restore_id=%s", (uuid4(),))
    with pytest.raises(GovernanceError, match="initial_target_not_fresh"):
        activate(c, data)
    assert state(c)["state"] == "quarantined"


def test_runtime_and_operator_cannot_rewrite_initial_evidence(activation):
    c = activation
    activate(c, review(c))
    for store in (c.store, c.runtime):
        with pytest.raises(GovernanceError, match="storage_failure"):
            with store.transaction() as tx:
                tx.execute("UPDATE governance_initial_activations SET review='{}'::jsonb")
        with pytest.raises(GovernanceError, match="storage_failure"):
            with store.transaction() as tx:
                tx.execute("DELETE FROM governance_initial_journal")


def test_readonly_runtime_cannot_pass_activation(activation):
    c = activation
    data = review(c)
    with runtime_role(c, readonly=True) as (readonly, name):
        with pytest.raises(GovernanceError, match="runtime_role_insufficient"):
            module.review_context(
                c.store,
                runtime_store=readonly,
                profile=c.profile,
                key_provider=c.keys,
                checkpoint=c.checkpoint,
                authority=memory_authority(c, runtime=readonly),
            )
        data["runtime_role"] = name
        with pytest.raises(GovernanceError, match="initial_review_scope_changed"):
            module.activate_initial(
                c.store,
                data,
                runtime_store=readonly,
                profile=c.profile,
                key_provider=c.keys,
                checkpoint=c.checkpoint,
                authority=memory_authority(c, runtime=readonly),
            )
    assert state(c)["state"] == "quarantined"


def test_wrong_runtime_schema_is_not_an_activation_qualifier(activation):
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from pii_redactor.governance.store import Store

    c = activation
    data = review(c)
    name = "test_initial_" + uuid4().hex
    with c.store.transaction() as tx:
        tx.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        tx.execute(
            sql.SQL("CREATE TABLE {}.governance_organization(organization_id uuid)").format(
                sql.Identifier(name)
            )
        )
        tx.execute(
            sql.SQL("INSERT INTO {}.governance_organization VALUES (%s)").format(
                sql.Identifier(name)
            ),
            (c.store.organization_id,),
        )
        tx.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(name), sql.Identifier(c.role)
            )
        )
        tx.execute(
            sql.SQL("GRANT SELECT ON {}.governance_organization TO {}").format(
                sql.Identifier(name), sql.Identifier(c.role)
            )
        )
    try:
        wrong = Store(
            make_conninfo(c.runtime._dsn, options="-csearch_path=" + name), c.store.organization_id
        )
        with pytest.raises(GovernanceError, match="initial_runtime_target_mismatch"):
            module.review_context(
                c.store,
                runtime_store=wrong,
                profile=c.profile,
                key_provider=c.keys,
                checkpoint=c.checkpoint,
                authority=memory_authority(c, runtime=wrong),
            )
        with pytest.raises(GovernanceError, match="initial_review_scope_changed"):
            module.activate_initial(
                c.store,
                data,
                runtime_store=wrong,
                profile=c.profile,
                key_provider=c.keys,
                checkpoint=c.checkpoint,
                authority=memory_authority(c, runtime=wrong),
            )
    finally:
        with c.store.transaction() as tx:
            tx.execute(
                sql.SQL("REVOKE ALL ON {}.governance_organization FROM {}").format(
                    sql.Identifier(name), sql.Identifier(c.role)
                )
            )
            tx.execute(
                sql.SQL("DROP TABLE {}.governance_organization").format(sql.Identifier(name))
            )
            tx.execute(
                sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
                    sql.Identifier(name), sql.Identifier(c.role)
                )
            )
            tx.execute(sql.SQL("DROP SCHEMA {}").format(sql.Identifier(name)))


def test_final_database_failure_does_not_release(activation, monkeypatch):
    c = activation
    data = review(c)
    original = c.store.transaction

    @contextmanager
    def fail_commit():
        with original() as tx:
            yield tx
            if tx.execute(
                "SELECT 1 FROM governance_initial_activations WHERE phase='released'"
            ).fetchone():
                raise GovernanceError("storage_failure")

    monkeypatch.setattr(c.store, "transaction", fail_commit)
    with pytest.raises(GovernanceError, match="storage_failure"):
        activate(c, data)
    monkeypatch.setattr(c.store, "transaction", original)
    assert state(c)["state"] == "quarantined"
    assert activate(c, data)["state"] == "reconciled"


def test_archived_released_record_cannot_activate_a_restored_database(
    whole_database, witness, tmp_path
):
    import os
    from types import SimpleNamespace

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from pii_redactor.governance.backup import backup_database, restore_database
    from pii_redactor.governance.store import Store
    from scripts.run_operations_drill import private_directory

    store, admin_dsn = whole_database
    with store.transaction() as tx:
        proposer = tx.execute(
            "SELECT member_id FROM governance_members WHERE roles ? 'system_administrator'"
        ).fetchone()["member_id"]
        reviewer = tx.execute(
            "SELECT member_id FROM governance_members WHERE roles ? 'authority_reviewer' AND member_id<>%s",
            (proposer,),
        ).fetchone()["member_id"]
    c = SimpleNamespace(store=store, ids=[proposer, reviewer], profile=production_profile())
    c.keys = SyntheticKeyProvider({(store.organization_id, None, "v1"): b"k" * 32})
    c.keys.active_version = "v1"
    c.checkpoint = client(witness, store.organization_id)
    private = tmp_path / "activation-private"
    private_directory(private)
    target = "aig_restore_" + uuid4().hex
    with runtime_role(c) as (c.runtime, c.role):
        data = review(c)
        activate(c, data)
        archive = private / "synthetic.aigdb"
        key = os.urandom(32)
        binary = os.environ["AIGUARD_OPERATIONS_PG_BIN"]
        backup_database(store, binary, archive, key, checkpoint=c.checkpoint)
        try:
            restore_database(admin_dsn, binary, archive, key, name=target, confirmation=target)
            restored = Store(make_conninfo(admin_dsn, dbname=target), store.organization_id)
            runtime = Store(make_conninfo(c.runtime._dsn, dbname=target), store.organization_id)
            with pytest.raises(GovernanceError, match="initial_review_scope_changed"):
                module.activate_initial(
                    restored,
                    data,
                    runtime_store=runtime,
                    profile=c.profile,
                    key_provider=c.keys,
                    checkpoint=c.checkpoint,
                    authority=memory_authority(c, store=restored, runtime=runtime),
                )
            with restored.transaction() as tx:
                assert (
                    tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
                    == "quarantined"
                )
        finally:
            assert target.startswith("aig_restore_") and len(target) == 44
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(target)
                    )
                )


def test_review_is_bound_to_database_before_its_first_use(whole_database, witness):
    from types import SimpleNamespace

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from psycopg.types.json import Jsonb

    from pii_redactor.governance.runtime_roles import grant_statements
    from pii_redactor.governance.store import Store

    source, admin_dsn = whole_database
    with source.transaction() as tx:
        proposer = tx.execute(
            "SELECT member_id FROM governance_members WHERE roles ? 'system_administrator'"
        ).fetchone()["member_id"]
        reviewer = tx.execute(
            "SELECT member_id FROM governance_members WHERE roles ? 'authority_reviewer' AND member_id<>%s",
            (proposer,),
        ).fetchone()["member_id"]
    c = SimpleNamespace(store=source, ids=[proposer, reviewer], profile=production_profile())
    c.keys = SyntheticKeyProvider({(source.organization_id, None, "v1"): b"k" * 32})
    c.keys.active_version = "v1"
    c.checkpoint = client(witness, source.organization_id)
    target_name = "aig_restore_" + uuid4().hex
    with runtime_role(c) as (c.runtime, c.role):
        data = review(c)
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_name)))
        try:
            target = Store(make_conninfo(admin_dsn, dbname=target_name), source.organization_id)
            target.migrate()
            with source.transaction() as src, target.transaction() as dst:
                src.execute("SET LOCAL timezone='UTC'")
                dst.execute("SET LOCAL timezone='UTC'")
                for table in ("governance_members", "governance_audit"):
                    rows = src.execute(
                        sql.SQL("SELECT to_jsonb(t) AS data FROM {} t").format(
                            sql.Identifier(table)
                        )
                    ).fetchall()
                    for row in rows:
                        dst.execute(
                            sql.SQL(
                                "INSERT INTO {} SELECT (jsonb_populate_record(NULL::{},%s)).*"
                            ).format(sql.Identifier(table), sql.Identifier(table)),
                            (Jsonb(row["data"]),),
                        )
                enrolled = src.execute(
                    "SELECT enrolled_at FROM governance_organization"
                ).fetchone()["enrolled_at"]
                dst.execute("UPDATE governance_organization SET enrolled_at=%s", (enrolled,))
                for statement in grant_statements("public", c.role):
                    dst.execute(statement)
            target_runtime = Store(
                make_conninfo(c.runtime._dsn, dbname=target_name), source.organization_id
            )
            with pytest.raises(GovernanceError, match="initial_review_scope_changed"):
                module.activate_initial(
                    target,
                    data,
                    runtime_store=target_runtime,
                    profile=c.profile,
                    key_provider=c.keys,
                    checkpoint=c.checkpoint,
                    authority=memory_authority(c, store=target, runtime=target_runtime),
                )
            with target.transaction() as tx:
                assert (
                    tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
                    == "quarantined"
                )
                assert (
                    tx.execute(
                        "SELECT count(*) AS n FROM governance_initial_activations"
                    ).fetchone()["n"]
                    == 0
                )
        finally:
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(target_name))
                )


@pytest.mark.parametrize("arguments", [["activate-initial"], ["initial-review-context"]])
def test_initial_cli_requires_explicit_protected_runtime_reference(arguments):
    from app.enterprise.operations import main

    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_actual_cli_uses_protected_review_runtime_and_key_files_without_login_secrets(
    activation, tmp_path, monkeypatch, capsys
):
    import json

    from app.enterprise import operations as cli
    from app.enterprise.settings import Settings

    c = activation
    folder = tmp_path / "initial-operator-files"
    physical_inputs(c, folder)
    file_environment(c, folder, monkeypatch)
    monkeypatch.setattr(
        Settings, "from_env", lambda: pytest.fail("initial operator read login credentials")
    )
    # The real signed fixture is loopback HTTP, not production TLS qualification.
    monkeypatch.setattr(cli, "load_profile_checkpoint", lambda _org: (c.profile, c.checkpoint))
    assert (
        cli.main(
            [
                "activate-initial",
                "--runtime-db-file",
                str(folder / "runtime"),
                "--review-file",
                str(folder / "review"),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "reconciled" and not result["owner_acceptance"]
    assert not {"dsn", "keys", "client_secret"}.intersection(result)
    assert state(c)["state"] == "reconciled"


@pytest.mark.parametrize(
    "changed",
    [
        "profile",
        "checkpoint",
        "operator",
        "runtime",
        "review",
        "managed",
        "missing",
        "acl",
        "replace",
    ],
)
def test_cli_physical_authority_drift_during_witness_never_releases(
    activation, tmp_path, monkeypatch, capsys, changed
):
    import json

    from app.enterprise import operations as cli

    c = activation
    folder = tmp_path / "live-initial-files"
    payloads, _configured = physical_inputs(c, folder)
    file_environment(c, folder, monkeypatch)
    monkeypatch.setattr(cli, "load_profile_checkpoint", lambda _org: (c.profile, c.checkpoint))
    original = c.checkpoint.check

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        if changed in {"missing", "acl", "replace"}:
            import os
            import subprocess

            selected = folder / "managed"
            if changed == "missing":
                selected.unlink()
            elif changed == "replace":
                replacement = folder / "managed-replacement"
                replacement.write_bytes(selected.read_bytes())
                replacement.replace(selected)
            elif os.name == "nt":
                subprocess.run(
                    ["icacls", str(selected), "/grant", "*S-1-1-0:R"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    timeout=10,
                )
            else:
                selected.chmod(0o644)
            return result
        value = payloads[changed]
        if changed == "managed":
            value["keys"][0]["key_hex"] = (b"z" * 32).hex()
        elif changed in {"operator", "runtime"}:
            value["dsn"] = "dbname=changed_synthetic_reference"
        elif changed == "review":
            value["decision"] = "pending_review"
        elif changed == "checkpoint":
            value["token"] = "changed-synthetic-token"
        else:
            value["evidence"]["capacity"] = "changed-synthetic-reference"
        (folder / changed).write_text(json.dumps(value), encoding="utf-8")
        return result

    monkeypatch.setattr(c.checkpoint, "check", mutate)
    assert (
        cli.main(
            [
                "activate-initial",
                "--runtime-db-file",
                str(folder / "runtime"),
                "--review-file",
                str(folder / "review"),
            ]
        )
        == 1
    )
    assert state(c)["state"] == "quarantined"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("phase", [1, 2])
def test_live_file_recheck_precedes_prepare_and_release(activation, tmp_path, monkeypatch, phase):
    import json

    from app.enterprise import operations as cli

    c = activation
    folder = tmp_path / "phase-bound-inputs"
    payloads, _configured = physical_inputs(c, folder)
    file_environment(c, folder, monkeypatch)
    monkeypatch.setattr(cli, "load_profile_checkpoint", lambda _org: (c.profile, c.checkpoint))
    original, calls = module._runtime, []

    def change_after_runtime(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        if len(calls) == phase:
            payloads["managed"]["keys"][0]["key_hex"] = (b"z" * 32).hex()
            (folder / "managed").write_text(json.dumps(payloads["managed"]), encoding="utf-8")
        return result

    monkeypatch.setattr(module, "_runtime", change_after_runtime)
    assert (
        cli.main(
            [
                "activate-initial",
                "--runtime-db-file",
                str(folder / "runtime"),
                "--review-file",
                str(folder / "review"),
            ]
        )
        == 1
    )
    assert state(c)["state"] == "quarantined"
    with c.store.transaction() as tx:
        count = tx.execute("SELECT count(*) AS n FROM governance_initial_activations").fetchone()[
            "n"
        ]
    assert count == (0 if phase == 1 else 1)


def test_current_keyfile_is_reparsed_not_only_snapshot_at_capture(
    activation, tmp_path, monkeypatch
):
    import json

    from app.enterprise import operations as cli

    c = activation
    folder = tmp_path / "cached-key-mismatch"
    payloads, _configured = physical_inputs(c, folder)
    file_environment(c, folder, monkeypatch)
    monkeypatch.setattr(cli, "load_profile_checkpoint", lambda _org: (c.profile, c.checkpoint))
    original = cli.ConfiguredKeyProvider

    def cached_then_changed(filename, org):
        provider = original(filename, org)
        payloads["managed"]["keys"][0]["key_hex"] = (b"z" * 32).hex()
        (folder / "managed").write_text(json.dumps(payloads["managed"]), encoding="utf-8")
        return provider

    monkeypatch.setattr(cli, "ConfiguredKeyProvider", cached_then_changed)
    assert (
        cli.main(
            [
                "activate-initial",
                "--runtime-db-file",
                str(folder / "runtime"),
                "--review-file",
                str(folder / "review"),
            ]
        )
        == 1
    )
    assert state(c)["state"] == "quarantined"
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_initial_activations").fetchone()["n"]
            == 0
        )


def test_core_requires_concrete_authority_and_configured_keys_have_no_fixture_escape(
    activation, tmp_path
):
    c = activation
    data = review(c)
    with pytest.raises(GovernanceError, match="initial_authority_unverified"):
        module.activate_initial(
            c.store,
            data,
            runtime_store=c.runtime,
            profile=c.profile,
            key_provider=c.keys,
            checkpoint=c.checkpoint,
        )
    _payloads, configured = physical_inputs(c, tmp_path / "configured-not-synthetic")
    with pytest.raises(GovernanceError, match="initial_authority_unverified"):
        module.SyntheticActivationAuthority(
            store=c.store, runtime_store=c.runtime, key_provider=configured, checkpoint=c.checkpoint
        )
    assert state(c)["state"] == "quarantined"
