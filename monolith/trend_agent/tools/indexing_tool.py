import os
import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


def request_google_indexing(url: str) -> dict:
    """Ping Google Indexing API to request crawl of a newly published URL.

    Called directly from run_agent.py — no LLM agent needed.

    Returns:
        On success: {"success": True, "url": "...", "notify_time": "..."}
        On failure: {"error": "<reason>"}
    """
    client_id = os.environ.get("BLOGGER_CLIENT_ID")
    client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
    refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        return {
            "error": "Missing env vars: BLOGGER_CLIENT_ID, "
                     "BLOGGER_CLIENT_SECRET, or BLOGGER_REFRESH_TOKEN"
        }

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/indexing"],
        )
        creds.refresh(Request())

        response = httpx.post(
            "https://indexing.googleapis.com/v3/urlNotifications:publish",
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            },
            json={"url": url, "type": "URL_UPDATED"},
            timeout=30,
        )

        if response.status_code == 200:
            meta = response.json().get("urlNotificationMetadata", {})
            return {
                "success": True,
                "url": meta.get("url", url),
                "notify_time": meta.get("latestUpdate", {}).get("notifyTime", ""),
            }

        return {"error": f"Indexing API {response.status_code}: {response.text}"}

    except Exception as e:
        return {"error": str(e)}
