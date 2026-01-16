"""
Knowledge Indexer - Indexes module-specific operational knowledge and training data
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
    """Indexes module-specific operational knowledge (docs, training data, API references)"""

    def __init__(
        self,
        module_id: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore
    ):
        """
        Initialize knowledge indexer

        Args:
            module_id: Module identifier ("vscode", "android", "3d-gen")
            embedding_manager: Embedding manager instance
            vector_store: Vector store instance
        """
        self.module_id = module_id
        self.embedder = embedding_manager
        self.vector_store = vector_store
        self.chunker = SimpleChunker(window_size=50, overlap=10)

        logger.info("knowledge_indexer_initialized", module_id=module_id)

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
                   module_id=self.module_id,
                   docs_path=str(docs_path))

        # Ensure collection exists
        collection_name = f"loco_rag_{self.module_id}"
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )

        # Find all indexable files
        files = []
        for ext in INDEXABLE_EXTENSIONS:
            files.extend(docs_path.rglob(f"*{ext}"))

        indexed = 0
        skipped = 0
        failed = 0

        for file_path in files:
            try:
                # Check if file was already indexed
                content = self._read_file(file_path)
                if content and file_path.suffix != '.jsonl':
                    content_hash = self._calculate_content_hash(content)
                    was_cached = await self._is_file_already_indexed(
                        collection_name,
                        file_path,
                        content_hash
                    )
                    if was_cached:
                        skipped += 1
                        continue

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
                   module_id=self.module_id,
                   total_files=len(files),
                   indexed=indexed,
                   skipped=skipped,
                   failed=failed)

        return {
            "module_id": self.module_id,
            "total_files": len(files),
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed
        }

    async def index_files(
        self,
        file_paths: List[str]
    ) -> Dict[str, Any]:
        """
        Index a list of documentation files directly.

        Args:
            file_paths: List of file paths to index

        Returns:
            Statistics about indexing
        """
        files = [Path(path) for path in file_paths]
        files = [path for path in files if path.exists() and path.is_file()]

        if not files:
            logger.warning("no_docs_files_found", module_id=self.module_id)
            return {
                "module_id": self.module_id,
                "total_files": 0,
                "indexed": 0,
                "failed": 0,
                "skipped": 0
            }

        logger.info("indexing_document_files",
                   module_id=self.module_id,
                   total_files=len(files))

        collection_name = f"loco_rag_{self.module_id}"
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )

        indexed = 0
        failed = 0
        skipped = 0

        for file_path in files:
            suffix = file_path.suffix.lower()
            if suffix not in INDEXABLE_EXTENSIONS or suffix == ".jsonl":
                skipped += 1
                continue

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

        logger.info("document_files_indexing_complete",
                   module_id=self.module_id,
                   indexed=indexed,
                   failed=failed,
                   skipped=skipped)

        return {
            "module_id": self.module_id,
            "total_files": len(files),
            "indexed": indexed,
            "failed": failed,
            "skipped": skipped
        }

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content for change detection"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def _is_file_already_indexed(
        self,
        collection_name: str,
        file_path: Path,
        content_hash: str
    ) -> bool:
        """
        Check if file is already indexed with the same content hash

        Returns:
            True if file exists in vector store with same hash, False otherwise
        """
        try:
            # Query for any vectors with this file path
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            scroll_result = self.vector_store.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="full_path",
                            match=MatchValue(value=str(file_path))
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False
            )

            points = scroll_result[0]
            if not points:
                return False

            # Check if hash matches
            existing_hash = points[0].payload.get("content_hash")
            if existing_hash == content_hash:
                logger.debug("file_already_indexed_with_same_hash",
                           file=str(file_path),
                           hash=content_hash[:8])
                return True
            else:
                logger.debug("file_hash_changed",
                           file=str(file_path),
                           old_hash=existing_hash[:8] if existing_hash else "none",
                           new_hash=content_hash[:8])
                # Need to delete old vectors before re-indexing
                await self._delete_file_vectors(collection_name, file_path)
                return False

        except Exception as e:
            logger.warning("hash_check_failed",
                         file=str(file_path),
                         error=str(e))
            return False

    async def _delete_file_vectors(
        self,
        collection_name: str,
        file_path: Path
    ) -> None:
        """Delete all vectors for a specific file"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            self.vector_store.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="full_path",
                            match=MatchValue(value=str(file_path))
                        )
                    ]
                )
            )
            logger.debug("deleted_old_vectors", file=str(file_path))
        except Exception as e:
            logger.warning("vector_deletion_failed",
                         file=str(file_path),
                         error=str(e))

    async def _index_doc_file(
        self,
        file_path: Path,
        collection_name: str
    ) -> bool:
        """Index a single documentation file with hash-based caching"""
        logger.debug("indexing_doc_file", file=str(file_path))

        # Read content
        content = self._read_file(file_path)
        if content is None:
            return False

        # Skip JSONL files (handled separately)
        if file_path.suffix == '.jsonl':
            return False

        # Calculate content hash
        content_hash = self._calculate_content_hash(content)

        # Check if already indexed with same hash
        if await self._is_file_already_indexed(collection_name, file_path, content_hash):
            logger.info("doc_file_skipped_unchanged",
                       file=str(file_path),
                       hash=content_hash[:8])
            return True  # Return True because file is indexed, just not newly

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
                    "module_id": self.module_id,
                    "source": str(file_path.name),
                    "full_path": str(file_path),
                    "chunk_index": idx,
                    "content": chunk.content,
                    "content_hash": content_hash,  # Store hash for future comparisons
                    "type": "documentation"
                }
            ))

        # Upsert to Qdrant
        try:
            self.vector_store.upsert_vectors(collection_name, points)
            logger.info("doc_file_indexed",
                       file=str(file_path),
                       chunks=len(chunks),
                       hash=content_hash[:8])
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
                   module_id=self.module_id,
                   jsonl_path=str(jsonl_path))

        # Ensure collection exists
        collection_name = f"loco_rag_{self.module_id}"
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
                   module_id=self.module_id,
                   total_files=len(jsonl_files),
                   indexed=indexed,
                   failed=failed)

        return {
            "module_id": self.module_id,
            "total_files": len(jsonl_files),
            "indexed": indexed,
            "failed": failed
        }

    async def _index_jsonl_file(
        self,
        file_path: Path,
        collection_name: str
    ) -> int:
        """Index a JSONL training data file with hash-based caching"""
        logger.debug("indexing_jsonl_file", file=str(file_path))

        # Read entire file for hash calculation
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # Calculate content hash
        content_hash = self._calculate_content_hash(file_content)

        # Check if already indexed with same hash
        if await self._is_file_already_indexed(collection_name, file_path, content_hash):
            # Count existing vectors for this file
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                count_result = self.vector_store.client.count(
                    collection_name=collection_name,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="full_path",
                                match=MatchValue(value=str(file_path))
                            )
                        ]
                    )
                )
                indexed_count = count_result.count
                logger.info("jsonl_file_skipped_unchanged",
                           file=str(file_path),
                           examples=indexed_count,
                           hash=content_hash[:8])
                return indexed_count
            except Exception:
                return 0

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
                            "module_id": self.module_id,
                            "source": str(file_path.name),
                            "full_path": str(file_path),
                            "line_number": line_num,
                            "content": content,
                            "content_hash": content_hash,  # Store hash for future comparisons
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
                   items=indexed_count,
                   hash=content_hash[:8])

        return indexed_count

    async def clear_knowledge(self):
        """Clear all knowledge for this module"""
        collection_name = f"loco_rag_{self.module_id}"

        logger.info("clearing_module_knowledge", module_id=self.module_id)
        self.vector_store.delete_collection(collection_name)

        # Recreate empty collection
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )
