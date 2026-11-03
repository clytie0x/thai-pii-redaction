-- Runtime credentials cannot release quarantine or disable its transaction fence.
-- Existing oversized metadata stays intact and blocks qualification for review.
ALTER TABLE governance_audit
    ADD CONSTRAINT governance_audit_details_bound CHECK(octet_length(details::text)<=4096) NOT VALID,
    ADD CONSTRAINT governance_audit_code_bound CHECK(octet_length(event_code)<=128) NOT VALID;

DO $migration$
DECLARE namespace text := current_schema(); target record;
BEGIN
    EXECUTE format($definition$
        CREATE FUNCTION %I.governance_runtime_guard() RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $guard$
        DECLARE ready_state text; active_key text;
        BEGIN
            IF pg_catalog.has_table_privilege(session_user, %L, 'UPDATE')
               AND current_setting('aiguard.production_operations',true) IS DISTINCT FROM 'on' THEN
                RETURN;
            END IF;
            SELECT state,active_key_version INTO ready_state,active_key
                FROM %I.governance_operations WHERE singleton FOR SHARE;
            IF ready_state IS DISTINCT FROM 'reconciled' THEN
                RAISE EXCEPTION 'operations_quarantined' USING ERRCODE='42501';
            END IF;
            IF active_key IS NULL OR active_key IS DISTINCT FROM current_setting('aiguard.key_version',true) THEN
                RAISE EXCEPTION 'key_version_stale' USING ERRCODE='42501';
            END IF;
        END;
        $guard$
    $definition$, namespace, format('%I.governance_operations',namespace), namespace);
    EXECUTE format($definition$
        CREATE OR REPLACE FUNCTION %I.governance_operations_fence() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $fence$
        BEGIN
            PERFORM %I.governance_runtime_guard();
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $fence$
    $definition$, namespace, namespace);
    EXECUTE format('REVOKE ALL ON FUNCTION %I.governance_runtime_guard() FROM PUBLIC',namespace);
    EXECUTE format('REVOKE ALL ON FUNCTION %I.governance_operations_fence() FROM PUBLIC',namespace);
    FOR target IN SELECT c.oid,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=namespace AND c.relkind IN ('r','p')
        AND (c.relname LIKE 'governance_%' OR c.relname LIKE 'enterprise_%')
        AND c.relname NOT IN ('governance_operations','governance_schema')
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid=target.oid AND tgname='operations_fence') THEN
            EXECUTE format('CREATE TRIGGER operations_fence BEFORE INSERT OR UPDATE OR DELETE ON %I.%I '
                'FOR EACH ROW EXECUTE FUNCTION %I.governance_operations_fence()',namespace,target.relname,namespace);
        END IF;
    END LOOP;
END;
$migration$;
