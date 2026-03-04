"""Pydantic models for Foundry TUI configuration."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DeploymentType(str, Enum):
    """Model deployment types."""

    AZURE_OPENAI = "azure_openai"
    AZURE_AI = "azure_ai"
    SERVERLESS = "serverless"


class ModelCategory(str, Enum):
    """Model categories."""

    CHAT = "chat"
    REASONING = "reasoning"


class ModelCapabilities(BaseModel):
    """Model capabilities."""

    tools: bool = False
    streaming: bool = True
    vision: bool = False


class AzureOpenAIDeployment(BaseModel):
    """Azure OpenAI deployment configuration."""

    type: Literal["azure_openai"]
    deployment_name: str


class AzureAIDeployment(BaseModel):
    """Azure AI Services deployment configuration."""

    type: Literal["azure_ai"]
    deployment_name: str


class ServerlessDeployment(BaseModel):
    """Serverless endpoint deployment configuration."""

    type: Literal["serverless"]
    endpoint_env: str
    key_env: str


class Model(BaseModel):
    """Model definition from catalog."""

    id: str
    name: str
    provider: str
    category: ModelCategory
    deployment: AzureOpenAIDeployment | AzureAIDeployment | ServerlessDeployment
    capabilities: ModelCapabilities
    context_window: int
    max_output_tokens: int

    @property
    def deployment_type(self) -> DeploymentType:
        """Get the deployment type."""
        return DeploymentType(self.deployment.type)


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
