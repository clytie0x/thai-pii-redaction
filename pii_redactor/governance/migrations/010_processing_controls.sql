CREATE TABLE governance_processing_bindings (
    binding_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    activity_id uuid NOT NULL REFERENCES governance_activities(activity_id),
    activity_revision integer NOT NULL CHECK(activity_revision>0),
    department_id text NOT NULL,
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','submitted','reviewed','active','rejected','superseded')),
    data jsonb NOT NULL,
    data_digest text NOT NULL CHECK(length(data_digest)=64),
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewer_revision integer,
    review_evidence_ref uuid,
    review_digest text CHECK(length(review_digest)=64),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK(reviewed_by IS NULL OR reviewed_by<>proposed_by)
);
CREATE UNIQUE INDEX governance_processing_one_active ON governance_processing_bindings
    (organization_id,activity_id,activity_revision) WHERE state='active';
CREATE INDEX governance_processing_scope ON governance_processing_bindings
    (organization_id,department_id,binding_id);
CREATE TABLE governance_processing_history (
    binding_id uuid NOT NULL REFERENCES governance_processing_bindings(binding_id),
    revision integer NOT NULL,
    snapshot jsonb NOT NULL,
    PRIMARY KEY(binding_id,revision)
);
CREATE TABLE governance_processing_previews (
    binding_id uuid NOT NULL REFERENCES governance_processing_bindings(binding_id),
    revision integer NOT NULL,
    reviewer_id uuid NOT NULL REFERENCES governance_members(member_id),
    reviewer_revision integer NOT NULL,
    snapshot_digest text NOT NULL CHECK(length(snapshot_digest)=64),
    PRIMARY KEY(binding_id,revision,reviewer_id,snapshot_digest)
);
CREATE TABLE governance_instruction_controls (
    instruction_id uuid PRIMARY KEY REFERENCES governance_execution_instructions(instruction_id),
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    binding_id uuid NOT NULL REFERENCES governance_processing_bindings(binding_id),
    binding_revision integer NOT NULL,
    binding_digest text NOT NULL CHECK(length(binding_digest)=64),
    snapshot jsonb NOT NULL
);
CREATE TRIGGER governance_processing_history_no_change BEFORE UPDATE OR DELETE ON governance_processing_history
FOR EACH ROW EXECUTE FUNCTION governance_control_history_immutable();
CREATE TRIGGER governance_processing_previews_no_change BEFORE UPDATE OR DELETE ON governance_processing_previews
FOR EACH ROW EXECUTE FUNCTION governance_control_history_immutable();
CREATE TRIGGER governance_instruction_controls_no_change BEFORE UPDATE OR DELETE ON governance_instruction_controls
FOR EACH ROW EXECUTE FUNCTION governance_control_history_immutable();
