-- New installations and every whole-database restore require offline reconciliation.
CREATE TABLE governance_operations (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    state text NOT NULL DEFAULT 'quarantined' CHECK (state IN ('quarantined','reconciled')),
    restore_id uuid,
    active_key_version text,
    reconciled_at timestamptz,
    control_digest text CHECK (length(control_digest)=64)
);
INSERT INTO governance_operations DEFAULT VALUES;

CREATE FUNCTION governance_operations_fence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ready_state text; active_key text;
BEGIN
    IF current_setting('aiguard.production_operations', true) = 'on' THEN
        SELECT state,active_key_version INTO ready_state,active_key
            FROM governance_operations WHERE singleton FOR SHARE;
        IF ready_state IS DISTINCT FROM 'reconciled' THEN
            RAISE EXCEPTION 'operations_quarantined' USING ERRCODE='42501';
        END IF;
        IF active_key IS NOT NULL AND active_key IS DISTINCT FROM current_setting('aiguard.key_version',true) THEN
            RAISE EXCEPTION 'key_version_stale' USING ERRCODE='42501';
        END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname=current_schema()
        AND (tablename LIKE 'governance_%' OR tablename LIKE 'enterprise_%')
        AND tablename NOT IN ('governance_operations','governance_schema')
    LOOP
        EXECUTE format('CREATE TRIGGER operations_fence BEFORE INSERT OR UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION governance_operations_fence()',t.tablename);
    END LOOP;
END;
$$;
