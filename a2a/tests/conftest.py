"""Shared test fixtures.

Sets dummy environment variables so that importing agent modules (which build
McpToolsets and AgentCards at import time) does not fail on missing creds.
All tests here are OFFLINE — no real API calls, no network.
"""

import os

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ.setdefault("VERTEX_IMAGEN_LOCATION", "us-central1")
os.environ.setdefault("IMAGE_BUCKET", "test-bucket")
os.environ.setdefault("BLOGGER_CLIENT_ID", "test-id")
os.environ.setdefault("BLOGGER_CLIENT_SECRET", "test-secret")
os.environ.setdefault("BLOGGER_REFRESH_TOKEN", "test-refresh")
os.environ.setdefault("BLOGGER_BLOG_ID", "1234567890")
os.environ.setdefault("FACEBOOK_PAGE_ID", "1234567890")
os.environ.setdefault("FACEBOOK_PAGE_ACCESS_TOKEN", "test-token")
os.environ.setdefault("FACEBOOK_API_VERSION", "v21.0")
