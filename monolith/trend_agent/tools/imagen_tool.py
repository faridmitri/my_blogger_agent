"""Imagen 4 cover-image tool.

Uses only the officially documented Imagen parameters:
  https://ai.google.dev/gemini-api/docs/imagen

Runs against Vertex AI (project + region + ADC) for consistency with
the rest of the pipeline, then uploads the returned bytes to Cloud
Storage explicitly.
"""
import os
import uuid
import datetime
import logging

from google import genai
from google.genai import types
from google.cloud import storage

logger = logging.getLogger(__name__)


def generate_cover_image(prompt: str, aspect_ratio: str = "16:9") -> dict:
    """Generate a blog cover image and save it to Cloud Storage.

    Call this tool exactly ONCE per blog post, with a short visual
    description of the desired cover image. The returned URL is
    immediately embeddable in an HTML <img> tag.

    Args:
        prompt: One sentence describing the desired image. No logos,
            faces, or rendered text. Example: "A minimalist illustration
            of a glowing neural network over a city skyline at dusk,
            vector art style."
        aspect_ratio: One of "1:1", "3:4", "4:3", "16:9", "9:16".
            Default "16:9" for blog headers.

    Returns:
        On success: {"cover_image_url": "<https URL>", "gcs_uri": "<gs:// URI>"}
        On failure: {"error": "<reason>"}
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("VERTEX_IMAGEN_LOCATION", "us-central1")
    bucket_name = os.environ.get("IMAGE_BUCKET")
    if not project or not bucket_name:
        return {"error": "GOOGLE_CLOUD_PROJECT or IMAGE_BUCKET env var not set"}

    # --- 1. Generate the image (official-docs-compliant config) ---
    try:
        client = genai.Client(vertexai=True, project=project, location=location)
        response = client.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                person_generation="allow_adult",
            ),
        )
    except Exception as e:
        logger.exception("Imagen API call failed")
        return {"error": f"Imagen API call failed: {e}"}

    if not response.generated_images:
        return {"error": "Imagen returned no images (likely safety-filtered)"}

    image_bytes = response.generated_images[0].image.image_bytes
    if not image_bytes:
        return {"error": "Imagen response missing image bytes"}

    # --- 2. Upload to Cloud Storage explicitly ---
    today = datetime.date.today().isoformat()
    blob_name = f"blog-covers/{today}/{uuid.uuid4().hex}.png"

    try:
        storage_client = storage.Client(project=project)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type="image/png")
    except Exception as e:
        logger.exception("Cloud Storage upload failed")
        return {"error": f"Cloud Storage upload failed: {e}"}

    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

    return {"cover_image_url": public_url, "gcs_uri": gcs_uri}