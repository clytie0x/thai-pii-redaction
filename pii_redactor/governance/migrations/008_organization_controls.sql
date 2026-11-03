CREATE TABLE governance_organization_controls (
    control_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    department_id text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('processor','transfer','incident','assessment','responsibility','policy','legal')),
    state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','submitted','reviewed','active','rejected','superseded')),
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    data jsonb NOT NULL,
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewer_revision integer,
    review_evidence_ref uuid,
    reviewed_at timestamptz,
    activated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK(reviewed_by IS NULL OR reviewed_by<>proposed_by)
);
CREATE INDEX governance_controls_scope ON governance_organization_controls(organization_id,department_id,kind,control_id);
CREATE TABLE governance_control_history (
    control_id uuid NOT NULL REFERENCES governance_organization_controls(control_id),
    revision integer NOT NULL,
    snapshot jsonb NOT NULL,
    PRIMARY KEY(control_id,revision)
);
CREATE FUNCTION governance_control_history_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable control history'; END $$;
CREATE TRIGGER governance_control_history_no_change BEFORE UPDATE OR DELETE ON governance_control_history
FOR EACH ROW EXECUTE FUNCTION governance_control_history_immutable();
