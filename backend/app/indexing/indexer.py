"""
File Indexer - Discovers and indexes workspace files
"""

import hashlib
import os
import uuid
import numpy as np
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
import structlog
import pathspec
import chardet

from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.chunker import SimpleChunker, Chunk
from qdrant_client.models import PointStruct

logger = structlog.get_logger()


# File extensions to index
INDEXABLE_EXTENSIONS = {
    # Code
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
    # Markup/Config
    '.html', '.css', '.scss', '.json', '.yaml', '.yml', '.toml', '.xml',
    # Docs
    '.md', '.txt', '.rst',
}

# Max file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class FileIndexer:
    """Indexes files in a workspace"""

    def __init__(
        self,
        workspace_id: str,
        domain_id: str,  # NEW: Domain for collection scoping
        workspace_path: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore,
        db_session  # SQLAlchemy async session
    ):
        """
        Initialize file indexer

        Args:
            workspace_id: Unique workspace identifier
            domain_id: Domain identifier for collection scoping (e.g., "coding", "unity")
            workspace_path: Absolute path to workspace root
            embedding_manager: Embedding manager instance
            vector_store: Vector store instance
            db_session: Database session for metadata storage
        """
        self.workspace_id = workspace_id
        self.domain_id = domain_id
        self.workspace_path = Path(workspace_path)
        self.embedder = embedding_manager
        self.vector_store = vector_store
        self.db = db_session

        self.chunker = SimpleChunker(window_size=50, overlap=10)

        # Load .gitignore patterns
        self.gitignore_spec = self._load_gitignore()

        logger.info("indexer_initialized",
                   workspace_id=workspace_id,
                   workspace_path=str(workspace_path))

    def _load_gitignore(self) -> Optional[pathspec.PathSpec]:
        """Load .gitignore patterns"""
        gitignore_path = self.workspace_path / ".gitignore"

        if not gitignore_path.exists():
            logger.debug("no_gitignore_found", workspace=str(self.workspace_path))
            return None

        try:
            with open(gitignore_path, 'r') as f:
                patterns = f.read().splitlines()

            spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
            logger.info("gitignore_loaded",
                       patterns=len(patterns),
                       workspace=str(self.workspace_path))

            return spec

        except Exception as e:
            logger.error("gitignore_load_failed",
                        workspace=str(self.workspace_path),
                        error=str(e))
            return None

    def discover_files(self) -> List[Path]:
        """
        Discover all indexable files in workspace

        Returns:
            List of file paths
        """
        files = []

        for root, dirs, filenames in os.walk(self.workspace_path):
            root_path = Path(root)

            # Relative path from workspace root
            try:
                rel_root = root_path.relative_to(self.workspace_path)
            except ValueError:
                continue

            # Check gitignore for directory
            if self.gitignore_spec:
                rel_root_str = str(rel_root)
                if rel_root_str != '.' and self.gitignore_spec.match_file(rel_root_str + '/'):
                    dirs.clear()  # Don't descend into ignored dirs
                    continue

            # Process files
            for filename in filenames:
                file_path = root_path / filename

                # Check extension
                if file_path.suffix not in INDEXABLE_EXTENSIONS:
                    continue

                # Relative path
                try:
                    rel_path = file_path.relative_to(self.workspace_path)
                except ValueError:
                    continue

                # Check gitignore
                if self.gitignore_spec and self.gitignore_spec.match_file(str(rel_path)):
                    logger.debug("file_ignored", file=str(rel_path))
                    continue

                # Check size
                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        logger.warning("file_too_large",
                                     file=str(rel_path),
                                     size=file_path.stat().st_size)
                        continue
                except OSError:
                    continue

                files.append(rel_path)

        logger.info("files_discovered",
                   workspace_id=self.workspace_id,
                   count=len(files))

        return files

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding"""
        try:
            with open(file_path, 'rb') as f:
                raw = f.read(10000)  # Read first 10KB
                result = chardet.detect(raw)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'

    def _read_file(self, file_path: Path) -> Optional[str]:
        """
        Read file content safely

        Args:
            file_path: Absolute path to file

        Returns:
            File content or None if failed
        """
        try:
            encoding = self._detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error("file_read_failed",
                        file=str(file_path),
                        error=str(e))
            return None

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect programming language from extension"""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.xml': 'xml',
            '.md': 'markdown',
            '.txt': 'text',
            '.rst': 'restructuredtext',
        }

        return ext_to_lang.get(file_path.suffix)

    async def index_file(self, rel_path: Path) -> bool:
        """
        Index a single file

        Args:
            rel_path: Path relative to workspace root

        Returns:
            True if indexed successfully
        """
        abs_path = self.workspace_path / rel_path
        rel_path_str = str(rel_path)

        logger.debug("indexing_file", file=rel_path_str)

        # Read content
        content = self._read_file(abs_path)
        if content is None:
            return False

        # Compute hash
        content_hash = self._compute_hash(content)

        # Check if file changed (TODO: implement in Phase 2)
        # For now, always index

        # Detect language
        language = self._detect_language(abs_path)

        # Chunk file
        chunks = self.chunker.chunk_file(
            content=content,
            language=language,
            file_path=rel_path_str
        )

        if not chunks:
            logger.warning("no_chunks_created", file=rel_path_str)
            return False

        # Embed chunks
        # FIXED #14: Batch embeddings to avoid memory pressure on large files
        chunk_contents = [chunk.content for chunk in chunks]
        embeddings = []

        try:
            BATCH_SIZE = 64
            for i in range(0, len(chunk_contents), BATCH_SIZE):
                batch = chunk_contents[i:i+BATCH_SIZE]
                batch_embeddings = self.embedder.embed(batch)
                embeddings.extend(batch_embeddings)

            embeddings = np.array(embeddings)
        except Exception as e:
            logger.error("embedding_failed",
                        file=rel_path_str,
                        error=str(e))
            return False

        # Store in database (simplified - full implementation in Phase 2)
        # For now, just log
        logger.debug("file_metadata_stored",
                    file=rel_path_str,
                    hash=content_hash,
                    language=language,
                    size=len(content),
                    chunks=len(chunks))

        # Store vectors in Qdrant
        # FIXED #1: Use domain-scoped collection instead of workspace
        collection_name = f"loco_rag_{self.domain_id}"

        # Create points
        points = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # FIXED #3: Use UUID for point IDs instead of string concatenation
            point_id = str(uuid.uuid4())

            # FIXED #4: Store minimal payload, retrieve content from SQLite
            points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "workspace_id": self.workspace_id,
                    "domain_id": self.domain_id,
                    "file_path": rel_path_str,
                    "chunk_index": idx,
                    "chunk_type": chunk.chunk_type,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": language,
                    # NOTE: Content removed from payload (SQLite is source of truth)
                    # Retriever will hydrate from database using file_path + chunk_index
                }
            ))

        # Upsert to Qdrant
        try:
            self.vector_store.upsert_vectors(collection_name, points)
            logger.info("file_indexed",
                       file=rel_path_str,
                       chunks=len(chunks))
            return True

        except Exception as e:
            logger.error("vector_storage_failed",
                        file=rel_path_str,
                        error=str(e))
            return False

    async def index_workspace(self) -> Dict[str, Any]:
        """
        Index entire workspace

        Returns:
            Statistics about indexing
        """
        logger.info("workspace_indexing_start",
                   workspace_id=self.workspace_id,
                   domain_id=self.domain_id)

        # Ensure collection exists
        # FIXED #1: Use domain-scoped collection
        collection_name = f"loco_rag_{self.domain_id}"
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )

        # Discover files
        files = self.discover_files()

        # Index each file
        indexed = 0
        failed = 0

        for rel_path in files:
            success = await self.index_file(rel_path)
            if success:
                indexed += 1
            else:
                failed += 1

        logger.info("workspace_indexing_complete",
                   workspace_id=self.workspace_id,
                   total_files=len(files),
                   indexed=indexed,
                   failed=failed)

        return {
            "workspace_id": self.workspace_id,
            "total_files": len(files),
            "indexed": indexed,
            "failed": failed
        }
