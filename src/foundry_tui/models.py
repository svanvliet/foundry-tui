"""Pydantic models for Foundry TUI configuration."""

from enum import Enum

from pydantic import BaseModel, Field


class ModelCategory(str, Enum):
    """Model categories."""

    CHAT = "chat"
    REASONING = "reasoning"


class RateLimits(BaseModel):
    """Rate limit ratios per capacity unit."""

    rpm_per_unit: int = 1
    tpm_per_unit: int = 1000


class ModelCapabilities(BaseModel):
    """Model capabilities."""

    tools: bool = False
    streaming: bool = True
    vision: bool = False
    api: str = "completions"  # "responses" or "completions"
    web_search: bool = False  # Built-in web search (RAPI only)


class Deployment(BaseModel):
    """Model deployment configuration."""

    deployment_name: str


class Model(BaseModel):
    """Model definition from catalog."""

    id: str
    name: str
    provider: str
    category: ModelCategory
    deployment: Deployment
    capabilities: ModelCapabilities
    context_window: int
    max_output_tokens: int
    rate_limits: RateLimits | None = None

    @property
    def deployment_name(self) -> str:
        """Get the deployment name."""
        return self.deployment.deployment_name


class ProvisionableModel(BaseModel):
    """Model available for provisioning."""

    id: str
    registry: str
    model_id: str


class ModelCatalog(BaseModel):
    """Full model catalog."""

    models: list[Model]
    available_for_provisioning: list[ProvisionableModel] = Field(default_factory=list)

    def get_model(self, model_id: str) -> Model | None:
        """Get a model by ID."""
        for model in self.models:
            if model.id == model_id:
                return model
        return None

    def get_models_by_category(self, category: ModelCategory) -> list[Model]:
        """Get models by category."""
        return [m for m in self.models if m.category == category]

    def get_chat_models(self) -> list[Model]:
        """Get chat models."""
        return self.get_models_by_category(ModelCategory.CHAT)

    def get_reasoning_models(self) -> list[Model]:
        """Get reasoning models."""
        return self.get_models_by_category(ModelCategory.REASONING)
