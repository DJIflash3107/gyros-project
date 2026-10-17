import asyncio
import base64
from datetime import datetime
import os
import re
from typing import Tuple, Dict, Any, Optional

import httpx

from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import (
    AppException,
    AIRateLimitException,
    ValidationException,
    ImageGenerationException,
)
from app.helpers.logging import logger
from app.models.schemas.artifact import GenerateImageRequest


# Known text/vision/chat models that must NEVER be accepted as image-gen models
NON_IMAGE_MODELS = {
    "deepseek-v4-flash",
    "deepseek-chat",
    "deepseek-coder",
    "gpt-4",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "claude-3-5-sonnet",
    "qwen-2.5-72b",
    "qwen-vl",
    "llama-3-70b",
    "llama-3.1-8b",
}

# Substrings that indicate text/chat/vision capability, not image synthesis
NON_IMAGE_SUBSTRINGS = ["vision", "ocr", "chat", "instruct", "coder", "embed"]

# Substrings that indicate verified image synthesis models
IMAGE_GEN_SUBSTRINGS = ["sd", "stable-diffusion", "flux", "dall-e", "imagen", "midjourney", "image-gen"]

ORIENTATION_TO_SIZE = {
    "square": "1024x1024",
    "portrait": "1024x1792",
    "landscape": "1792x1024",
}


