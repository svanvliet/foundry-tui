"""Image generation tool — calls GPT-image-1 on Azure OpenAI."""

import base64
import logging
import os
from datetime import datetime
from pathlib import Path

from openai import AsyncAzureOpenAI

from foundry_tui.tools.base import Tool, ToolResult
from foundry_tui.tools.file_create import DOWNLOADS_DIR, resolve_collision, _path_to_file_url

logger = logging.getLogger(__name__)

VALID_SIZES = {"1024x1024", "1024x1536", "1536x1024"}
VALID_QUALITIES = {"low", "medium", "high"}


class GenerateImageTool(Tool):
    """Generate an image using GPT-image-1 on Azure OpenAI."""

    name = "generate_image"
    description = (
        "Generate an image from a text description using AI. "
        "The image is saved to the user's ~/Downloads/ folder as a PNG. "
        "Use when the user asks you to create, draw, generate, or design an image, "
        "illustration, logo, diagram, or any visual content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Detailed text description of the image to generate. "
                    "Be specific about style, composition, colors, and mood."
                ),
            },
            "size": {
                "type": "string",
                "enum": ["1024x1024", "1024x1536", "1536x1024"],
                "description": (
                    "Image dimensions. Use 1024x1024 for square, "
                    "1024x1536 for portrait, 1536x1024 for landscape."
                ),
            },
        },
        "required": ["prompt"],
    }

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2025-03-01-preview",
        default_quality: str = "high",
    ):
        self._deployment = deployment
        self._default_quality = default_quality
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=0,
        )

    @property
    def default_quality(self) -> str:
        return self._default_quality

    @default_quality.setter
    def default_quality(self, value: str) -> None:
        if value in VALID_QUALITIES:
            self._default_quality = value

    async def execute(self, *, prompt: str, size: str = "1024x1024") -> ToolResult:
        """Generate an image and save it to ~/Downloads/."""
        try:
            # Validate size
            if size not in VALID_SIZES:
                size = "1024x1024"

            logger.info(
                "Generating image: prompt=%s, size=%s, quality=%s",
                prompt[:80], size, self._default_quality,
            )

            # Call Azure OpenAI Images API
            response = await self._client.images.generate(
                model=self._deployment,
                prompt=prompt,
                size=size,
                quality=self._default_quality,
                response_format="b64_json",
                n=1,
            )

            # Extract base64 data
            image_data = response.data[0]
            b64_content = image_data.b64_json
            if not b64_content:
                return ToolResult(
                    content="Error: API returned empty image data.",
                    error=True,
                )

            # Decode
            image_bytes = base64.b64decode(b64_content)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.png"

            # Save to Downloads
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
            target = resolve_collision(DOWNLOADS_DIR, filename)

            target.write_bytes(image_bytes)
            size_kb = len(image_bytes) / 1024
            file_url = _path_to_file_url(target)

            logger.info("Image saved: %s (%.1f KB)", target, size_kb)

            # Get revised prompt if available
            revised = getattr(image_data, "revised_prompt", None)
            prompt_note = f"\n🔄 Revised prompt: {revised}" if revised else ""

            return ToolResult(
                content=(
                    f"✅ Image generated and saved\n"
                    f"📁 Location: {file_url}\n"
                    f"📐 Size: {size} | 📏 {size_kb:.0f} KB"
                    f"{prompt_note}"
                ),
            )

        except Exception as e:
            error_msg = str(e)
            # Extract useful info from API errors
            if "content_policy" in error_msg.lower() or "safety" in error_msg.lower():
                return ToolResult(
                    content="Error: Image generation was blocked by the content safety filter. Try a different prompt.",
                    error=True,
                )
            logger.exception("Image generation failed: %s", e)
            return ToolResult(content=f"Error generating image: {error_msg}", error=True)


def create_image_tool(default_quality: str = "high") -> GenerateImageTool | None:
    """Create an image generation tool if deployment is configured."""
    deployment = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT")
    if not deployment:
        return None

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        logger.warning("Image deployment set but Azure OpenAI endpoint/key missing")
        return None

    logger.info("Image generation tool configured (deployment: %s)", deployment)
    return GenerateImageTool(
        endpoint=endpoint,
        api_key=api_key,
        deployment=deployment,
        default_quality=default_quality,
    )
