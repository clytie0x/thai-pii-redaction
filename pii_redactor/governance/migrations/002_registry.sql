CREATE TABLE governance_commands (
    actor_id uuid NOT NULL REFERENCES governance_members(member_id),
    command_key uuid NOT NULL,
    request_digest text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (actor_id, command_key)
);

CREATE TABLE governance_activities (
    activity_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    department_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('draft', 'submitted', 'active', 'rejected')),
    revision integer NOT NULL CHECK (revision > 0),
    data jsonb NOT NULL,
    created_by uuid NOT NULL REFERENCES governance_members(member_id),
    last_editor uuid NOT NULL REFERENCES governance_members(member_id),
    submitted_by uuid REFERENCES governance_members(member_id),
    review jsonb,
    reviewed_by uuid REFERENCES governance_members(member_id),
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE governance_notices (
    notice_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    activity_id uuid NOT NULL REFERENCES governance_activities(activity_id),
    payload_digest text NOT NULL,
    content_digest text NOT NULL,
    state text NOT NULL CHECK (state IN ('draft', 'published')),
    revision integer NOT NULL CHECK (revision > 0),
    data jsonb NOT NULL,
    created_by uuid NOT NULL REFERENCES governance_members(member_id),
    published_by uuid REFERENCES governance_members(member_id),
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE governance_grants (
    grant_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    target_id uuid NOT NULL REFERENCES governance_members(member_id),
    target_revision integer NOT NULL CHECK (target_revision > 0),
    proposed_by uuid NOT NULL REFERENCES governance_members(member_id),
    proposer_revision integer NOT NULL CHECK (proposer_revision > 0),
    approved_by uuid REFERENCES governance_members(member_id),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    state text NOT NULL CHECK (state IN ('proposed', 'applied')),
    roles jsonb NOT NULL,
    departments jsonb NOT NULL,
    enabled_change boolean,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE governance_outbox (
    event_id uuid PRIMARY KEY REFERENCES governance_audit(event_id),
    event_code text NOT NULL,
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'claimed', 'delivered', 'failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION governance_preserve_notice() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'published' THEN
        RAISE EXCEPTION 'notice_immutable' USING ERRCODE = '42501';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NEW.state = 'published' AND (
        NEW.data IS DISTINCT FROM OLD.data OR
        NEW.payload_digest IS DISTINCT FROM OLD.payload_digest OR
        NEW.content_digest IS DISTINCT FROM OLD.content_digest OR
        NEW.activity_id IS DISTINCT FROM OLD.activity_id
    ) THEN
        RAISE EXCEPTION 'notice_immutable' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER governance_notice_immutable
BEFORE UPDATE OR DELETE ON governance_notices
FOR EACH ROW EXECUTE FUNCTION governance_preserve_notice();
