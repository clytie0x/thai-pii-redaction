"""The runtime can use application records, never operational release authority."""

from contextlib import nullcontext

from psycopg import sql

from pii_redactor.governance.errors import GovernanceError

READ_ONLY = frozenset(
    {
        "governance_organization",
        "governance_schema",
        "governance_operations",
        "governance_restore_sessions",
        "governance_restore_journal",
        "governance_initial_activations",
        "governance_initial_journal",
    }
)
APPEND_ONLY = frozenset(
    {
        "governance_audit",
        "governance_commands",
        "governance_document_versions",
        "governance_protected_evidence",
        "governance_execution_outcomes",
        "governance_consent_purposes",
        "governance_consent_events",
        "governance_subject_commands",
        "governance_rights_subject_commands",
        "governance_rights_instruction_bindings",
        "governance_rights_previews",
        "governance_rights_history",
        "governance_control_history",
        "governance_retention_instruction_links",
        "governance_processing_history",
        "governance_processing_previews",
        "governance_instruction_controls",
    }
)
MUTABLE = frozenset(
    {
        "governance_members",
        "governance_activities",
        "governance_notices",
        "governance_grants",
        "governance_outbox",
        "enterprise_staff_sessions",
        "enterprise_subject_sessions",
        "governance_subjects",
        "governance_subject_links",
        "governance_consent_presentations",
        "governance_consent_current",
        "governance_consent_propagation",
        "governance_consent_offline_cases",
        "governance_collections",
        "governance_managed_documents",
        "governance_execution_instructions",
        "governance_execution_tasks",
        "governance_collection_snapshots",
        "governance_holds",
        "governance_retention_policies",
        "governance_retention_triggers",
        "governance_retention_due",
        "governance_retention_copies",
        "governance_rights_cases",
        "governance_rights_manual",
        "governance_rights_deliveries",
        "governance_organization_controls",
        "governance_processing_bindings",
    }
)
EPHEMERAL = frozenset({"enterprise_login_states", "enterprise_subject_login_states"})
TABLES = READ_ONLY | APPEND_ONLY | MUTABLE | EPHEMERAL


def permissions(name):
    if name in READ_ONLY:
        return {"SELECT"}
    if name in APPEND_ONLY:
        return {"SELECT", "INSERT"}
    if name in MUTABLE:
        return {"SELECT", "INSERT", "UPDATE"}
    if name in EPHEMERAL:
        return {"SELECT", "INSERT", "DELETE"}
    raise GovernanceError("runtime_role_schema_unqualified")


def grant_statements(schema, role):
    """Return reviewable grants for a separately created, dedicated runtime role."""
    result = [
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(schema), sql.Identifier(role)
        )
    ]
    for name in sorted(TABLES):
        result.append(
            sql.SQL("GRANT {} ON TABLE {}.{} TO {}").format(
                sql.SQL(", ").join(sql.SQL(p) for p in sorted(permissions(name))),
                sql.Identifier(schema),
                sql.Identifier(name),
                sql.Identifier(role),
            )
        )
    result.append(
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(schema), sql.Identifier(role)
        )
    )
    result.append(
        sql.SQL("GRANT EXECUTE ON FUNCTION {}.governance_runtime_guard() TO {}").format(
            sql.Identifier(schema), sql.Identifier(role)
        )
    )
    return result


def check_runtime_role(store, *, tx=None):
    with store.transaction() if tx is None else nullcontext(tx) as tx:
        role = tx.execute(
            "SELECT oid,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        if not role:
            raise GovernanceError("runtime_role_overprivileged")
        schema = tx.execute(
            "SELECT has_schema_privilege(current_user,current_schema(),'CREATE') AS ddl,"
            "has_schema_privilege(current_user,current_schema(),'USAGE') AS usable,"
            "current_user<>session_user AS switched,"
            "has_database_privilege(current_user,current_database(),'CREATE') AS database_ddl"
        ).fetchone()
        memberships = tx.execute(
            "SELECT count(*) AS n FROM pg_auth_members WHERE member=%s", (role["oid"],)
        ).fetchone()
        owners = tx.execute(
            "SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=current_schema() AND pg_has_role(current_user,c.relowner,'MEMBER')) + "
            "(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=current_schema() AND pg_has_role(current_user,p.proowner,'MEMBER')) AS n"
        ).fetchone()
        if (
            any(role[k] for k in role if k != "oid")
            or schema["ddl"]
            or schema["switched"]
            or schema["database_ddl"]
            or memberships["n"]
            or owners["n"]
        ):
            raise GovernanceError("runtime_role_overprivileged")
        if not schema["usable"]:
            raise GovernanceError("runtime_role_insufficient")
        rows = tx.execute(
            "SELECT c.relname AS name,p.privilege,has_table_privilege(current_user,c.oid,p.privilege) AS full,"
            "CASE WHEN p.privilege IN ('SELECT','INSERT','UPDATE','REFERENCES') "
            "THEN has_any_column_privilege(current_user,c.oid,p.privilege) ELSE false END AS column_grant "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']) p(privilege) "
            "WHERE n.nspname=current_schema() AND c.relkind IN ('r','p')"
        ).fetchall()
        seen = {row["name"] for row in rows}
        if seen != TABLES:
            raise GovernanceError("runtime_role_schema_unqualified")
        for row in rows:
            allowed = permissions(row["name"])
            if row["privilege"] not in allowed and (row["full"] or row["column_grant"]):
                raise GovernanceError("runtime_role_overprivileged")
            if row["privilege"] in allowed and not row["full"]:
                raise GovernanceError("runtime_role_insufficient")
        sequences = tx.execute(
            "SELECT has_sequence_privilege(current_user,c.oid,'USAGE') AS usable,"
            "has_sequence_privilege(current_user,c.oid,'SELECT') AS readable,"
            "has_sequence_privilege(current_user,c.oid,'UPDATE') AS changeable "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=current_schema() AND c.relkind='S'"
        ).fetchall()
        if any(row["changeable"] for row in sequences):
            raise GovernanceError("runtime_role_overprivileged")
        if any(not row["usable"] or not row["readable"] for row in sequences):
            raise GovernanceError("runtime_role_insufficient")
        guards = tx.execute(
            "SELECT p.proname,p.prosecdef,p.proconfig,has_function_privilege(current_user,p.oid,'EXECUTE') AS usable,"
            "EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl "
            "WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE') AS public_execute "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=current_schema() AND p.proname IN ('governance_runtime_guard','governance_operations_fence')"
        ).fetchall()
        if {row["proname"] for row in guards} != {
            "governance_runtime_guard",
            "governance_operations_fence",
        }:
            raise GovernanceError("runtime_role_schema_unqualified")
        if any(row["public_execute"] for row in guards):
            raise GovernanceError("runtime_role_overprivileged")
        if any(
            not row["prosecdef"] or row["proconfig"] != ["search_path=pg_catalog"] for row in guards
        ):
            raise GovernanceError("runtime_role_schema_unqualified")
        if not next(
            row["usable"] for row in guards if row["proname"] == "governance_runtime_guard"
        ):
            raise GovernanceError("runtime_role_insufficient")
    return True
