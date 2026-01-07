"""
Vector Store - Qdrant client wrapper
Handles all vector database operations
"""

from typing import List, Dict, Any, Optional
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams
)

logger = structlog.get_logger()


class VectorStore:
    """Wrapper for Qdrant vector database operations"""

    def __init__(self, host: str = "localhost", port: int = 6333):
        """
        Initialize Qdrant client

        Args:
            host: Qdrant server host
            port: Qdrant server port
        """
        self.host = host
        self.port = port

        logger.info("connecting_to_qdrant", host=host, port=port)

        try:
            self.client = QdrantClient(host=host, port=port)

            # Test connection
            collections = self.client.get_collections()
            logger.info("qdrant_connected",
                       host=host,
                       port=port,
                       collections=len(collections.collections))

        except Exception as e:
            logger.error("qdrant_connection_failed",
                        host=host,
                        port=port,
                        error=str(e))
            raise

    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: Distance = Distance.COSINE
    ) -> bool:
        """
        Create a new collection

        Args:
            collection_name: Name of the collection
            vector_size: Dimensionality of vectors
            distance: Distance metric (COSINE, EUCLID, DOT)

        Returns:
            True if created, False if already exists
        """
        try:
            # Check if collection already exists
            collections = self.client.get_collections()
            existing_names = [c.name for c in collections.collections]

            if collection_name in existing_names:
                logger.info("collection_already_exists", name=collection_name)
                return False

            # Create collection
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance
                )
            )

            logger.info("collection_created",
                       name=collection_name,
                       vector_size=vector_size,
                       distance=distance)

            return True

        except Exception as e:
            logger.error("collection_creation_failed",
                        name=collection_name,
                        error=str(e))
            raise

    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection

        Args:
            collection_name: Name of the collection

        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info("collection_deleted", name=collection_name)
            return True

        except Exception as e:
            logger.error("collection_deletion_failed",
                        name=collection_name,
                        error=str(e))
            return False

    def upsert_vectors(
        self,
        collection_name: str,
        points: List[PointStruct]
    ) -> bool:
        """
        Insert or update vectors in collection

        Args:
            collection_name: Name of the collection
            points: List of PointStruct objects with id, vector, payload

        Returns:
            True if successful
        """
        if not points:
            logger.warning("upsert_empty_points", collection=collection_name)
            return False

        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )

            logger.info("vectors_upserted",
                       collection=collection_name,
                       count=len(points))

            return True

        except Exception as e:
            logger.error("vector_upsert_failed",
                        collection=collection_name,
                        count=len(points),
                        error=str(e))
            raise

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors

        Args:
            collection_name: Name of the collection
            query_vector: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1 for cosine)
            filter_conditions: Optional metadata filters

        Returns:
            List of search results with score, id, payload
        """
        try:
            # Build filter if provided
            query_filter = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                query_filter = Filter(must=conditions)

            # Search
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter
            )

            logger.debug("vector_search_complete",
                        collection=collection_name,
                        results=len(results),
                        limit=limit)

            # Format results
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in results
            ]

        except Exception as e:
            logger.error("vector_search_failed",
                        collection=collection_name,
                        error=str(e))
            raise

    def scroll(
        self,
        collection_name: str,
        limit: int = 100,
        offset: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scroll through all vectors in collection

        Args:
            collection_name: Name of the collection
            limit: Number of points to return
            offset: Pagination offset

        Returns:
            Dictionary with 'points' list and 'next_offset' for pagination
        """
        try:
            points, next_offset = self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset
            )

            # FIXED #5: Return next_offset for pagination support
            return {
                "points": [
                    {
                        "id": point.id,
                        "vector": point.vector,
                        "payload": point.payload
                    }
                    for point in points
                ],
                "next_offset": next_offset  # Return for pagination
            }

        except Exception as e:
            logger.error("scroll_failed",
                        collection=collection_name,
                        error=str(e))
            raise

    # FIXED #18: Add delete_points method to VectorStore abstraction
    def delete_points(self, collection_name: str, point_ids: List[str]) -> bool:
        """
        Delete points from a collection

        Args:
            collection_name: Name of the collection
            point_ids: List of point IDs to delete

        Returns:
            True if successful
        """
        try:
            from qdrant_client.models import PointIdsList

            self.client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids)
            )

            logger.debug("points_deleted",
                        collection=collection_name,
                        count=len(point_ids))
            return True

        except Exception as e:
            logger.error("delete_points_failed",
                        collection=collection_name,
                        count=len(point_ids),
                        error=str(e))
            raise

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get collection information

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection stats
        """
        try:
            info = self.client.get_collection(collection_name=collection_name)

            return {
                "name": collection_name,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance,
                "points_count": info.points_count,
                "status": info.status
            }

        except Exception as e:
            logger.error("get_collection_info_failed",
                        collection=collection_name,
                        error=str(e))
            raise
