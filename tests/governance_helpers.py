"""Synthetic organization fixture shared by real database integration tests."""

from types import SimpleNamespace

import pytest

from tests import test_governance_store as store_fixtures

database = store_fixtures.database


@pytest.fixture
def context(database):
    from pii_redactor.governance.models import Enrollment, Principal
    from pii_redactor.governance.store import Store

    members = store_fixtures.enrollments()
    members[0].roles.extend(["privacy_reviewer", "authority_reviewer"])
    members.extend(
        [
            Enrollment(
                principal=Principal(issuer=members[0].principal.issuer, subject="finance-staff"),
                roles=["data_steward"],
                departments=["finance"],
            ),
            Enrollment(
                principal=Principal(issuer=members[0].principal.issuer, subject="authority-staff"),
                roles=["authority_reviewer"],
                departments=["operations"],
            ),
        ]
    )
    store = Store(database, store_fixtures.ORG)
    store.migrate()
    ids = store.bootstrap(members)
    return SimpleNamespace(
        store=store,
        a=members[0].principal,
        b=members[1].principal,
        c=members[2].principal,
        d=members[3].principal,
        ids=ids,
    )
