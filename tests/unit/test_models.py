"""Unit tests for models.py — Model catalog, Pydantic parsing, lookups."""

import json

import pytest
from pydantic import ValidationError

from foundry_tui.models import (
    Deployment,
    Model,
    ModelCapabilities,
    ModelCatalog,
    ModelCategory,
    ProvisionableModel,
    RateLimits,
)


class TestLoadCatalog:
    """Tests for loading the real models-catalog.json."""

    def test_load_catalog_from_json(self, catalog: ModelCatalog):
        """All models in the catalog should parse successfully."""
        assert len(catalog.models) > 0
        for model in catalog.models:
            assert model.id
            assert model.name
            assert model.provider
            assert model.deployment_name

    def test_provisionable_models(self, catalog: ModelCatalog):
        """Available-for-provisioning list should parse correctly."""
        assert len(catalog.available_for_provisioning) > 0
        for pm in catalog.available_for_provisioning:
            assert pm.id
            assert pm.registry
            assert pm.model_id


class TestModelDeployment:
    """Tests for the unified Deployment class."""

    def test_model_deployment_name(self):
        """Model.deployment_name property should return the deployment name."""
        model = Model(
            id="test",
            name="Test Model",
            provider="test",
            category=ModelCategory.CHAT,
            deployment=Deployment(deployment_name="test-deploy"),
            capabilities=ModelCapabilities(),
            context_window=4096,
            max_output_tokens=1024,
        )
        assert model.deployment_name == "test-deploy"

    def test_extra_fields_ignored(self):
        """Deployment JSON with extra fields (e.g. vestigial 'type') should still parse."""
        data = {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "provider": "openai",
            "category": "chat",
            "deployment": {
                "type": "azure_openai",
                "deployment_name": "gpt-4o",
            },
            "capabilities": {"tools": True, "streaming": True},
            "context_window": 128000,
            "max_output_tokens": 16384,
        }
        model = Model.model_validate(data)
        assert model.deployment_name == "gpt-4o"

    def test_deployment_missing_name_raises(self):
        """Deployment without deployment_name should fail validation."""
        with pytest.raises(ValidationError):
            Deployment.model_validate({})


class TestCatalogLookups:
    """Tests for ModelCatalog query methods."""

    def test_get_model_by_id(self, catalog: ModelCatalog):
        """get_model should return the correct model."""
        model = catalog.get_model("gpt-4o")
        assert model is not None
        assert model.name == "GPT-4o"
        assert model.provider == "openai"

    def test_get_model_not_found(self, catalog: ModelCatalog):
        """get_model should return None for unknown IDs."""
        assert catalog.get_model("nonexistent-model") is None

    def test_get_chat_models(self, catalog: ModelCatalog):
        """get_chat_models should return only chat models."""
        chat_models = catalog.get_chat_models()
        assert len(chat_models) > 0
        for m in chat_models:
            assert m.category == ModelCategory.CHAT

    def test_get_reasoning_models(self, catalog: ModelCatalog):
        """get_reasoning_models should return only reasoning models."""
        reasoning_models = catalog.get_reasoning_models()
        assert len(reasoning_models) > 0
        for m in reasoning_models:
            assert m.category == ModelCategory.REASONING

    def test_categories_are_exhaustive(self, catalog: ModelCatalog):
        """Chat + reasoning models should cover all models in the catalog."""
        chat = catalog.get_chat_models()
        reasoning = catalog.get_reasoning_models()
        assert len(chat) + len(reasoning) == len(catalog.models)


class TestModelCapabilitiesDefaults:
    """Tests for capability field defaults."""

    def test_defaults(self):
        """Missing capability fields should get correct defaults."""
        caps = ModelCapabilities()
        assert caps.tools is False
        assert caps.streaming is True
        assert caps.vision is False
        assert caps.api == "completions"
        assert caps.web_search is False

    def test_override(self):
        """Explicitly set capabilities should be preserved."""
        caps = ModelCapabilities(tools=True, vision=True, api="responses", web_search=True)
        assert caps.tools is True
        assert caps.vision is True
        assert caps.api == "responses"
        assert caps.web_search is True


class TestRateLimits:
    """Tests for rate limits."""

    def test_rate_limits_optional(self):
        """Models without rate_limits should have None."""
        model = Model(
            id="test",
            name="Test",
            provider="test",
            category=ModelCategory.CHAT,
            deployment=Deployment(deployment_name="test"),
            capabilities=ModelCapabilities(),
            context_window=4096,
            max_output_tokens=1024,
        )
        assert model.rate_limits is None

    def test_rate_limits_defaults(self):
        """RateLimits should have sensible defaults."""
        rl = RateLimits()
        assert rl.rpm_per_unit == 1
        assert rl.tpm_per_unit == 1000

    def test_rate_limits_custom(self):
        """Custom rate limits should be preserved."""
        rl = RateLimits(rpm_per_unit=10, tpm_per_unit=5000)
        assert rl.rpm_per_unit == 10
        assert rl.tpm_per_unit == 5000
