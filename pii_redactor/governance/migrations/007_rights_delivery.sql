CREATE TABLE governance_rights_cases (
    case_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    department_id text NOT NULL,
    intake jsonb NOT NULL,
    received_by uuid REFERENCES governance_members(member_id),
    received_session uuid REFERENCES enterprise_subject_sessions(session_id),
    subject_id uuid REFERENCES governance_subjects(subject_id),
    link_revision integer,
    revision integer NOT NULL DEFAULT 1 CHECK(revision > 0),
    state text NOT NULL DEFAULT 'received' CHECK(state IN
        ('received','verified','planned','approved','partial','closed','refused','withdrawn')),
    verification jsonb,
    verified_by uuid REFERENCES governance_members(member_id),
    verifier_revision integer,
    plan jsonb,
    plan_version integer NOT NULL DEFAULT 0,
    proposed_by uuid REFERENCES governance_members(member_id),
    proposer_revision integer,
    approved_by uuid REFERENCES governance_members(member_id),
    approver_revision integer,
    approval_expires_at timestamptz,
    review_ref uuid,
    closure_ref uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX governance_rights_scope ON governance_rights_cases(organization_id,department_id,case_id);
CREATE TABLE governance_rights_history (
    history_id uuid PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES governance_rights_cases(case_id),
    revision integer NOT NULL,
    kind text NOT NULL,
    data jsonb NOT NULL,
    actor_id uuid REFERENCES governance_members(member_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(case_id,revision)
);
CREATE TABLE governance_rights_manual (
    obligation_id uuid PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES governance_rights_cases(case_id),
    plan_version integer NOT NULL,
    data jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','submitted','verified','failed')),
    revision integer NOT NULL DEFAULT 1,
    evidence_ref uuid,
    submitted_by uuid REFERENCES governance_members(member_id),
    reviewed_by uuid REFERENCES governance_members(member_id),
    review_ref uuid
);
CREATE TABLE governance_rights_subject_commands (
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    command_key uuid NOT NULL,
    request_digest text NOT NULL,
    case_id uuid NOT NULL REFERENCES governance_rights_cases(case_id),
    PRIMARY KEY(subject_id,command_key)
);
CREATE TABLE governance_rights_instruction_bindings (
    instruction_id uuid PRIMARY KEY REFERENCES governance_execution_instructions(instruction_id),
    case_id uuid NOT NULL REFERENCES governance_rights_cases(case_id),
    plan_version integer NOT NULL
);
CREATE TABLE governance_rights_previews (
    case_id uuid NOT NULL REFERENCES governance_rights_cases(case_id),
    plan_version integer NOT NULL,
    reviewer_id uuid NOT NULL REFERENCES governance_members(member_id),
    plan_digest text NOT NULL,
    PRIMARY KEY(case_id,plan_version,reviewer_id)
);
CREATE TABLE governance_rights_deliveries (
    delivery_id uuid PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES governance_rights_cases(case_id),
    plan_version integer NOT NULL,
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    link_revision integer NOT NULL,
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    key_version text NOT NULL,
    nonce bytea NOT NULL CHECK(octet_length(nonce)=12),
    ciphertext bytea NOT NULL CHECK(octet_length(ciphertext) BETWEEN 17 AND 32784),
    ciphertext_digest text NOT NULL CHECK(length(ciphertext_digest)=64),
    expires_at timestamptz NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    state text NOT NULL DEFAULT 'issued' CHECK(state IN ('issued','downloaded','received','revoked')),
    downloaded_session uuid REFERENCES enterprise_subject_sessions(session_id),
    receipt_ref uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(case_id,plan_version)
);
CREATE FUNCTION governance_preserve_rights_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'rights_source_immutable' USING ERRCODE='42501'; END IF;
    IF TG_TABLE_NAME='governance_rights_cases' AND
      (NEW.intake,NEW.received_by,NEW.received_session,NEW.organization_id,NEW.department_id,NEW.created_at) IS DISTINCT FROM
      (OLD.intake,OLD.received_by,OLD.received_session,OLD.organization_id,OLD.department_id,OLD.created_at) THEN
        RAISE EXCEPTION 'rights_source_immutable' USING ERRCODE='42501';
    END IF;
    IF TG_TABLE_NAME='governance_rights_history' THEN
        RAISE EXCEPTION 'rights_source_immutable' USING ERRCODE='42501';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER governance_rights_intake_immutable BEFORE UPDATE OR DELETE ON governance_rights_cases
FOR EACH ROW EXECUTE FUNCTION governance_preserve_rights_source();
CREATE TRIGGER governance_rights_history_immutable BEFORE UPDATE OR DELETE ON governance_rights_history
FOR EACH ROW EXECUTE FUNCTION governance_preserve_rights_source();
