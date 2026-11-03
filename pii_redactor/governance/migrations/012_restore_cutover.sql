-- Restore bookkeeping is local; canonical audit remains a source-chain prefix.
CREATE TABLE governance_restore_sessions (
    restore_id uuid PRIMARY KEY,
    cutover_id uuid NOT NULL UNIQUE,
    manifest jsonb NOT NULL,
    manifest_digest text NOT NULL CHECK(length(manifest_digest)=64),
    phase text NOT NULL DEFAULT 'restored' CHECK(phase IN ('restored','source_frozen','replayed','released')),
    source_fingerprint text CHECK(length(source_fingerprint)=64),
    source_head jsonb,
    source_control_digest text CHECK(length(source_control_digest)=64),
    profile_digest text CHECK(length(profile_digest)=64),
    control_digest text CHECK(length(control_digest)=64),
    target_head jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE governance_restore_journal (
    restore_id uuid NOT NULL REFERENCES governance_restore_sessions(restore_id),
    ordinal integer NOT NULL CHECK(ordinal>0),
    phase text NOT NULL CHECK(phase IN ('restored','source_frozen','replayed','released')),
    evidence_digest text NOT NULL CHECK(length(evidence_digest)=64),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(restore_id,ordinal)
);
CREATE FUNCTION governance_restore_operator_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT has_table_privilege(current_user,format('%I.governance_operations',TG_TABLE_SCHEMA),'UPDATE') THEN
        RAISE EXCEPTION 'recovery_operator_required' USING ERRCODE='42501';
    END IF;
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'restore_evidence_immutable' USING ERRCODE='42501'; END IF;
    IF TG_TABLE_NAME='governance_restore_journal' AND TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'restore_evidence_immutable' USING ERRCODE='42501';
    END IF;
    IF TG_OP='UPDATE' THEN
        IF (NEW.restore_id,NEW.cutover_id,NEW.manifest,NEW.manifest_digest,NEW.created_at) IS DISTINCT FROM
           (OLD.restore_id,OLD.cutover_id,OLD.manifest,OLD.manifest_digest,OLD.created_at) THEN
            RAISE EXCEPTION 'restore_evidence_immutable' USING ERRCODE='42501';
        END IF;
        IF OLD.source_fingerprint IS NOT NULL AND
           (NEW.source_fingerprint,NEW.source_head,NEW.source_control_digest,NEW.profile_digest) IS DISTINCT FROM
           (OLD.source_fingerprint,OLD.source_head,OLD.source_control_digest,OLD.profile_digest) THEN
            RAISE EXCEPTION 'restore_evidence_immutable' USING ERRCODE='42501';
        END IF;
        IF OLD.target_head IS NOT NULL AND
           (NEW.target_head,NEW.control_digest) IS DISTINCT FROM (OLD.target_head,OLD.control_digest) THEN
            RAISE EXCEPTION 'restore_evidence_immutable' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER restore_session_operator BEFORE INSERT OR UPDATE OR DELETE ON governance_restore_sessions
FOR EACH ROW EXECUTE FUNCTION governance_restore_operator_only();
CREATE TRIGGER restore_journal_operator BEFORE INSERT OR UPDATE OR DELETE ON governance_restore_journal
FOR EACH ROW EXECUTE FUNCTION governance_restore_operator_only();
REVOKE ALL ON FUNCTION governance_restore_operator_only() FROM PUBLIC;
