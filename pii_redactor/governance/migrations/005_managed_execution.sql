CREATE TABLE governance_collections (
    collection_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    activity_id uuid NOT NULL REFERENCES governance_activities(activity_id),
    activity_revision integer NOT NULL CHECK (activity_revision > 0),
    department_id text NOT NULL,
    consent_bound boolean NOT NULL,
    subject_id uuid,
    purpose_version uuid,
    key_version text NOT NULL,
    state text NOT NULL DEFAULT 'ready' CHECK (state IN ('ready','quarantined')),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_by uuid NOT NULL REFERENCES governance_members(member_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT consent_bound OR (subject_id IS NOT NULL AND purpose_version IS NOT NULL))
);

CREATE TABLE governance_managed_documents (
    document_id uuid PRIMARY KEY,
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    current_version integer NOT NULL CHECK (current_version > 0),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    state text NOT NULL DEFAULT 'active' CHECK (state IN ('active','restricted','suppressed','quarantined')),
    last_instruction_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE governance_document_versions (
    document_id uuid NOT NULL REFERENCES governance_managed_documents(document_id),
    version integer NOT NULL CHECK (version > 0),
    key_version text NOT NULL,
    nonce bytea NOT NULL CHECK (octet_length(nonce) = 12),
    ciphertext bytea NOT NULL CHECK (octet_length(ciphertext) BETWEEN 17 AND 32784),
    ciphertext_digest text NOT NULL CHECK (length(ciphertext_digest) = 64),
    content_type text NOT NULL CHECK (content_type IN ('text/plain','application/json')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id,version)
);

CREATE TABLE governance_protected_evidence (
    evidence_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    document_id uuid REFERENCES governance_managed_documents(document_id),
    target_version integer,
    key_version text NOT NULL,
    nonce bytea NOT NULL CHECK (octet_length(nonce) = 12),
    ciphertext bytea NOT NULL CHECK (octet_length(ciphertext) BETWEEN 17 AND 32784),
    ciphertext_digest text NOT NULL CHECK (length(ciphertext_digest) = 64),
    content_type text NOT NULL CHECK (content_type IN ('text/plain','application/json')),
    created_by uuid NOT NULL REFERENCES governance_members(member_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((document_id IS NULL) = (target_version IS NULL)),
    CHECK (target_version IS NULL OR target_version > 0)
);

CREATE TABLE governance_execution_instructions (
    instruction_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    document_id uuid NOT NULL REFERENCES governance_managed_documents(document_id),
    target_revision integer NOT NULL CHECK (target_revision > 0),
    target_version integer NOT NULL CHECK (target_version > 0),
    action text NOT NULL CHECK (action IN ('restrict','suppress','correct')),
    evidence_id uuid REFERENCES governance_protected_evidence(evidence_id),
    expires_at timestamptz NOT NULL,
    instruction_digest text NOT NULL CHECK (length(instruction_digest) = 64),
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL CHECK (proposer_revision > 0),
    approved_by uuid REFERENCES governance_members(member_id),
    approver_revision integer,
    state text NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed','pending','running','verified','failed','unknown')),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (approved_by IS NULL OR approved_by <> proposed_by),
    CHECK ((action = 'correct') = (evidence_id IS NOT NULL))
);

CREATE TABLE governance_execution_tasks (
    instruction_id uuid PRIMARY KEY REFERENCES governance_execution_instructions(instruction_id),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','running','verified','failed','unknown')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 10),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at timestamptz NOT NULL DEFAULT now(),
    worker_id text,
    lease_token uuid,
    lease_until timestamptz,
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((state = 'running') = (worker_id IS NOT NULL AND lease_token IS NOT NULL AND lease_until IS NOT NULL))
);

CREATE TABLE governance_execution_outcomes (
    instruction_id uuid PRIMARY KEY REFERENCES governance_execution_instructions(instruction_id),
    instruction_digest text NOT NULL CHECK (length(instruction_digest) = 64),
    document_id uuid NOT NULL REFERENCES governance_managed_documents(document_id),
    result_version integer NOT NULL CHECK (result_version > 0),
    result_revision integer NOT NULL CHECK (result_revision > 0),
    result_state text NOT NULL CHECK (result_state IN ('active','restricted','suppressed')),
    ciphertext_digest text NOT NULL CHECK (length(ciphertext_digest) = 64),
    verified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE governance_collection_snapshots (
    snapshot_id uuid PRIMARY KEY,
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    collection_revision integer NOT NULL CHECK (collection_revision > 0),
    manifest jsonb NOT NULL,
    manifest_digest text NOT NULL CHECK (length(manifest_digest) = 64),
    restore_controls jsonb,
    state text NOT NULL DEFAULT 'captured' CHECK (state IN ('captured','quarantined','reconciled')),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    captured_by uuid NOT NULL REFERENCES governance_members(member_id),
    restored_by uuid REFERENCES governance_members(member_id),
    reviewed_by uuid REFERENCES governance_members(member_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION governance_preserve_managed_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'managed_record_immutable' USING ERRCODE = '42501';
END;
$$;

CREATE TRIGGER governance_document_version_immutable BEFORE UPDATE OR DELETE
ON governance_document_versions FOR EACH ROW EXECUTE FUNCTION governance_preserve_managed_version();
CREATE TRIGGER governance_protected_evidence_immutable BEFORE UPDATE OR DELETE
ON governance_protected_evidence FOR EACH ROW EXECUTE FUNCTION governance_preserve_managed_version();
CREATE TRIGGER governance_execution_outcome_immutable BEFORE UPDATE OR DELETE
ON governance_execution_outcomes FOR EACH ROW EXECUTE FUNCTION governance_preserve_managed_version();

CREATE FUNCTION governance_preserve_instruction_target() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.organization_id,NEW.collection_id,NEW.document_id,NEW.target_revision,NEW.target_version,
        NEW.action,NEW.evidence_id,NEW.expires_at,NEW.instruction_digest,NEW.proposed_by,NEW.proposer_revision)
       IS DISTINCT FROM
       (OLD.organization_id,OLD.collection_id,OLD.document_id,OLD.target_revision,OLD.target_version,
        OLD.action,OLD.evidence_id,OLD.expires_at,OLD.instruction_digest,OLD.proposed_by,OLD.proposer_revision) THEN
        RAISE EXCEPTION 'instruction_immutable' USING ERRCODE = '42501';
    END IF;
    IF OLD.approved_by IS NOT NULL AND (NEW.approved_by,NEW.approver_revision)
       IS DISTINCT FROM (OLD.approved_by,OLD.approver_revision) THEN
        RAISE EXCEPTION 'approval_immutable' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER governance_instruction_target_immutable BEFORE UPDATE
ON governance_execution_instructions FOR EACH ROW EXECUTE FUNCTION governance_preserve_instruction_target();

CREATE FUNCTION governance_preserve_snapshot_manifest() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.collection_id,NEW.collection_revision,NEW.manifest,NEW.manifest_digest,NEW.captured_by)
       IS DISTINCT FROM (OLD.collection_id,OLD.collection_revision,OLD.manifest,OLD.manifest_digest,OLD.captured_by)
       OR (OLD.restore_controls IS NOT NULL AND NEW.restore_controls IS DISTINCT FROM OLD.restore_controls) THEN
        RAISE EXCEPTION 'snapshot_manifest_immutable' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER governance_snapshot_manifest_immutable BEFORE UPDATE
ON governance_collection_snapshots FOR EACH ROW EXECUTE FUNCTION governance_preserve_snapshot_manifest();

CREATE INDEX governance_execution_due ON governance_execution_tasks (available_at,instruction_id)
WHERE state = 'pending';