class ImageGeneratorService:
    """
    Service for generating F&B business-purpose images using verified image-generation models.
    Strictly prohibits treating vision/OCR/chat models as image generators.
    Enforces business-purpose restriction and never returns placeholder images on failure.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self.timeout = timeout if timeout is not None else settings.IMAGE_GEN_REQUEST_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else settings.IMAGE_GEN_MAX_RETRIES

    @property
    def base_url(self) -> str:
        return (self._base_url or settings.AMD_API_BASE_URL).rstrip("/")

    @property
    def api_key(self) -> str:
        return self._api_key if self._api_key is not None else settings.AMD_API_KEY

    @property
    def model(self) -> str:
        return self._model if self._model is not None else settings.IMAGE_GEN_MODEL

    def _verify_model(self, model_name: str) -> str:
        """Validate that the model explicitly supports image generation and is not a vision/text model."""
        clean_name = (model_name or "").strip()
        if not clean_name:
            raise AppException(
                status_code=503,
                message="Image generation model is not configured. Set IMAGE_GEN_MODEL in configuration.",
                errors={"model": "Missing IMAGE_GEN_MODEL"},
                error_code=ErrorCodeRegistry.ART_IMAGE_NOT_CONFIGURED,
            )

        lower_name = clean_name.lower()
        # Direct check against non-image models
        if lower_name in NON_IMAGE_MODELS:
            raise ValidationException(
                errors={"model": f"Model '{clean_name}' is a text/chat model, not an image generation model."},
                message="Model does not support image generation. Vision and chat models cannot generate images.",
                error_code=ErrorCodeRegistry.ART_IMAGE_MODEL_UNSUPPORTED,
            )

        # Check for non-image substrings unless it explicitly contains an image-gen substring
        has_image_sub = any(s in lower_name for s in IMAGE_GEN_SUBSTRINGS)
        has_non_image_sub = any(s in lower_name for s in NON_IMAGE_SUBSTRINGS)

        if has_non_image_sub and not has_image_sub:
            raise ValidationException(
                errors={"model": f"Model '{clean_name}' appears to be a vision/chat model, not an image generator."},
                message="Vision/OCR capability cannot be used for image generation.",
                error_code=ErrorCodeRegistry.ART_IMAGE_MODEL_UNSUPPORTED,
            )

        return clean_name

    def _enhance_prompt(self, request: GenerateImageRequest) -> str:
        """Enhance user prompt with F&B commercial visual cues."""
        style_prompt = request.style or "commercial photography"
        base_prompt = request.prompt.strip()

        if request.purpose == "product_catalog":
            enhancement = (
                f", {style_prompt}, commercial product catalog photography, isolated on clean background, "
                "studio lighting, ultra sharp focus, appetizing culinary detail, 8k resolution"
            )
        elif request.purpose == "promotional_poster":
            enhancement = (
                f", {style_prompt}, restaurant marketing poster visual, appetizing presentation, "
                "eye-catching commercial composition, vibrant appetizing colors, high resolution promotional visual"
            )
        elif request.purpose == "promotion_visual":
            enhancement = (
                f", {style_prompt}, delicious food presentation, professional food styling, warm ambient lighting, "
                "shallow depth of field, commercial food photography"
            )
        else:
            enhancement = f", {style_prompt}, professional culinary commercial photography"

        return f"{base_prompt}{enhancement}"

    async def generate_image(
        self,
        request: GenerateImageRequest,
        business_id: int,
    ) -> Tuple[bytes, str, str, Dict[str, Any]]:
        """
        Generate an image for F&B business purpose.
        Returns (image_bytes, file_name, mime_type, metadata_json).
        Never returns placeholder images on failure.
        """
        if not settings.IMAGE_GEN_ENABLED:
            raise AppException(
                status_code=503,
                message="Image generation service is currently disabled in system settings.",
                errors={"service": "IMAGE_GEN_ENABLED is False"},
                error_code=ErrorCodeRegistry.ART_IMAGE_NOT_CONFIGURED,
            )

        if not self.api_key or not self.api_key.strip():
            raise AppException(
                status_code=503,
                message="AMD API key is not configured for image generation.",
                errors={"api_key": "AMD_API_KEY is empty"},
                error_code=ErrorCodeRegistry.ART_IMAGE_NOT_CONFIGURED,
            )

        model = self._verify_model(self.model)
        size = ORIENTATION_TO_SIZE.get(request.orientation, "1024x1024")
        enhanced_prompt = self._enhance_prompt(request)

        endpoint = f"{self.base_url}/images/generations"
        payload = {
            "model": model,
            "prompt": enhanced_prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        last_error: Optional[Exception] = None
        attempt = 0

        while attempt <= self.max_retries:
            attempt += 1
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        timeout=float(self.timeout),
                        connect=20.0,
                        read=float(self.timeout),
                        write=20.0,
                    )
                ) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    image_data_list = data.get("data", [])
                    if not image_data_list:
                        raise ImageGenerationException(
                            message="Provider returned empty image data",
                            errors={"provider": "No image data returned in response"},
                            error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
                        )

                    first_item = image_data_list[0]
                    if "b64_json" in first_item and first_item["b64_json"]:
                        image_bytes = base64.b64decode(first_item["b64_json"])
                    elif "url" in first_item and first_item["url"]:
                        # Download image from URL
                        async with httpx.AsyncClient(timeout=30.0) as dl_client:
                            dl_resp = await dl_client.get(first_item["url"])
                            if dl_resp.status_code != 200:
                                raise ImageGenerationException(
                                    message=f"Failed to download generated image from URL: {dl_resp.status_code}",
                                    error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
                                )
                            image_bytes = dl_resp.content
                    else:
                        raise ImageGenerationException(
                            message="Provider response contained neither b64_json nor url",
                            error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
                        )

                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"{request.purpose}_{timestamp_str}.png"
                    mime_type = "image/png"

                    metadata = {
                        "business_id": business_id,
                        "purpose": request.purpose,
                        "prompt": request.prompt,
                        "enhanced_prompt": enhanced_prompt,
                        "model": model,
                        "size": size,
                        "orientation": request.orientation,
                        "style": request.style,
                        "product_id": request.product_id,
                        "promotion_plan_id": request.promotion_plan_id,
                        "generated_at": datetime.now().isoformat(),
                    }
                    return image_bytes, file_name, mime_type, metadata

                # Handle HTTP errors
                error_body = response.text
                try:
                    error_json = response.json()
                    error_msg = error_json.get("error", {}).get("message") or error_body
                except Exception:
                    error_msg = error_body

                if response.status_code == 400:
                    # Content safety or bad request
                    raise AppException(
                        status_code=400,
                        message=f"Image generation rejected: {error_msg}",
                        errors={"prompt": error_msg},
                        error_code=ErrorCodeRegistry.ART_IMAGE_CONTENT_POLICY,
                    )
                elif response.status_code == 429:
                    raise AIRateLimitException(
                        message=f"Image generation rate limit exceeded: {error_msg}",
                    )
                elif response.status_code in (500, 502, 503, 504):
                    logger.warning(
                        f"Image generation attempt {attempt}/{self.max_retries + 1} failed with status {response.status_code}: {error_msg}"
                    )
                    if attempt <= self.max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise ImageGenerationException(
                        message=f"Image generation provider error ({response.status_code}): {error_msg}",
                        status_code=502,
                        error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
                    )
                else:
                    raise ImageGenerationException(
                        message=f"Image generation failed with HTTP {response.status_code}: {error_msg}",
                        status_code=502,
                        error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
                    )

            except httpx.TimeoutException as exc:
                logger.warning(f"Image generation attempt {attempt} timed out: {exc}")
                if attempt <= self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise AppException(
                    status_code=504,
                    message="Image generation timed out waiting for provider response",
                    errors={"timeout": str(exc)},
                    error_code=ErrorCodeRegistry.ART_IMAGE_TIMEOUT,
                )
            except (AppException, ValidationException, AIRateLimitException):
                raise
            except Exception as exc:
                logger.error(f"Image generation unexpected error on attempt {attempt}: {exc}")
                last_error = exc
                if attempt <= self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ImageGenerationException(
                    message=f"Image generation failed: {str(exc)}",
                    errors={"provider": str(exc)},
                    error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
                )

        raise ImageGenerationException(
            message=f"Image generation failed after {self.max_retries + 1} attempts: {last_error}",
            error_code=ErrorCodeRegistry.ART_GENERATION_FAILED,
        )
