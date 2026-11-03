"""CI uses its exact service tools without exposing credentials on argv."""

from subprocess import CompletedProcess

import pytest

from scripts.prepare_enterprise_ci_tools import command, prepare

CONTAINER = "a" * 64


def environment(**changes):
    return {
        "PGHOST": "127.0.0.1",
        "PGPORT": "5432",
        "PGDATABASE": "postgres",
        "PGUSER": "synthetic_ci",
        "PGPASSWORD": "synthetic-private-password",
        **changes,
    }


def test_dump_and_restore_use_only_owned_service_and_inherited_secret_environment():
    for tool, arguments in (
        ("pg_dump", ["--format=custom", "--snapshot=00000005-00000022-1"]),
        ("pg_restore", ["--single-transaction", "--dbname=aig_restore_" + "b" * 32]),
    ):
        actual = command(CONTAINER, tool, arguments, environment())
        assert actual[:3] == ["docker", "exec", "--interactive"]
        assert actual[-len(arguments) - 2 :] == [CONTAINER, tool, *arguments]
        assert "PGPASSWORD" in actual and "synthetic-private-password" not in " ".join(actual)


@pytest.mark.parametrize(
    "changes",
    [
        {"PGHOST": "remote.example.test"},
        {"PGPORT": "5433"},
        {"PGDATABASE": "owner_database"},
        {"PGSSLROOTCERT": "/foreign"},
    ],
)
def test_service_shim_rejects_foreign_connections(changes):
    with pytest.raises(ValueError):
        command(CONTAINER, "pg_dump", [], environment(**changes))


def test_service_shim_refuses_other_tools_containers_and_restore_targets():
    for container, tool, arguments in (
        ("foreign", "pg_dump", []),
        (CONTAINER, "psql", []),
        (CONTAINER, "pg_restore", ["--dbname=owner_database"]),
    ):
        with pytest.raises(ValueError):
            command(container, tool, arguments, environment())


@pytest.mark.parametrize(
    "argument",
    ["--host=remote.example.test", "-h", "--file=/foreign", "--create", "postgresql://foreign"],
)
def test_connection_or_file_options_cannot_override_the_owned_service(argument):
    with pytest.raises(ValueError):
        command(CONTAINER, "pg_dump", [argument], environment())


def test_prepare_preserves_existing_target_and_requires_major_18(tmp_path):
    target = tmp_path / "tools"

    def bad(*_args, **_kwargs):
        return CompletedProcess([], 0, "pg_dump (PostgreSQL) 16.8\n", "")

    with pytest.raises(ValueError, match="version_invalid"):
        prepare(CONTAINER, target, runner=bad)
    assert not target.exists()

    def good(*_args, **_kwargs):
        return CompletedProcess([], 0, "pg_dump (PostgreSQL) 18.6 (Debian)\n", "")

    prepare(CONTAINER, target, runner=good)
    assert {p.name for p in target.iterdir()} == {"pg_dump", "pg_restore"}
    with pytest.raises(ValueError, match="target_invalid"):
        prepare(CONTAINER, target, runner=good)
