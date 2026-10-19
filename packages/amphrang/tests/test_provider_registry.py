"""One provider registry, consumed by every surface (spec: no copied lists)."""

import pytest

from amphrang.engine.ai_client import PROVIDER_FACTORIES, get_provider_factories

EXPECTED = {"fake", "pathumma", "tokenmind", "ollama", "claude"}


class TestCanonicalRegistry:
    def test_tokenmind_is_registered_by_name(self):
        # Asserted by NAME, not set-equality: equality alone passes when the
        # provider is forgotten everywhere at once (the likeliest mistake).
        assert "tokenmind" in PROVIDER_FACTORIES

    def test_full_registry(self):
        assert set(PROVIDER_FACTORIES) == EXPECTED

    def test_registry_is_immutable(self):
        with pytest.raises(TypeError):
            PROVIDER_FACTORIES["evil"] = object  # type: ignore[index]

    def test_filter_returns_subset(self):
        assert set(get_provider_factories(allowed=["fake", "tokenmind"])) == {
            "fake",
            "tokenmind",
        }

    def test_filter_fails_loud_on_unknown_name(self):
        with pytest.raises(ValueError, match="typo_provider"):
            get_provider_factories(allowed=["fake", "typo_provider"])


class TestSurfaceRegistries:
    def test_server_surface_has_tokenmind(self):
        pytest.importorskip("fastapi")
        from amphrang.server import server

        assert "tokenmind" in server._PROVIDER_FACTORIES
        assert set(server._PROVIDER_FACTORIES) == EXPECTED
