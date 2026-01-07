"""
Knowledge Indexer - Indexes frontend-specific operational knowledge and training data
NOT for user workspace code (that's handled on-demand)
"""

import hashlib
import os
import uuid
import json
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
import structlog
import pathspec
import chardet

from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.chunker import SimpleChunker, Chunk
from qdrant_client.models import PointStruct

logger = structlog.get_logger()


# File extensions to index for documentation
INDEXABLE_EXTENSIONS = {
    '.md', '.txt', '.rst', '.json', '.jsonl', '.yaml', '.yml'
}


class KnowledgeIndexer:
    """Indexes frontend-specific operational knowledge (docs, training data, API references)"""

    def __init__(
        self,
        frontend_id: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore
    ):
        """
        Initialize knowledge indexer

        Args:
            frontend_id: Frontend identifier ("vscode", "android", "3d-gen")
            embedding_manager: Embedding manager instance
            vector_store: Vector store instance
        """
        self.frontend_id = frontend_id
        self.embedder = embedding_manager
        self.vector_store = vector_store
        self.chunker = SimpleChunker(window_size=50, overlap=10)

        logger.info("knowledge_indexer_initialized", frontend_id=frontend_id)

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding"""
        try:
            with open(file_path, 'rb') as f:
                raw = f.read(10000)
                result = chardet.detect(raw)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Read file content safely"""
        try:
            encoding = self._detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error("file_read_failed", file=str(file_path), error=str(e))
            return None

    async def index_documentation(
        self,
        docs_path: str
    ) -> Dict[str, Any]:
        """
        Index documentation files (markdown, text, etc.)

        Args:
            docs_path: Path to documentation directory

        Returns:
            Statistics about indexing
        """
        docs_path = Path(docs_path)
        if not docs_path.exists():
            logger.error("docs_path_not_found", path=str(docs_path))
            return {"error": "Path not found"}

        logger.info("indexing_documentation",
                   frontend_id=self.frontend_id,
                   docs_path=str(docs_path))

        # Ensure collection exists
        collection_name = f"loco_rag_{self.frontend_id}"
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )

        # Find all indexable files
        files = []
        for ext in INDEXABLE_EXTENSIONS:
            files.extend(docs_path.rglob(f"*{ext}"))

        indexed = 0
        failed = 0

        for file_path in files:
            try:
                success = await self._index_doc_file(
                    file_path,
                    collection_name
                )
                if success:
                    indexed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error("file_indexing_failed",
                           file=str(file_path),
                           error=str(e))
                failed += 1

        logger.info("documentation_indexing_complete",
                   frontend_id=self.frontend_id,
                   total_files=len(files),
                   indexed=indexed,
                   failed=failed)

        return {
            "frontend_id": self.frontend_id,
            "total_files": len(files),
            "indexed": indexed,
            "failed": failed
        }

    async def _index_doc_file(
        self,
        file_path: Path,
        collection_name: str
    ) -> bool:
        """Index a single documentation file"""
        logger.debug("indexing_doc_file", file=str(file_path))

        # Read content
        content = self._read_file(file_path)
        if content is None:
            return False

        # Skip JSONL files (handled separately)
        if file_path.suffix == '.jsonl':
            return False

        # Chunk content
        chunks = self.chunker.chunk_file(
            content=content,
            language=None,
            file_path=str(file_path)
        )

        if not chunks:
            return False

        # Embed chunks
        chunk_contents = [chunk.content for chunk in chunks]
        try:
            embeddings = self.embedder.embed(chunk_contents)
        except Exception as e:
            logger.error("embedding_failed", file=str(file_path), error=str(e))
            return False

        # Create points
        points = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())

            points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "frontend_id": self.frontend_id,
                    "source": str(file_path.name),
                    "full_path": str(file_path),
                    "chunk_index": idx,
                    "content": chunk.content,  # Store content in payload for operational knowledge
                    "type": "documentation"
                }
            ))

        # Upsert to Qdrant
        try:
            self.vector_store.upsert_vectors(collection_name, points)
            logger.info("doc_file_indexed",
                       file=str(file_path),
                       chunks=len(chunks))
            return True
        except Exception as e:
            logger.error("vector_storage_failed",
                        file=str(file_path),
                        error=str(e))
            return False

    async def index_training_data(
        self,
        jsonl_path: str
    ) -> Dict[str, Any]:
        """
        Index training data from JSONL files (e.g., Unity 3D-gen examples)

        Args:
            jsonl_path: Path to JSONL file or directory of JSONL files

        Returns:
            Statistics about indexing
        """
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            logger.error("jsonl_path_not_found", path=str(jsonl_path))
            return {"error": "Path not found"}

        logger.info("indexing_training_data",
                   frontend_id=self.frontend_id,
                   jsonl_path=str(jsonl_path))

        # Ensure collection exists
        collection_name = f"loco_rag_{self.frontend_id}"
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )

        # Find all JSONL files
        if jsonl_path.is_file():
            jsonl_files = [jsonl_path]
        else:
            jsonl_files = list(jsonl_path.rglob("*.jsonl"))

        indexed = 0
        failed = 0

        for file_path in jsonl_files:
            try:
                count = await self._index_jsonl_file(
                    file_path,
                    collection_name
                )
                indexed += count
            except Exception as e:
                logger.error("jsonl_indexing_failed",
                           file=str(file_path),
                           error=str(e))
                failed += 1

        logger.info("training_data_indexing_complete",
                   frontend_id=self.frontend_id,
                   total_files=len(jsonl_files),
                   indexed=indexed,
                   failed=failed)

        return {
            "frontend_id": self.frontend_id,
            "total_files": len(jsonl_files),
            "indexed": indexed,
            "failed": failed
        }

    async def _index_jsonl_file(
        self,
        file_path: Path,
        collection_name: str
    ) -> int:
        """Index a JSONL training data file"""
        logger.debug("indexing_jsonl_file", file=str(file_path))

        indexed_count = 0

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    item = json.loads(line)

                    # Extract prompt/completion (supports legacy and 3D-gen formats)
                    instruction = item.get('instruction', '')
                    input_text = item.get('input', '')
                    prompt = item.get('prompt', '') or instruction
                    completion = item.get('completion', '') or item.get('output', '')

                    if not prompt and not completion:
                        continue

                    # Create searchable content
                    if instruction or input_text:
                        content_parts = [
                            f"Instruction: {instruction}",
                            f"Input: {input_text}",
                            f"Output: {completion}"
                        ]
                        content = "\n".join([part for part in content_parts if part.strip()])
                    else:
                        content = f"Prompt: {prompt}\n\nCompletion: {completion}"

                    # Embed
                    embedding = self.embedder.embed_single(content)

                    # Create point
                    point_id = str(uuid.uuid4())
                    point = PointStruct(
                        id=point_id,
                        vector=embedding.tolist(),
                        payload={
                            "frontend_id": self.frontend_id,
                            "source": str(file_path.name),
                            "full_path": str(file_path),
                            "line_number": line_num,
                            "content": content,
                            "prompt": prompt,
                            "completion": completion,
                            "instruction": instruction,
                            "input": input_text,
                            "output": item.get('output', ''),
                            "category": item.get('category'),
                            "complexity": item.get('complexity'),
                            "asset_type": item.get('asset_type'),
                            "metadata": item.get('metadata', {}),
                            "type": "training_example"
                        }
                    )

                    # Upsert
                    self.vector_store.upsert_vectors(collection_name, [point])
                    indexed_count += 1

                except json.JSONDecodeError as e:
                    logger.error("jsonl_parse_error",
                               file=str(file_path),
                               line=line_num,
                               error=str(e))
                    continue
                except Exception as e:
                    logger.error("jsonl_item_failed",
                               file=str(file_path),
                               line=line_num,
                               error=str(e))
                    continue

        logger.info("jsonl_file_indexed",
                   file=str(file_path),
                   items=indexed_count)

        return indexed_count

    async def clear_knowledge(self):
        """Clear all knowledge for this frontend"""
        collection_name = f"loco_rag_{self.frontend_id}"

        logger.info("clearing_frontend_knowledge", frontend_id=self.frontend_id)
        self.vector_store.delete_collection(collection_name)

        # Recreate empty collection
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )
