"""
Retriever - Searches indexed operational knowledge for relevant context
"""

from typing import List, Dict, Any, Optional, Callable, Iterable, Tuple
from dataclasses import dataclass
import asyncio
import os
import re
import shutil
import subprocess
import structlog
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore

logger = structlog.get_logger()


@dataclass
class RetrievalResult:
    """A single retrieval result"""
    score: float          # Similarity score (0-1)
    content: str         # Chunk content
    source: str          # Source identifier (file path, doc name, etc.)
    metadata: Dict[str, Any]  # Additional metadata
    frontend_id: str = None


@dataclass
class ContextPack:
    """Structured context pack within a token budget."""
    text: str
    items: List[RetrievalResult]
    token_count: int
    truncated: bool


class Retriever:
    """Retrieves relevant context from indexed operational knowledge"""

    def __init__(
        self,
        frontend_id: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore,
        db_session_maker: Optional[async_sessionmaker] = None,
        workspace_path: Optional[str] = None
    ):
        """
        Initialize retriever

        Args:
            frontend_id: Frontend to search in ("vscode", "android", "3d-gen")
            embedding_manager: Embedding manager instance
            vector_store: Vector store instance
        """
        self.frontend_id = frontend_id
        self.embedder = embedding_manager
        self.vector_store = vector_store
        self.db_session_maker = db_session_maker
        self.workspace_path = workspace_path
        self.collection_name = f"loco_rag_{frontend_id}"
        self._rg_path = shutil.which("rg")

        logger.debug("retriever_initialized", frontend_id=frontend_id)

    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.5
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for a query

        Args:
            query: Search query
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of RetrievalResult objects, sorted by score descending
        """
        if not query:
            logger.warning("empty_query")
            return []

        logger.debug("retrieval_start",
                    frontend_id=self.frontend_id,
                    query=query[:100],
                    limit=limit)

        # Embed query
        try:
            query_vector = self.embedder.embed_query(query)
        except Exception as e:
            logger.error("query_embedding_failed",
                        query=query[:100],
                        error=str(e))
            return []

        # Search vector store
        try:
            results = self.vector_store.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                limit=limit,
                score_threshold=score_threshold
            )
        except Exception as e:
            logger.error("vector_search_failed",
                        frontend_id=self.frontend_id,
                        error=str(e))
            return []

        # Convert to RetrievalResult objects
        retrieval_results = []
        for hit in results:
            payload = hit["payload"]

            retrieval_results.append(RetrievalResult(
                score=hit["score"],
                content=payload.get("content", ""),
                source=payload.get("source", payload.get("full_path", "unknown")),
                metadata=payload,
                frontend_id=self.frontend_id
            ))

        retrieval_results = self._rerank_results(retrieval_results, query)

        logger.info("retrieval_complete",
                   frontend_id=self.frontend_id,
                   query=query[:50],
                   results=len(retrieval_results),
                   top_score=retrieval_results[0].score if retrieval_results else 0)

        return retrieval_results

    async def retrieve_workspace(
        self,
        query: str,
        workspace_id: str,
        limit: int = 10,
        score_threshold: float = 0.5
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant workspace chunks for a query.

        Args:
            query: Search query
            workspace_id: Workspace identifier
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of RetrievalResult objects, sorted by score descending
        """
        if not query or not workspace_id:
            logger.warning("empty_workspace_query")
            return []

        collection_name = f"loco_rag_workspace_{workspace_id}"

        logger.debug("workspace_retrieval_start",
                    workspace_id=workspace_id,
                    query=query[:100],
                    limit=limit)

        # Embed query
        try:
            query_vector = self.embedder.embed_query(query)
        except Exception as e:
            logger.error("workspace_query_embedding_failed",
                        query=query[:100],
                        error=str(e))
            return []

        # Search vector store
        try:
            results = self.vector_store.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist(),
                limit=limit,
                score_threshold=score_threshold
            )
        except Exception as e:
            logger.error("workspace_vector_search_failed",
                        workspace_id=workspace_id,
                        error=str(e))
            return []

        content_by_vector_id = {}
        source_by_vector_id = {}
        if self.db_session_maker and results:
            vector_ids = [hit["id"] for hit in results]
            content_by_vector_id, source_by_vector_id = await self._hydrate_workspace_chunks(vector_ids)

        retrieval_results = []
        for hit in results:
            payload = hit["payload"]
            vector_id = hit["id"]
            content = content_by_vector_id.get(vector_id, payload.get("content", ""))
            source = source_by_vector_id.get(vector_id, payload.get("file_path", "workspace"))

            retrieval_results.append(RetrievalResult(
                score=hit["score"],
                content=content,
                source=source,
                metadata=payload,
                frontend_id=self.frontend_id
            ))

        logger.info("workspace_retrieval_complete",
                   workspace_id=workspace_id,
                   results=len(retrieval_results),
                   top_score=retrieval_results[0].score if retrieval_results else 0)

        return retrieval_results

    async def retrieve_workspace_hybrid(
        self,
        query: str,
        workspace_id: str,
        limit: int = 10,
        score_threshold: float = 0.5,
        use_regex: bool = False
    ) -> List[RetrievalResult]:
        """Hybrid retrieval (vector + symbol + text) for workspace content."""
        vector_results = await self.retrieve_workspace(
            query=query,
            workspace_id=workspace_id,
            limit=limit,
            score_threshold=score_threshold
        )

        symbol_results = await self._search_workspace_symbols(
            query=query,
            workspace_id=workspace_id,
            limit=limit
        )

        text_results = await self._search_workspace_text(
            query=query,
            workspace_id=workspace_id,
            limit=limit,
            use_regex=use_regex
        )

        merged = self._merge_results(vector_results, symbol_results, text_results)
        merged = self._rerank_results(merged, query)
        return merged[:limit]

    def build_context_pack(
        self,
        title: str,
        results: List[RetrievalResult],
        token_budget: int,
        item_formatter: Optional[Callable[[RetrievalResult], str]] = None
    ) -> ContextPack:
        if not results or token_budget <= 0:
            return ContextPack(text="", items=[], token_count=0, truncated=False)

        lines = [f"## {title}"]
        token_count = self._estimate_tokens(lines[0])
        items: List[RetrievalResult] = []
        truncated = False

        for result in results:
            if item_formatter:
                item_text = item_formatter(result)
            else:
                header = f"### {result.source} (score: {result.score:.2f})"
                item_text = f"{header}\n{result.content}".strip()

            if not item_text:
                continue

            item_tokens = self._estimate_tokens(item_text)
            if token_count + item_tokens > token_budget:
                truncated = True
                if not items:
                    available = max(token_budget - token_count, 0)
                    item_text = self._truncate_text_to_tokens(item_text, available)
                    if item_text:
                        lines.append(item_text)
                        token_count += self._estimate_tokens(item_text)
                        items.append(result)
                break

            lines.append(item_text)
            token_count += item_tokens
            items.append(result)

        text = "\n\n".join(lines) if items else ""
        return ContextPack(text=text, items=items, token_count=token_count, truncated=truncated)

    async def _hydrate_workspace_chunks(
        self,
        vector_ids: List[str]
    ) -> (Dict[str, str], Dict[str, str]):
        """Fetch chunk content and file paths from SQLite by vector IDs."""
        if not vector_ids:
            return {}, {}

        query = text("""
            SELECT chunks.vector_id, chunks.content, files.path
            FROM chunks
            JOIN files ON files.id = chunks.file_id
            WHERE chunks.vector_id IN :vector_ids
        """).bindparams(bindparam("vector_ids", expanding=True))

        content_by_vector_id = {}
        source_by_vector_id = {}

        try:
            async with self.db_session_maker() as session:
                result = await session.execute(query, {"vector_ids": vector_ids})
                rows = result.fetchall()

            for row in rows:
                content_by_vector_id[row[0]] = row[1]
                source_by_vector_id[row[0]] = row[2]
        except Exception as e:
            logger.error("workspace_chunk_hydration_failed", error=str(e))

        return content_by_vector_id, source_by_vector_id

    async def _search_workspace_symbols(
        self,
        query: str,
        workspace_id: str,
        limit: int
    ) -> List[RetrievalResult]:
        if not self.db_session_maker:
            return []

        terms = self._extract_query_terms(query)
        if not terms:
            return []

        results: List[RetrievalResult] = []

        async with self.db_session_maker() as session:
            for term in terms:
                pattern = f"%{term}%"
                rowset = await session.execute(text("""
                    SELECT symbols.name, symbols.kind, symbols.signature,
                           symbols.line, symbols.end_line, symbols.chunk_id,
                           files.path, chunks.content
                    FROM symbols
                    JOIN files ON files.id = symbols.file_id
                    LEFT JOIN chunks ON chunks.id = symbols.chunk_id
                    WHERE symbols.workspace_id = :workspace_id
                      AND (LOWER(symbols.name) LIKE :pattern
                           OR LOWER(symbols.qualified_name) LIKE :pattern)
                    LIMIT :limit
                """), {
                    "workspace_id": workspace_id,
                    "pattern": pattern,
                    "limit": limit
                })
                rows = rowset.fetchall()

                for row in rows:
                    name, kind, signature, line, end_line, chunk_id, file_path, content = row
                    score = self._score_symbol_match(term, name or "")
                    payload = {
                        "source_type": "symbol",
                        "symbol_name": name,
                        "symbol_kind": kind,
                        "signature": signature,
                        "line": line,
                        "end_line": end_line,
                        "file_path": file_path,
                        "chunk_id": chunk_id
                    }
                    results.append(RetrievalResult(
                        score=score,
                        content=content or signature or name or "",
                        source=file_path or "workspace",
                        metadata=payload,
                        frontend_id=self.frontend_id
                    ))

        return results

    async def _search_workspace_text(
        self,
        query: str,
        workspace_id: str,
        limit: int,
        use_regex: bool
    ) -> List[RetrievalResult]:
        if not query:
            return []

        if self._rg_path and self.workspace_path:
            rg_results = await self._search_with_ripgrep(query, limit, use_regex)
            if rg_results:
                return rg_results

        return await self._search_chunks_text(query, workspace_id, limit, use_regex)

    async def _search_with_ripgrep(
        self,
        query: str,
        limit: int,
        use_regex: bool
    ) -> List[RetrievalResult]:
        if not self._rg_path or not self.workspace_path:
            return []

        args = [self._rg_path, "--vimgrep", "--no-heading", "--max-count", str(limit)]
        if not use_regex:
            args.append("-F")
        args.append(query)
        args.append(self.workspace_path)

        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(
                args,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                check=False
            )

        result = await asyncio.to_thread(_run)
        if result.returncode not in (0, 1):
            return []

        matches = []
        for line in result.stdout.splitlines():
            parts = line.split(":", 3)
            if len(parts) < 4:
                continue
            file_path, line_no, col_no, text_line = parts
            rel_path = file_path
            if os.path.isabs(file_path):
                rel_path = os.path.relpath(file_path, self.workspace_path)
            payload = {
                "source_type": "text",
                "file_path": rel_path,
                "line": int(line_no),
                "column": int(col_no)
            }
            matches.append(RetrievalResult(
                score=0.55,
                content=text_line.strip(),
                source=rel_path,
                metadata=payload,
                frontend_id=self.frontend_id
            ))

        return matches

    async def _search_chunks_text(
        self,
        query: str,
        workspace_id: str,
        limit: int,
        use_regex: bool
    ) -> List[RetrievalResult]:
        if not self.db_session_maker:
            return []

        regex = re.compile(query, re.IGNORECASE) if use_regex else None
        pattern = f"%{query.lower()}%"

        results: List[RetrievalResult] = []
        async with self.db_session_maker() as session:
            if not use_regex:
                rowset = await session.execute(text("""
                    SELECT chunks.content, files.path, chunks.start_line
                    FROM chunks
                    JOIN files ON files.id = chunks.file_id
                    WHERE chunks.workspace_id = :workspace_id
                      AND LOWER(chunks.content) LIKE :pattern
                    LIMIT :limit
                """), {
                    "workspace_id": workspace_id,
                    "pattern": pattern,
                    "limit": limit
                })
                rows = rowset.fetchall()
            else:
                rowset = await session.execute(text("""
                    SELECT chunks.content, files.path, chunks.start_line
                    FROM chunks
                    JOIN files ON files.id = chunks.file_id
                    WHERE chunks.workspace_id = :workspace_id
                    LIMIT :limit
                """), {
                    "workspace_id": workspace_id,
                    "limit": limit * 5
                })
                rows = rowset.fetchall()

            for content, file_path, start_line in rows:
                if regex and not regex.search(content or ""):
                    continue
                snippet = self._extract_snippet(content or "", query, regex)
                payload = {
                    "source_type": "text",
                    "file_path": file_path,
                    "line": start_line
                }
                results.append(RetrievalResult(
                    score=0.5,
                    content=snippet,
                    source=file_path,
                    metadata=payload,
                    frontend_id=self.frontend_id
                ))
                if len(results) >= limit:
                    break

        return results

    def _extract_snippet(self, content: str, query: str, regex: Optional[re.Pattern]) -> str:
        if not content:
            return ""
        lines = content.splitlines()
        if regex:
            for line in lines:
                if regex.search(line):
                    return line.strip()
        lower_query = query.lower()
        for line in lines:
            if lower_query in line.lower():
                return line.strip()
        return lines[0].strip() if lines else ""

    def _extract_query_terms(self, query: str) -> List[str]:
        return [term for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", query.lower())]

    def _score_symbol_match(self, term: str, name: str) -> float:
        name_lower = name.lower()
        if name_lower == term:
            return 0.95
        if name_lower.startswith(term):
            return 0.85
        if term in name_lower:
            return 0.7
        return 0.5

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    def _lexical_score(self, query: str, text: str) -> float:
        if not query or not text:
            return 0.0
        query_terms = set(self._extract_query_terms(query))
        if not query_terms:
            return 0.0
        text_terms = set(self._extract_query_terms(text))
        if not text_terms:
            return 0.0
        overlap = query_terms.intersection(text_terms)
        return len(overlap) / len(query_terms)

    def _rerank_results(self, results: List[RetrievalResult], query: str) -> List[RetrievalResult]:
        if not results:
            return results
        for result in results:
            lexical = self._lexical_score(query, result.content)
            base = result.score
            result.metadata = result.metadata or {}
            result.metadata["lexical_score"] = lexical
            result.score = min(1.0, base + (0.2 * lexical))
        results.sort(key=lambda item: item.score, reverse=True)
        return results

    def _result_key(self, result: RetrievalResult) -> Tuple[str, Optional[int], Optional[int]]:
        file_path = result.metadata.get("file_path") if result.metadata else None
        chunk_index = result.metadata.get("chunk_index") if result.metadata else None
        line = result.metadata.get("line") if result.metadata else None
        return (file_path or result.source, chunk_index, line)

    def _merge_results(self, *result_sets: Iterable[RetrievalResult]) -> List[RetrievalResult]:
        merged: Dict[Tuple[str, Optional[int], Optional[int]], RetrievalResult] = {}
        for results in result_sets:
            for result in results:
                key = self._result_key(result)
                if key not in merged or result.score > merged[key].score:
                    merged[key] = result
        return list(merged.values())

    async def retrieve_ace_bullets(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.5
    ) -> List[RetrievalResult]:
        """
        Retrieve ACE bullets relevant to query

        Args:
            query: Search query (usually the user's task)
            limit: Maximum number of bullets
            score_threshold: Minimum similarity score

        Returns:
            List of relevant ACE bullets
        """
        ace_collection = f"loco_ace_{self.frontend_id}"

        if not query:
            logger.warning("empty_ace_query")
            return []

        logger.debug("ace_retrieval_start",
                    frontend_id=self.frontend_id,
                    query=query[:100],
                    limit=limit)

        # Embed query
        try:
            query_vector = self.embedder.embed_query(query)
        except Exception as e:
            logger.error("ace_query_embedding_failed",
                        query=query[:100],
                        error=str(e))
            return []

        # Search ACE collection
        try:
            results = self.vector_store.search(
                collection_name=ace_collection,
                query_vector=query_vector.tolist(),
                limit=limit,
                score_threshold=score_threshold
            )
        except Exception as e:
            logger.error("ace_search_failed",
                        frontend_id=self.frontend_id,
                        error=str(e))
            return []

        # Convert to RetrievalResult
        retrieval_results = []
        for hit in results:
            payload = hit["payload"]
            bullet_id = payload.get("bullet_id", payload.get("id", "unknown"))

            retrieval_results.append(RetrievalResult(
                score=hit["score"],
                content=payload.get("content", ""),
                source=f"ace_bullet_{bullet_id}",
                metadata=payload,
                frontend_id=self.frontend_id
            ))

        logger.info("ace_retrieval_complete",
                   frontend_id=self.frontend_id,
                   query=query[:50],
                   results=len(retrieval_results))

        return retrieval_results

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the indexed knowledge

        Returns:
            Dictionary with collection stats
        """
        try:
            rag_info = self.vector_store.get_collection_info(self.collection_name)

            # Try to get ACE stats too
            ace_collection = f"loco_ace_{self.frontend_id}"
            try:
                ace_info = self.vector_store.get_collection_info(ace_collection)
            except:
                ace_info = None

            return {
                "frontend_id": self.frontend_id,
                "rag_collection": self.collection_name,
                "rag_chunks": rag_info["points_count"],
                "rag_status": rag_info["status"],
                "ace_collection": ace_collection if ace_info else None,
                "ace_bullets": ace_info["points_count"] if ace_info else 0,
                "vector_size": rag_info["vector_size"]
            }
        except Exception as e:
            logger.error("get_stats_failed",
                        frontend_id=self.frontend_id,
                        error=str(e))
            return {}
