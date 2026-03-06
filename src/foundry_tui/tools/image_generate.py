"""Image generation tool — calls FLUX.2-pro on Azure AI Services.

Uses the Black Forest Labs provider API (not the OpenAI deployments path):
  POST {endpoint}/providers/blackforestlabs/v1/{deployment}?api-version=preview
  Auth: Bearer token
  Body: { prompt, model, width, height, n }
  Response: { data: [{ b64_json }] }
"""

import base64
import logging
import os
from datetime import datetime

import httpx

from foundry_tui.tools.base import Tool, ToolResult
from foundry_tui.tools.file_create import DOWNLOADS_DIR, resolve_collision, _path_to_file_url

logger = logging.getLogger(__name__)

# FLUX.2-pro supports up to 4MP; these are common presets
SIZE_MAP = {
    "1024x1024": (1024, 1024),
    "1024x1536": (1024, 1536),
    "1536x1024": (1536, 1024),
}
VALID_SIZES = set(SIZE_MAP.keys())


class GenerateImageTool(Tool):
    """Generate an image using FLUX.2-pro on Azure AI Services."""

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
    ):
        self._deployment = deployment
        self._api_url = (
            f"{endpoint.rstrip('/')}/providers/blackforestlabs"
            f"/v1/{deployment}?api-version=preview"
        )
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def execute(self, *, prompt: str, size: str = "1024x1024") -> ToolResult:
        """Generate an image and save it to ~/Downloads/."""
        try:
            if size not in VALID_SIZES:
                size = "1024x1024"
            width, height = SIZE_MAP[size]

            logger.info(
                "Generating image: prompt=%s, size=%s",
                prompt[:80], size,
            )

            payload = {
                "prompt": prompt,
                "model": self._deployment,
                "width": width,
                "height": height,
                "n": 1,
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self._api_url,
                    headers=self._headers,
                    json=payload,
                )

            if response.status_code != 200:
                error_body = response.text[:300]
                logger.error("FLUX API error %d: %s", response.status_code, error_body)
                return ToolResult(
                    content=f"Error: Image API returned {response.status_code}: {error_body}",
                    error=True,
                )

            data = response.json()
            b64_content = data.get("data", [{}])[0].get("b64_json")
            if not b64_content:
                return ToolResult(
                    content="Error: API returned empty image data.",
                    error=True,
                )

            image_bytes = base64.b64decode(b64_content)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.png"

            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
            target = resolve_collision(DOWNLOADS_DIR, filename)

            target.write_bytes(image_bytes)
            size_kb = len(image_bytes) / 1024
            file_url = _path_to_file_url(target)

            logger.info("Image saved: %s (%.1f KB)", target, size_kb)

            return ToolResult(
                content=(
                    f"✅ Image generated and saved\n"
                    f"📁 Location: {file_url}\n"
                    f"📐 Size: {size} | 📏 {size_kb:.0f} KB"
                ),
            )

        except httpx.TimeoutException:
            return ToolResult(
                content="Error: Image generation timed out. FLUX.2-pro can take up to 60s — please try again.",
                error=True,
            )
        except Exception as e:
            error_msg = str(e)
            if "content_policy" in error_msg.lower() or "safety" in error_msg.lower():
                return ToolResult(
                    content="Error: Image generation was blocked by the content safety filter. Try a different prompt.",
                    error=True,
                )
            logger.exception("Image generation failed: %s", e)
            return ToolResult(content=f"Error generating image: {error_msg}", error=True)


def create_image_tool() -> GenerateImageTool | None:
    """Create an image generation tool if FLUX.2-pro deployment is configured."""
    deployment = os.environ.get("AZURE_AI_IMAGE_DEPLOYMENT")
    if not deployment:
        return None

    endpoint = os.environ.get("AZURE_AI_ENDPOINT")
    api_key = os.environ.get("AZURE_AI_API_KEY")
    if not endpoint or not api_key:
        logger.warning("Image deployment set but Azure AI Services endpoint/key missing")
        return None

    logger.info("Image generation tool configured (deployment: %s)", deployment)
    return GenerateImageTool(
        endpoint=endpoint,
        api_key=api_key,
        deployment=deployment,
    )
