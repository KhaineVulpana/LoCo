"""
Headless browser tools using Playwright.
"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

import structlog

from app.tools.base import Tool

logger = structlog.get_logger()


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class HeadlessBrowserTool(Tool):
    """Render a URL with a headless browser and return text/HTML."""

    name = "headless_browser"
    description = "Render a URL with Playwright to get JS-rendered content."
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "HTTP/HTTPS URL to render"
            },
            "wait_ms": {
                "type": "number",
                "description": "Extra wait time after load (ms)",
                "default": 1000
            },
            "timeout_ms": {
                "type": "number",
                "description": "Navigation timeout (ms)",
                "default": 30000
            },
            "return_html": {
                "type": "boolean",
                "description": "Include page HTML in output",
                "default": True
            },
            "return_text": {
                "type": "boolean",
                "description": "Include page text in output",
                "default": True
            },
            "max_chars": {
                "type": "number",
                "description": "Max characters to return for text/html",
                "default": 20000
            }
        },
        "required": ["url"]
    }

    def approval_prompt(self, arguments: Dict[str, Any]) -> str:
        url = arguments.get("url", "")
        return f"Approve headless browser render: {url}"

    async def execute(
        self,
        url: str,
        wait_ms: int = 1000,
        timeout_ms: int = 30000,
        return_html: bool = True,
        return_text: bool = True,
        max_chars: int = 20000
    ) -> Dict[str, Any]:
        if not _is_http_url(url):
            return {"success": False, "error": "Invalid URL (must be http/https)."}

        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            return {
                "success": False,
                "error": f"Playwright not available: {str(exc)}"
            }

        wait_ms = max(int(wait_ms), 0)
        timeout_ms = max(int(timeout_ms), 1000)
        max_chars = max(int(max_chars), 0)

        html: Optional[str] = None
        text: Optional[str] = None

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                if wait_ms:
                    await page.wait_for_timeout(wait_ms)

                if return_html:
                    html = await page.content()
                if return_text:
                    text = await page.inner_text("body")

                await browser.close()
        except Exception as exc:
            logger.error("headless_browser_failed", url=url, error=str(exc))
            return {"success": False, "error": f"Headless render failed: {str(exc)}"}

        if max_chars:
            if html and len(html) > max_chars:
                html = html[:max_chars]
            if text and len(text) > max_chars:
                text = text[:max_chars]

        return {
            "success": True,
            "url": url,
            "html": html if return_html else None,
            "text": text if return_text else None
        }
