-- Initial organization activation is an offline operator action, never runtime setup.
CREATE TABLE governance_initial_activations (
    activation_id uuid PRIMARY KEY,
    review jsonb NOT NULL,
    review_digest text NOT NULL CHECK(length(review_digest)=64),
    key_proof text NOT NULL CHECK(length(key_proof)=64),
    scope_digest text NOT NULL CHECK(length(scope_digest)=64),
    prepared_head jsonb NOT NULL,
    phase text NOT NULL DEFAULT 'prepared' CHECK(phase IN ('prepared','released','superseded')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    released_at timestamptz
);
CREATE UNIQUE INDEX governance_initial_one_current ON governance_initial_activations ((true))
    WHERE phase IN ('prepared','released');
CREATE TABLE governance_initial_journal (
    activation_id uuid NOT NULL REFERENCES governance_initial_activations(activation_id),
    ordinal integer NOT NULL CHECK(ordinal>0),
    phase text NOT NULL CHECK(phase IN ('prepared','released','superseded')),
    evidence_digest text NOT NULL CHECK(length(evidence_digest)=64),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(activation_id,ordinal)
);
CREATE FUNCTION governance_initial_operator_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT has_table_privilege(current_user,format('%I.governance_operations',TG_TABLE_SCHEMA),'UPDATE') THEN
        RAISE EXCEPTION 'initial_operator_required' USING ERRCODE='42501';
    END IF;
    IF TG_OP='DELETE' OR (TG_TABLE_NAME='governance_initial_journal' AND TG_OP='UPDATE') THEN
        RAISE EXCEPTION 'initial_evidence_immutable' USING ERRCODE='42501';
    END IF;
    IF TG_OP='UPDATE' THEN
        IF (NEW.activation_id,NEW.review,NEW.review_digest,NEW.key_proof,NEW.scope_digest,NEW.prepared_head,NEW.created_at)
           IS DISTINCT FROM
           (OLD.activation_id,OLD.review,OLD.review_digest,OLD.key_proof,OLD.scope_digest,OLD.prepared_head,OLD.created_at)
           OR OLD.phase<>'prepared'
           OR NEW.phase NOT IN ('released','superseded')
           OR (NEW.phase='released') IS DISTINCT FROM (NEW.released_at IS NOT NULL) THEN
            RAISE EXCEPTION 'initial_evidence_immutable' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER initial_activation_operator BEFORE INSERT OR UPDATE OR DELETE ON governance_initial_activations
FOR EACH ROW EXECUTE FUNCTION governance_initial_operator_only();
CREATE TRIGGER initial_journal_operator BEFORE INSERT OR UPDATE OR DELETE ON governance_initial_journal
FOR EACH ROW EXECUTE FUNCTION governance_initial_operator_only();
REVOKE ALL ON FUNCTION governance_initial_operator_only() FROM PUBLIC;
