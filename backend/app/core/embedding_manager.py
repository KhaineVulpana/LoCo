"""
Embedding Manager - Handles text-to-vector embeddings
Uses sentence-transformers for local embedding generation
"""

import numpy as np
from typing import List, Union
import structlog
from sentence_transformers import SentenceTransformer
from pathlib import Path

logger = structlog.get_logger()


class EmbeddingManager:
    """Manages embedding model and vector generation"""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_folder: str = None
    ):
        """
        Initialize embedding manager

        Args:
            model_name: HuggingFace model name
            cache_folder: Where to cache the model (default: ~/.cache/sentence_transformers)
        """
        self.model_name = model_name
        self.cache_folder = cache_folder or str(Path.home() / ".cache" / "sentence_transformers")

        logger.info("loading_embedding_model", model=model_name)

        try:
            self.model = SentenceTransformer(
                model_name,
                cache_folder=self.cache_folder
            )
            self.dimensions = self.model.get_sentence_embedding_dimension()

            logger.info("embedding_model_loaded",
                       model=model_name,
                       dimensions=self.dimensions)

        except Exception as e:
            logger.error("embedding_model_load_failed",
                        model=model_name,
                        error=str(e))
            raise

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Embed multiple texts into vectors

        Args:
            texts: List of text strings to embed

        Returns:
            numpy array of shape (len(texts), dimensions)
        """
        # FIXED #12: Return correct shape for empty input
        if not texts:
            return np.empty((0, self.dimensions))

        try:
            # Batch encode for efficiency
            embeddings = self.model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True  # L2 normalization for cosine similarity
            )

            logger.debug("embedded_batch",
                        count=len(texts),
                        shape=embeddings.shape)

            return embeddings

        except Exception as e:
            logger.error("embedding_failed",
                        text_count=len(texts),
                        error=str(e))
            raise

    def embed_single(self, text: str) -> np.ndarray:
        """
        Embed a single text into a vector

        Args:
            text: Text string to embed

        Returns:
            numpy array of shape (dimensions,)
        """
        if not text:
            # Return zero vector for empty text
            return np.zeros(self.dimensions)

        embeddings = self.embed([text])
        return embeddings[0]

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a search query (alias for embed_single for clarity)

        Args:
            query: Search query text

        Returns:
            numpy array of shape (dimensions,)
        """
        return self.embed_single(query)

    def get_dimensions(self) -> int:
        """Get the dimensionality of embeddings"""
        return self.dimensions

    def get_model_name(self) -> str:
        """Get the name of the loaded model"""
        return self.model_name
