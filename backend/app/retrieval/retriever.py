"""
Retriever - Searches indexed operational knowledge for relevant context
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

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


class Retriever:
    """Retrieves relevant context from indexed operational knowledge"""

    def __init__(
        self,
        frontend_id: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore
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
        self.collection_name = f"loco_rag_{frontend_id}"

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

        logger.info("retrieval_complete",
                   frontend_id=self.frontend_id,
                   query=query[:50],
                   results=len(retrieval_results),
                   top_score=retrieval_results[0].score if retrieval_results else 0)

        return retrieval_results

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
