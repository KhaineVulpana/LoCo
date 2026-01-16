"""
Web tools for fetching and searching online content.
"""

import hashlib
import uuid
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

import aiohttp
import structlog

from app.tools.base import Tool
from app.core.config import settings
from app.indexing.chunker import SimpleChunker
from qdrant_client.models import PointStruct

logger = structlog.get_logger()


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _looks_like_html(text: str) -> bool:
    lowered = text.lower()
    return "<html" in lowered or "<!doctype" in lowered or "</p>" in lowered


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned: List[str] = []
    blank = False
    for line in lines:
        if line:
            cleaned.append(line)
            blank = False
        else:
            if not blank:
                cleaned.append("")
                blank = True
    return "\n".join(cleaned).strip()


class WebFetchTool(Tool):
    """Fetch a URL, extract readable text, and optionally ingest into RAG."""

    name = "web_fetch"
    description = "Fetch a URL and extract clean text. Optionally ingest into RAG."
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "HTTP/HTTPS URL to fetch"
            },
            "ingest": {
                "type": "boolean",
                "description": "Whether to chunk + embed into RAG",
                "default": False
            },
            "max_chars": {
                "type": "number",
                "description": "Max characters to return/ingest",
                "default": 20000
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Request timeout in seconds",
                "default": 20
            }
        },
        "required": ["url"]
    }

    def __init__(self, module_id: str, embedding_manager=None, vector_store=None):
        self.module_id = module_id
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.chunker = SimpleChunker(window_size=50, overlap=10)

    def approval_prompt(self, arguments: Dict[str, Any]) -> str:
        url = arguments.get("url", "")
        return f"Approve web fetch: {url}"

    async def execute(
        self,
        url: str,
        ingest: bool = False,
        max_chars: int = 20000,
        timeout_seconds: int = 20
    ) -> Dict[str, Any]:
        if not _is_http_url(url):
            return {"success": False, "error": "Invalid URL (must be http/https)."}

        timeout_seconds = max(int(timeout_seconds), 1)
        max_chars = max(int(max_chars), 0)

        headers = {
            "User-Agent": getattr(settings, "WEB_FETCH_USER_AGENT", "LoCo-Agent/0.1")
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                headers=headers
            ) as session:
                async with session.get(url, allow_redirects=True) as response:
                    status = response.status
                    content_type = response.headers.get("Content-Type", "")
                    if status >= 400:
                        return {
                            "success": False,
                            "error": f"Fetch failed with status {status}"
                        }
                    raw_text = await response.text()
        except Exception as exc:
            logger.error("web_fetch_failed", url=url, error=str(exc))
            return {"success": False, "error": f"Fetch failed: {str(exc)}"}

        title: Optional[str] = None
        cleaned_text = raw_text

        if "text/html" in content_type or _looks_like_html(raw_text):
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw_text, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
                cleaned_text = soup.get_text(separator="\n")
            except Exception as exc:
                logger.warning("html_parse_failed", url=url, error=str(exc))
                cleaned_text = raw_text

        cleaned_text = _clean_text(cleaned_text)

        if max_chars and len(cleaned_text) > max_chars:
            cleaned_text = cleaned_text[:max_chars]
            truncated = True
        else:
            truncated = False

        ingest_result = None
        if ingest:
            if not self.embedding_manager or not self.vector_store:
                return {
                    "success": False,
                    "error": "Embedding manager or vector store not available for ingestion."
                }
            if not cleaned_text.strip():
                return {"success": False, "error": "No readable content to ingest."}

            content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
            collection_name = f"loco_rag_{self.module_id}"

            try:
                self.vector_store.create_collection(
                    collection_name=collection_name,
                    vector_size=self.embedding_manager.get_dimensions()
                )

                chunks = self.chunker.chunk_text(cleaned_text)
                if not chunks:
                    return {"success": False, "error": "Chunking produced no content."}

                chunk_contents = [chunk.content for chunk in chunks]
                embeddings = self.embedding_manager.embed(chunk_contents)

                points = []
                for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    point_id = str(uuid.uuid5(
                        uuid.NAMESPACE_URL, f"{url}|{content_hash}|{idx}"
                    ))
                    points.append(PointStruct(
                        id=point_id,
                        vector=embedding.tolist(),
                        payload={
                            "module_id": self.module_id,
                            "source": url,
                            "url": url,
                            "title": title,
                            "chunk_index": idx,
                            "content": chunk.content,
                            "content_hash": content_hash,
                            "type": "web"
                        }
                    ))

                self.vector_store.upsert_vectors(collection_name, points)
                ingest_result = {
                    "collection": collection_name,
                    "chunks": len(points),
                    "content_hash": content_hash
                }
            except Exception as exc:
                logger.error("web_ingest_failed", url=url, error=str(exc))
                return {"success": False, "error": f"Ingest failed: {str(exc)}"}

        return {
            "success": True,
            "url": url,
            "title": title,
            "content_type": content_type,
            "text": cleaned_text,
            "truncated": truncated,
            "ingested": ingest_result
        }


class WebSearchTool(Tool):
    """Search the web using SerpAPI."""

    name = "web_search"
    description = "Search the web via SerpAPI and return top results."
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "limit": {
                "type": "number",
                "description": "Max results to return",
                "default": 5
            },
            "engine": {
                "type": "string",
                "description": "SerpAPI engine (default: google)"
            },
            "location": {
                "type": "string",
                "description": "Location for localized results"
            }
        },
        "required": ["query"]
    }

    def approval_prompt(self, arguments: Dict[str, Any]) -> str:
        query = arguments.get("query", "")
        return f"Approve web search: {query}"

    async def execute(
        self,
        query: str,
        limit: int = 5,
        engine: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        api_key = getattr(settings, "SERPAPI_API_KEY", None)
        base_url = getattr(settings, "SERPAPI_BASE_URL", "https://serpapi.com/search.json")
        default_engine = getattr(settings, "SERPAPI_ENGINE", "google")

        if not api_key:
            return {"success": False, "error": "SERPAPI_API_KEY is not configured."}

        params = {
            "engine": engine or default_engine,
            "q": query,
            "num": max(int(limit), 1),
            "api_key": api_key
        }
        if location:
            params["location"] = location

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                async with session.get(base_url, params=params) as response:
                    if response.status >= 400:
                        text = await response.text()
                        return {
                            "success": False,
                            "error": f"Search failed with status {response.status}: {text}"
                        }
                    data = await response.json()
        except Exception as exc:
            logger.error("web_search_failed", query=query, error=str(exc))
            return {"success": False, "error": f"Search failed: {str(exc)}"}

        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "position": item.get("position")
            })

        if limit:
            results = results[: max(int(limit), 1)]

        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results)
        }
