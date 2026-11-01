CREATE TABLE enterprise_login_states (
    state_hash text PRIMARY KEY CHECK (length(state_hash)=64),
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    binding_hash text NOT NULL CHECK (length(binding_hash)=64),
    nonce text NOT NULL CHECK (length(nonce)=43),
    code_verifier text NOT NULL CHECK (length(code_verifier)=43),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX enterprise_login_expiry ON enterprise_login_states(expires_at);

CREATE TABLE enterprise_staff_sessions (
    session_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES governance_organization(organization_id),
    member_id uuid NOT NULL REFERENCES governance_members(member_id),
    member_revision integer NOT NULL CHECK (member_revision>0),
    cookie_hash text NOT NULL UNIQUE CHECK (length(cookie_hash)=64),
    csrf_hash text NOT NULL CHECK (length(csrf_hash)=64),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    idle_until timestamptz NOT NULL,
    absolute_until timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT false
);

CREATE INDEX enterprise_session_member ON enterprise_staff_sessions(member_id);
