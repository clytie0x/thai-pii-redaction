CREATE TABLE governance_organization (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    organization_id uuid NOT NULL UNIQUE,
    enrolled_at timestamptz
);

CREATE TABLE governance_members (
    member_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    issuer text NOT NULL,
    subject text NOT NULL,
    roles jsonb NOT NULL CHECK (jsonb_typeof(roles) = 'array' AND jsonb_array_length(roles) > 0),
    departments jsonb NOT NULL CHECK (jsonb_typeof(departments) = 'array' AND jsonb_array_length(departments) > 0),
    enabled boolean NOT NULL DEFAULT true,
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, issuer, subject)
);

CREATE TABLE governance_audit (
    sequence bigint PRIMARY KEY CHECK (sequence > 0),
    event_id uuid NOT NULL UNIQUE,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    actor_id uuid,
    event_code text NOT NULL,
    target_id uuid,
    record_revision integer,
    occurred_at timestamptz NOT NULL,
    details jsonb NOT NULL,
    previous_hash text NOT NULL CHECK (length(previous_hash) = 64),
    event_hash text NOT NULL CHECK (length(event_hash) = 64)
);

CREATE FUNCTION governance_refuse_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_append_only' USING ERRCODE = '42501';
END;
$$;

CREATE TRIGGER governance_audit_immutable
BEFORE UPDATE OR DELETE ON governance_audit
FOR EACH ROW EXECUTE FUNCTION governance_refuse_audit_mutation();
