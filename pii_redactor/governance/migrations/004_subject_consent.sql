CREATE TABLE governance_subjects (
    subject_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    state text NOT NULL CHECK (state IN ('unresolved','resolved')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE governance_subject_links (
    link_id uuid PRIMARY KEY,
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    subject_revision integer NOT NULL CHECK (subject_revision > 0),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    state text NOT NULL CHECK (state IN ('proposed','awaiting_privacy','active','superseded','rejected')),
    issuer text NOT NULL,
    oidc_subject text NOT NULL,
    source_system text NOT NULL,
    source_record_id uuid NOT NULL,
    source_version text NOT NULL,
    departments jsonb NOT NULL CHECK (jsonb_array_length(departments) BETWEEN 1 AND 32),
    identity_evidence_ref uuid NOT NULL,
    capacity_evidence_ref uuid NOT NULL,
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL,
    identity_reviewed_by uuid REFERENCES governance_members(member_id),
    identity_reviewer_revision integer,
    identity_review_ref uuid,
    privacy_reviewed_by uuid REFERENCES governance_members(member_id),
    privacy_review_ref uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(subject_id,subject_revision)
);
CREATE UNIQUE INDEX governance_subject_active_identity ON governance_subject_links(organization_id,issuer,oidc_subject) WHERE state='active';
CREATE UNIQUE INDEX governance_subject_active_source ON governance_subject_links(organization_id,source_system,source_record_id) WHERE state='active';

CREATE TABLE enterprise_subject_login_states (
    state_hash text PRIMARY KEY CHECK (length(state_hash)=64),
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    binding_hash text NOT NULL CHECK (length(binding_hash)=64),
    nonce text NOT NULL CHECK (length(nonce)=43),
    code_verifier text NOT NULL CHECK (length(code_verifier)=43),
    expires_at timestamptz NOT NULL
);
CREATE TABLE enterprise_subject_sessions (
    session_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    link_revision integer NOT NULL CHECK (link_revision>0),
    issuer text NOT NULL,
    client_id text NOT NULL,
    cookie_hash text NOT NULL UNIQUE CHECK (length(cookie_hash)=64),
    csrf_hash text NOT NULL CHECK (length(csrf_hash)=64),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    idle_until timestamptz NOT NULL,
    absolute_until timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT false
);

CREATE TABLE governance_consent_purposes (
    purpose_version uuid PRIMARY KEY REFERENCES governance_notices(notice_id),
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    activity_id uuid NOT NULL REFERENCES governance_activities(activity_id),
    activity_revision integer NOT NULL,
    department_id text NOT NULL,
    notice_revision integer NOT NULL,
    notice_digest text NOT NULL CHECK (length(notice_digest)=64),
    activity_digest text NOT NULL CHECK (length(activity_digest)=64),
    purpose text NOT NULL,
    categories jsonb NOT NULL,
    recipients jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE governance_consent_presentations (
    presentation_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    session_id uuid NOT NULL REFERENCES enterprise_subject_sessions(session_id),
    link_revision integer NOT NULL,
    purpose_version uuid NOT NULL REFERENCES governance_consent_purposes(purpose_version),
    notice_digest text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);
CREATE TABLE governance_consent_events (
    consent_event_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    purpose_version uuid NOT NULL REFERENCES governance_consent_purposes(purpose_version),
    revision integer NOT NULL CHECK (revision>0),
    link_revision integer NOT NULL,
    action text NOT NULL CHECK (action IN ('grant','refuse','withdraw')),
    categories jsonb NOT NULL,
    notice_revision integer NOT NULL,
    notice_digest text NOT NULL,
    channel text NOT NULL CHECK (channel IN ('subject_portal','reviewed_offline_withdrawal','reviewed_representative')),
    session_id uuid REFERENCES enterprise_subject_sessions(session_id),
    staff_actor_id uuid REFERENCES governance_members(member_id),
    offline_case_id uuid,
    source_received_at timestamptz,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(subject_id,purpose_version,revision),
    CHECK ((channel='subject_portal' AND session_id IS NOT NULL AND staff_actor_id IS NULL AND offline_case_id IS NULL)
        OR (channel<>'subject_portal' AND session_id IS NULL AND staff_actor_id IS NOT NULL AND offline_case_id IS NOT NULL))
);
CREATE TABLE governance_consent_current (
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    purpose_version uuid NOT NULL REFERENCES governance_consent_purposes(purpose_version),
    consent_event_id uuid NOT NULL REFERENCES governance_consent_events(consent_event_id),
    revision integer NOT NULL,
    PRIMARY KEY(subject_id,purpose_version)
);
CREATE TABLE governance_subject_commands (
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    command_key uuid NOT NULL,
    request_digest text NOT NULL,
    consent_event_id uuid NOT NULL REFERENCES governance_consent_events(consent_event_id),
    PRIMARY KEY(subject_id,command_key)
);
CREATE TABLE governance_consent_propagation (
    propagation_id uuid PRIMARY KEY,
    consent_event_id uuid NOT NULL REFERENCES governance_consent_events(consent_event_id),
    recipient_ordinal integer NOT NULL CHECK (recipient_ordinal>0),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','failed','verified')),
    evidence_ref uuid,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewed_at timestamptz,
    UNIQUE(consent_event_id,recipient_ordinal),
    CHECK (state<>'verified' OR (evidence_ref IS NOT NULL AND reviewed_by IS NOT NULL))
);
CREATE TABLE governance_consent_offline_cases (
    case_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    subject_id uuid NOT NULL REFERENCES governance_subjects(subject_id),
    link_revision integer NOT NULL,
    purpose_version uuid NOT NULL REFERENCES governance_consent_purposes(purpose_version),
    categories jsonb NOT NULL,
    expected_consent_revision integer NOT NULL,
    action text NOT NULL CHECK (action IN ('grant','refuse','withdraw')),
    mode text NOT NULL CHECK (mode IN ('offline_withdrawal','representative')),
    source_evidence_ref uuid NOT NULL,
    capacity_evidence_ref uuid,
    representative_authority_ref uuid,
    source_received_at timestamptz NOT NULL,
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL,
    reviewed_by uuid REFERENCES governance_members(member_id),
    review_evidence_ref uuid,
    state text NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed','applied','rejected')),
    revision integer NOT NULL DEFAULT 1 CHECK (revision>0),
    CHECK ((mode='offline_withdrawal' AND action='withdraw') OR
           (mode='representative' AND capacity_evidence_ref IS NOT NULL AND representative_authority_ref IS NOT NULL))
);

CREATE FUNCTION governance_consent_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'consent_record_immutable' USING ERRCODE='42501';
END;
$$;
CREATE TRIGGER governance_consent_events_immutable BEFORE UPDATE OR DELETE ON governance_consent_events
FOR EACH ROW EXECUTE FUNCTION governance_consent_append_only();
CREATE TRIGGER governance_consent_purposes_immutable BEFORE UPDATE OR DELETE ON governance_consent_purposes
FOR EACH ROW EXECUTE FUNCTION governance_consent_append_only();

CREATE FUNCTION governance_subject_link_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'subject_link_immutable' USING ERRCODE='42501';
    END IF;
    IF ROW(NEW.subject_id,NEW.organization_id,NEW.subject_revision,NEW.issuer,NEW.oidc_subject,
           NEW.source_system,NEW.source_record_id,NEW.source_version,NEW.departments,
           NEW.identity_evidence_ref,NEW.capacity_evidence_ref,NEW.proposed_by,NEW.proposer_revision)
       IS DISTINCT FROM
       ROW(OLD.subject_id,OLD.organization_id,OLD.subject_revision,OLD.issuer,OLD.oidc_subject,
           OLD.source_system,OLD.source_record_id,OLD.source_version,OLD.departments,
           OLD.identity_evidence_ref,OLD.capacity_evidence_ref,OLD.proposed_by,OLD.proposer_revision) THEN
        RAISE EXCEPTION 'subject_link_immutable' USING ERRCODE='42501';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER governance_subject_link_version BEFORE UPDATE OR DELETE ON governance_subject_links
FOR EACH ROW EXECUTE FUNCTION governance_subject_link_version();
