CREATE TABLE governance_holds (
    hold_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    document_id uuid NOT NULL REFERENCES governance_managed_documents(document_id),
    target_revision integer NOT NULL CHECK(target_revision>0),
    target_version integer NOT NULL CHECK(target_version>0),
    actual_revision integer NOT NULL CHECK(actual_revision>0),
    actual_version integer NOT NULL CHECK(actual_version>0),
    actual_state text NOT NULL,
    state text NOT NULL CHECK(state IN ('effective','post_action_review','release_pending','released')),
    reason text NOT NULL CHECK(reason IN ('legal_preservation','rights_case','incident','review_required')),
    evidence_ref uuid NOT NULL,
    review_due_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    fenced_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    imposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    imposer_revision integer NOT NULL,
    reviewed_by uuid REFERENCES governance_members(member_id),
    review_evidence_ref uuid,
    post_action boolean NOT NULL,
    release_proposed_by uuid REFERENCES governance_members(member_id),
    release_proposer_revision integer,
    release_evidence_ref uuid,
    released_by uuid REFERENCES governance_members(member_id),
    release_review_ref uuid,
    released_at timestamptz,
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    CHECK(reviewed_by IS NULL OR reviewed_by<>imposed_by),
    CHECK(released_by IS NULL OR released_by<>release_proposed_by)
);
CREATE INDEX governance_hold_fence ON governance_holds(organization_id,collection_id,document_id)
WHERE state<>'released';

CREATE TABLE governance_retention_policies (
    policy_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    purpose_version uuid NOT NULL REFERENCES governance_notices(notice_id),
    activity_revision integer NOT NULL,
    data jsonb NOT NULL,
    state text NOT NULL DEFAULT 'proposed' CHECK(state IN ('proposed','active','superseded','rejected')),
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewer_revision integer,
    review_evidence_ref uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK(reviewed_by IS NULL OR reviewed_by<>proposed_by)
);
CREATE UNIQUE INDEX governance_retention_active ON governance_retention_policies(collection_id) WHERE state='active';

CREATE TABLE governance_retention_triggers (
    trigger_id uuid PRIMARY KEY,
    policy_id uuid NOT NULL REFERENCES governance_retention_policies(policy_id),
    document_id uuid NOT NULL REFERENCES governance_managed_documents(document_id),
    target_revision integer NOT NULL CHECK(target_revision>0),
    target_version integer NOT NULL CHECK(target_version>0),
    occurred_at timestamptz NOT NULL,
    evidence_ref uuid NOT NULL,
    state text NOT NULL DEFAULT 'proposed' CHECK(state IN ('proposed','active','rejected')),
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewer_revision integer,
    review_evidence_ref uuid,
    CHECK(reviewed_by IS NULL OR reviewed_by<>proposed_by),
    UNIQUE(policy_id,document_id,target_version)
);

CREATE TABLE governance_retention_due (
    due_id uuid PRIMARY KEY,
    policy_id uuid NOT NULL REFERENCES governance_retention_policies(policy_id),
    policy_revision integer NOT NULL,
    trigger_id uuid NOT NULL UNIQUE REFERENCES governance_retention_triggers(trigger_id),
    trigger_revision integer NOT NULL,
    collection_id uuid NOT NULL REFERENCES governance_collections(collection_id),
    document_id uuid NOT NULL REFERENCES governance_managed_documents(document_id),
    target_revision integer NOT NULL,
    target_version integer NOT NULL,
    due_at timestamptz NOT NULL,
    state text NOT NULL DEFAULT 'proposed' CHECK(state IN ('proposed','approved','issued')),
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewer_revision integer,
    review_evidence_ref uuid,
    approval_expires_at timestamptz,
    instruction_id uuid UNIQUE REFERENCES governance_execution_instructions(instruction_id)
);
CREATE TABLE governance_retention_instruction_links (
    instruction_id uuid PRIMARY KEY REFERENCES governance_execution_instructions(instruction_id),
    due_id uuid NOT NULL UNIQUE REFERENCES governance_retention_due(due_id)
);
CREATE TABLE governance_retention_copies (
    obligation_id uuid PRIMARY KEY,
    due_id uuid NOT NULL REFERENCES governance_retention_due(due_id),
    kind text NOT NULL CHECK(kind IN ('derived','processor','replica_wal','backup','physical_storage')),
    recipient_ref uuid NOT NULL,
    state text NOT NULL CHECK(state IN ('pending','failed','verified','not_applicable')),
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    evidence_ref uuid,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewed_at timestamptz,
    UNIQUE(due_id,kind,recipient_ref),
    CHECK(state NOT IN ('verified','not_applicable') OR evidence_ref IS NOT NULL)
);

CREATE FUNCTION governance_preserve_retention_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retention_source_immutable' USING ERRCODE='42501'; END IF;
    IF TG_TABLE_NAME='governance_retention_policies' AND
       (to_jsonb(NEW)-ARRAY['state','revision','reviewed_by','reviewer_revision','review_evidence_ref']) IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['state','revision','reviewed_by','reviewer_revision','review_evidence_ref']) THEN
        RAISE EXCEPTION 'retention_source_immutable' USING ERRCODE='42501';
    END IF;
    IF TG_TABLE_NAME='governance_retention_triggers' AND
       (to_jsonb(NEW)-ARRAY['state','revision','reviewed_by','reviewer_revision','review_evidence_ref']) IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['state','revision','reviewed_by','reviewer_revision','review_evidence_ref']) THEN
        RAISE EXCEPTION 'retention_source_immutable' USING ERRCODE='42501';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER governance_retention_policy_source BEFORE UPDATE OR DELETE ON governance_retention_policies
FOR EACH ROW EXECUTE FUNCTION governance_preserve_retention_source();
CREATE TRIGGER governance_retention_trigger_source BEFORE UPDATE OR DELETE ON governance_retention_triggers
FOR EACH ROW EXECUTE FUNCTION governance_preserve_retention_source();
