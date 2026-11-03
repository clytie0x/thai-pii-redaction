-- Offline migration authority only. Start with a new dedicated LOGIN role.
-- Its password and private connection file are provisioned separately.
-- psql --file runtime-role.sql -v schema=organization -v runtime_role=aiguard_runtime
\set ON_ERROR_STOP on
BEGIN;
SELECT set_config('aiguard.runtime_role', :'runtime_role', true);
DO $role$
DECLARE candidate record;
BEGIN
    SELECT * INTO candidate FROM pg_roles WHERE rolname=current_setting('aiguard.runtime_role');
    IF candidate IS NULL OR NOT candidate.rolcanlogin OR candidate.rolname=session_user OR candidate.rolsuper
       OR candidate.rolcreatedb OR candidate.rolcreaterole OR candidate.rolreplication
       OR candidate.rolbypassrls OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=candidate.oid) THEN
        RAISE EXCEPTION 'dedicated_runtime_role_required';
    END IF;
END;
$role$;
GRANT USAGE ON SCHEMA :"schema" TO :"runtime_role";
GRANT DELETE, INSERT, SELECT ON TABLE :"schema".enterprise_login_states TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".enterprise_staff_sessions TO :"runtime_role";
GRANT DELETE, INSERT, SELECT ON TABLE :"schema".enterprise_subject_login_states TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".enterprise_subject_sessions TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_activities TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_audit TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_collection_snapshots TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_collections TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_commands TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_consent_current TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_consent_events TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_consent_offline_cases TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_consent_presentations TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_consent_propagation TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_consent_purposes TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_control_history TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_document_versions TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_execution_instructions TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_execution_outcomes TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_execution_tasks TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_grants TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_holds TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_instruction_controls TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_initial_activations TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_initial_journal TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_managed_documents TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_members TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_notices TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_operations TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_organization TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_organization_controls TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_outbox TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_processing_bindings TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_processing_history TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_processing_previews TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_protected_evidence TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_restore_journal TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_restore_sessions TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_retention_copies TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_retention_due TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_retention_instruction_links TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_retention_policies TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_retention_triggers TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_rights_cases TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_rights_deliveries TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_rights_history TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_rights_instruction_bindings TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_rights_manual TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_rights_previews TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_rights_subject_commands TO :"runtime_role";
GRANT SELECT ON TABLE :"schema".governance_schema TO :"runtime_role";
GRANT INSERT, SELECT ON TABLE :"schema".governance_subject_commands TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_subject_links TO :"runtime_role";
GRANT INSERT, SELECT, UPDATE ON TABLE :"schema".governance_subjects TO :"runtime_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA :"schema" TO :"runtime_role";
GRANT EXECUTE ON FUNCTION :"schema".governance_runtime_guard() TO :"runtime_role";
COMMIT;
-- The application still verifies effective grants, PUBLIC grants and memberships.
