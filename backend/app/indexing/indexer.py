"""
File Indexer - Discovers and indexes workspace files
"""

import hashlib
import os
import uuid
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
import structlog
import pathspec
import chardet
from sqlalchemy import text, bindparam

from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.chunker import ASTChunker, Chunk, ChunkResult, SymbolInfo
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
        frontend_id: str,  # Frontend for collection scoping
        workspace_path: str,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStore,
        db_session  # SQLAlchemy async session
    ):
        """
        Initialize file indexer

        Args:
            workspace_id: Unique workspace identifier
            frontend_id: Frontend identifier for collection scoping (e.g., "vscode", "3d-gen")
            workspace_path: Absolute path to workspace root
            embedding_manager: Embedding manager instance
            vector_store: Vector store instance
            db_session: Database session for metadata storage
        """
        self.workspace_id = workspace_id
        self.frontend_id = frontend_id
        self.workspace_path = Path(workspace_path)
        self.embedder = embedding_manager
        self.vector_store = vector_store
        self.db = db_session

        self.chunker = ASTChunker()

        # Load .gitignore patterns
        self.gitignore_spec = self._load_gitignore()

        logger.info("indexer_initialized",
                   workspace_id=workspace_id,
                   frontend_id=frontend_id,
                   workspace_path=str(workspace_path))

    def _get_collection_name(self) -> str:
        """Get workspace-scoped collection name."""
        return f"loco_rag_workspace_{self.workspace_id}"

    async def _update_workspace_index_stats(self, **fields) -> None:
        """Update workspace indexing metadata."""
        if not self.db or not fields:
            return

        allowed_fields = {
            "index_status",
            "index_progress",
            "total_files",
            "indexed_files",
            "total_chunks",
            "last_indexed_at"
        }
        update_fields = {k: v for k, v in fields.items() if k in allowed_fields}
        if not update_fields:
            return

        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{key} = :{key}" for key in update_fields.keys())
        query = text(f"UPDATE workspaces SET {set_clause} WHERE id = :workspace_id")

        update_fields["workspace_id"] = self.workspace_id
        await self.db.execute(query, update_fields)
        await self.db.commit()

    async def _upsert_file_record(
        self,
        rel_path_str: str,
        content_hash: str,
        language: Optional[str],
        size_bytes: int,
        line_count: int
    ) -> Optional[int]:
        """Insert or update a file record and return its ID."""
        if not self.db:
            return None

        now = datetime.now(timezone.utc).isoformat()
        select_query = text("""
            SELECT id FROM files
            WHERE workspace_id = :workspace_id AND path = :path
        """)
        result = await self.db.execute(select_query, {
            "workspace_id": self.workspace_id,
            "path": rel_path_str
        })
        row = result.fetchone()

        if row:
            file_id = row[0]
            update_query = text("""
                UPDATE files
                SET content_hash = :content_hash,
                    language = :language,
                    size_bytes = :size_bytes,
                    line_count = :line_count,
                    index_status = :index_status,
                    parse_error = NULL,
                    updated_at = :updated_at
                WHERE id = :file_id
            """)
            await self.db.execute(update_query, {
                "content_hash": content_hash,
                "language": language,
                "size_bytes": size_bytes,
                "line_count": line_count,
                "index_status": "indexing",
                "updated_at": now,
                "file_id": file_id
            })
        else:
            insert_query = text("""
                INSERT INTO files (
                    workspace_id, path, content_hash, language, size_bytes,
                    line_count, index_status, created_at, updated_at
                )
                VALUES (
                    :workspace_id, :path, :content_hash, :language, :size_bytes,
                    :line_count, :index_status, :created_at, :updated_at
                )
            """)
            await self.db.execute(insert_query, {
                "workspace_id": self.workspace_id,
                "path": rel_path_str,
                "content_hash": content_hash,
                "language": language,
                "size_bytes": size_bytes,
                "line_count": line_count,
                "index_status": "indexing",
                "created_at": now,
                "updated_at": now
            })
            result = await self.db.execute(select_query, {
                "workspace_id": self.workspace_id,
                "path": rel_path_str
            })
            row = result.fetchone()
            file_id = row[0] if row else None

        await self.db.commit()
        return file_id

    async def _set_file_index_status(self, file_id: int, status: str, error: Optional[str] = None) -> None:
        """Update file index status and optional error."""
        if not self.db:
            return

        now = datetime.now(timezone.utc).isoformat()
        query = text("""
            UPDATE files
            SET index_status = :index_status,
                parse_error = :parse_error,
                updated_at = :updated_at
            WHERE id = :file_id
        """)
        await self.db.execute(query, {
            "index_status": status,
            "parse_error": error,
            "updated_at": now,
            "file_id": file_id
        })
        await self.db.commit()

    async def _delete_chunks_for_file(self, file_id: int) -> None:
        """Delete existing chunks for a file."""
        if not self.db:
            return

        delete_query = text("DELETE FROM chunks WHERE file_id = :file_id")
        await self.db.execute(delete_query, {"file_id": file_id})
        await self.db.commit()

    async def _insert_chunks(
        self,
        file_id: int,
        chunks: List[Chunk],
        vector_ids: List[str],
        embedding_model: str
    ) -> None:
        """Insert chunk records for a file."""
        if not self.db:
            return

        now = datetime.now(timezone.utc).isoformat()
        insert_query = text("""
            INSERT INTO chunks (
                file_id, workspace_id, start_line, end_line,
                start_offset, end_offset, content, content_hash,
                tokens_estimated, chunk_type, parent_chunk_id,
                vector_id, embedding_model, created_at, updated_at
            )
            VALUES (
                :file_id, :workspace_id, :start_line, :end_line,
                :start_offset, :end_offset, :content, :content_hash,
                :tokens_estimated, :chunk_type, :parent_chunk_id,
                :vector_id, :embedding_model, :created_at, :updated_at
            )
        """)

        for chunk, vector_id in zip(chunks, vector_ids):
            await self.db.execute(insert_query, {
                "file_id": file_id,
                "workspace_id": self.workspace_id,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "start_offset": chunk.start_offset,
                "end_offset": chunk.end_offset,
                "content": chunk.content,
                "content_hash": self._compute_hash(chunk.content),
                "tokens_estimated": None,
                "chunk_type": chunk.chunk_type,
                "parent_chunk_id": None,
                "vector_id": vector_id,
                "embedding_model": embedding_model,
                "created_at": now,
                "updated_at": now
            })

        await self.db.commit()

    async def _delete_symbols_for_file(self, file_id: int) -> None:
        """Delete existing symbols for a file."""
        if not self.db:
            return

        delete_query = text("DELETE FROM symbols WHERE file_id = :file_id")
        await self.db.execute(delete_query, {"file_id": file_id})
        await self.db.commit()

    async def _get_chunk_id_map(self, file_id: int) -> Dict[str, int]:
        """Map vector_id to chunk_id for a file."""
        if not self.db:
            return {}

        query = text("""
            SELECT id, vector_id FROM chunks
            WHERE file_id = :file_id
        """)
        result = await self.db.execute(query, {"file_id": file_id})
        rows = result.fetchall()
        return {row[1]: row[0] for row in rows if row[1]}

    async def _insert_symbols(
        self,
        file_id: int,
        symbols: List[SymbolInfo],
        vector_ids: List[str]
    ) -> None:
        """Insert symbol records for a file."""
        if not self.db or not symbols:
            return

        await self._delete_symbols_for_file(file_id)

        chunk_id_map = await self._get_chunk_id_map(file_id)
        symbol_id_map: Dict[str, int] = {}

        insert_query = text("""
            INSERT INTO symbols (
                file_id, workspace_id, chunk_id, name, qualified_name,
                kind, signature, line, column, end_line, end_column,
                parent_symbol_id, is_exported, is_private, created_at, updated_at
            )
            VALUES (
                :file_id, :workspace_id, :chunk_id, :name, :qualified_name,
                :kind, :signature, :line, :column, :end_line, :end_column,
                :parent_symbol_id, :is_exported, :is_private, :created_at, :updated_at
            )
        """)

        now = datetime.now(timezone.utc).isoformat()

        for symbol in symbols:
            qualified_name = symbol.name
            if symbol.parent_qualname:
                qualified_name = f"{symbol.parent_qualname}.{symbol.name}"

            parent_id = symbol_id_map.get(symbol.parent_qualname) if symbol.parent_qualname else None

            chunk_id = None
            if symbol.chunk_index is not None and symbol.chunk_index < len(vector_ids):
                vector_id = vector_ids[symbol.chunk_index]
                chunk_id = chunk_id_map.get(vector_id)

            await self.db.execute(insert_query, {
                "file_id": file_id,
                "workspace_id": self.workspace_id,
                "chunk_id": chunk_id,
                "name": symbol.name,
                "qualified_name": qualified_name,
                "kind": symbol.kind,
                "signature": symbol.signature,
                "line": symbol.start_line,
                "column": symbol.start_column,
                "end_line": symbol.end_line,
                "end_column": symbol.end_column,
                "parent_symbol_id": parent_id,
                "is_exported": 0,
                "is_private": 0,
                "created_at": now,
                "updated_at": now
            })

            result = await self.db.execute(text("SELECT last_insert_rowid()"))
            row = result.fetchone()
            if row:
                symbol_id_map[qualified_name] = row[0]

        await self.db.commit()

    async def _get_file_record(self, rel_path_str: str) -> Optional[Dict[str, Any]]:
        """Fetch file metadata for change detection."""
        if not self.db:
            return None

        query = text("""
            SELECT id, content_hash, index_status
            FROM files
            WHERE workspace_id = :workspace_id AND path = :path
        """)
        result = await self.db.execute(query, {
            "workspace_id": self.workspace_id,
            "path": rel_path_str
        })
        row = result.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "content_hash": row[1],
            "index_status": row[2]
        }

    async def _get_chunk_count(self, file_id: int) -> int:
        if not self.db:
            return 0

        result = await self.db.execute(text("""
            SELECT COUNT(*) FROM chunks WHERE file_id = :file_id
        """), {"file_id": file_id})
        row = result.fetchone()
        return int(row[0]) if row else 0

    async def _get_vector_ids_for_file(self, file_id: int) -> List[str]:
        if not self.db:
            return []

        result = await self.db.execute(text("""
            SELECT vector_id FROM chunks WHERE file_id = :file_id AND vector_id IS NOT NULL
        """), {"file_id": file_id})
        rows = result.fetchall()
        return [row[0] for row in rows if row and row[0]]

    async def _delete_vectors_for_file(self, file_id: int) -> None:
        vector_ids = await self._get_vector_ids_for_file(file_id)
        if vector_ids:
            self.vector_store.delete_points(
                collection_name=self._get_collection_name(),
                point_ids=vector_ids
            )

    def _normalize_embedding(self, embedding: Any) -> np.ndarray:
        if isinstance(embedding, np.ndarray):
            return embedding.astype(np.float32)
        if hasattr(embedding, "tolist"):
            return np.asarray(embedding.tolist(), dtype=np.float32)
        return np.asarray(embedding, dtype=np.float32)

    def _embedding_cache_key(self, text: str) -> str:
        model_name = self.embedder.get_model_name()
        payload = f"{model_name}:{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _fetch_cached_embeddings(
        self,
        cache_keys: List[str]
    ) -> Dict[str, np.ndarray]:
        if not self.db or not cache_keys:
            return {}

        query = text("""
            SELECT content_hash, embedding_blob, dimensions
            FROM embedding_cache
            WHERE content_hash IN :hashes
        """).bindparams(bindparam("hashes", expanding=True))

        result = await self.db.execute(query, {"hashes": cache_keys})
        rows = result.fetchall()

        cached: Dict[str, np.ndarray] = {}
        for row in rows:
            content_hash = row[0]
            blob = row[1]
            dimensions = row[2]
            vector = np.frombuffer(blob, dtype=np.float32)
            if dimensions and vector.size == dimensions:
                cached[content_hash] = vector

        if cached:
            now = datetime.now(timezone.utc).isoformat()
            update_query = text("""
                UPDATE embedding_cache
                SET last_used_at = :last_used_at,
                    use_count = use_count + 1
                WHERE content_hash IN :hashes
            """).bindparams(bindparam("hashes", expanding=True))
            await self.db.execute(update_query, {
                "last_used_at": now,
                "hashes": list(cached.keys())
            })
            await self.db.commit()

        return cached

    async def _store_embeddings(
        self,
        cache_keys: List[str],
        embeddings: List[Any]
    ) -> None:
        if not self.db or not cache_keys:
            return

        now = datetime.now(timezone.utc).isoformat()
        model_name = self.embedder.get_model_name()

        insert_query = text("""
            INSERT OR REPLACE INTO embedding_cache (
                content_hash, embedding_blob, embedding_model, dimensions,
                created_at, last_used_at, use_count
            )
            VALUES (
                :content_hash, :embedding_blob, :embedding_model, :dimensions,
                :created_at, :last_used_at, :use_count
            )
        """)

        for key, embedding in zip(cache_keys, embeddings):
            vector = self._normalize_embedding(embedding)
            await self.db.execute(insert_query, {
                "content_hash": key,
                "embedding_blob": vector.tobytes(),
                "embedding_model": model_name,
                "dimensions": vector.size,
                "created_at": now,
                "last_used_at": now,
                "use_count": 1
            })

        await self.db.commit()

    async def _embed_with_cache(self, texts: List[str]) -> List[np.ndarray]:
        if not texts:
            return []

        if not self.db:
            raw_embeddings = self.embedder.embed(texts)
            return [self._normalize_embedding(embedding) for embedding in raw_embeddings]

        cache_keys = [self._embedding_cache_key(text) for text in texts]
        cached = await self._fetch_cached_embeddings(cache_keys)

        embeddings: List[Optional[np.ndarray]] = [None] * len(texts)
        to_embed = []
        to_embed_keys = []
        to_embed_indices = []

        for idx, key in enumerate(cache_keys):
            if key in cached:
                embeddings[idx] = cached[key]
            else:
                to_embed.append(texts[idx])
                to_embed_keys.append(key)
                to_embed_indices.append(idx)

        if to_embed:
            batch_embeddings: List[np.ndarray] = []
            batch_size = 64
            for i in range(0, len(to_embed), batch_size):
                batch = to_embed[i:i + batch_size]
                raw_embeddings = self.embedder.embed(batch)
                batch_embeddings.extend(
                    self._normalize_embedding(embedding) for embedding in raw_embeddings
                )

            for idx, embedding in zip(to_embed_indices, batch_embeddings):
                embeddings[idx] = embedding

            await self._store_embeddings(to_embed_keys, batch_embeddings)

        if any(embedding is None for embedding in embeddings):
            raise ValueError("embedding_cache_incomplete")

        return [embedding for embedding in embeddings if embedding is not None]

    async def _recalculate_workspace_stats(self) -> None:
        if not self.db:
            return

        result = await self.db.execute(text("""
            SELECT COUNT(*) AS total_files,
                   SUM(CASE WHEN index_status = 'indexed' THEN 1 ELSE 0 END) AS indexed_files
            FROM files
            WHERE workspace_id = :workspace_id
        """), {"workspace_id": self.workspace_id})
        row = result.fetchone()
        total_files = int(row[0] or 0)
        indexed_files = int(row[1] or 0)

        chunk_result = await self.db.execute(text("""
            SELECT COUNT(*) FROM chunks WHERE workspace_id = :workspace_id
        """), {"workspace_id": self.workspace_id})
        chunk_row = chunk_result.fetchone()
        total_chunks = int(chunk_row[0] or 0)

        progress = (indexed_files / total_files) if total_files else 1.0

        await self._update_workspace_index_stats(
            total_files=total_files,
            indexed_files=indexed_files,
            total_chunks=total_chunks,
            index_progress=progress
        )

    async def delete_file(self, rel_path: Path) -> bool:
        """Remove a file from index and vector store."""
        return await self._delete_file(rel_path, recalculate=True)

    async def _delete_file(self, rel_path: Path, recalculate: bool = True) -> bool:
        if not self.db:
            return False

        rel_path_str = str(rel_path)
        record = await self._get_file_record(rel_path_str)
        if not record:
            return False

        file_id = record["id"]
        await self._delete_vectors_for_file(file_id)
        await self._delete_chunks_for_file(file_id)
        await self._delete_symbols_for_file(file_id)

        await self.db.execute(text("""
            DELETE FROM files WHERE id = :file_id
        """), {"file_id": file_id})
        await self.db.commit()

        if recalculate:
            await self._recalculate_workspace_stats()
        return True

    async def _get_existing_file_paths(self) -> List[str]:
        if not self.db:
            return []

        result = await self.db.execute(text("""
            SELECT path FROM files WHERE workspace_id = :workspace_id
        """), {"workspace_id": self.workspace_id})
        rows = result.fetchall()
        return [row[0] for row in rows if row and row[0]]

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

                # Relative path
                try:
                    rel_path = file_path.relative_to(self.workspace_path)
                except ValueError:
                    continue

                if not self._is_file_indexable(file_path, rel_path):
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

    def _is_path_allowed(self, rel_path: Path) -> bool:
        if rel_path.suffix.lower() not in INDEXABLE_EXTENSIONS:
            return False

        if self.gitignore_spec and self.gitignore_spec.match_file(str(rel_path)):
            logger.debug("file_ignored", file=str(rel_path))
            return False

        return True

    def _is_file_indexable(self, abs_path: Path, rel_path: Path) -> bool:
        if not self._is_path_allowed(rel_path):
            return False

        try:
            if abs_path.stat().st_size > MAX_FILE_SIZE:
                logger.warning("file_too_large",
                               file=str(rel_path),
                               size=abs_path.stat().st_size)
                return False
        except OSError:
            return False

        return True

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

        return ext_to_lang.get(file_path.suffix.lower())

    async def index_file(self, rel_path: Path) -> Dict[str, Any]:
        """
        Index a single file

        Args:
            rel_path: Path relative to workspace root

        Returns:
            Dictionary with success status and chunk count
        """
        abs_path = self.workspace_path / rel_path
        rel_path_str = str(rel_path)

        logger.debug("indexing_file", file=rel_path_str)

        # Read content
        content = self._read_file(abs_path)
        if content is None:
            return {"success": False, "chunks": 0}

        # Compute hash
        content_hash = self._compute_hash(content)
        try:
            size_bytes = abs_path.stat().st_size
        except OSError:
            size_bytes = len(content.encode("utf-8"))
        line_count = len(content.splitlines())

        existing_record = await self._get_file_record(rel_path_str)
        if existing_record:
            if (
                existing_record.get("content_hash") == content_hash
                and existing_record.get("index_status") == "indexed"
            ):
                chunk_count = await self._get_chunk_count(existing_record["id"])
                return {"success": True, "chunks": chunk_count, "skipped": True}

        if not self._is_file_indexable(abs_path, rel_path):
            return {"success": False, "chunks": 0, "skipped": True}

        # Detect language
        language = self._detect_language(abs_path)

        # Chunk file
        chunk_result = self.chunker.chunk_file(
            content=content,
            language=language,
            file_path=rel_path_str
        )
        chunks = chunk_result.chunks if isinstance(chunk_result, ChunkResult) else chunk_result
        symbols = chunk_result.symbols if isinstance(chunk_result, ChunkResult) else []

        if not chunks:
            logger.warning("no_chunks_created", file=rel_path_str)
            return {"success": False, "chunks": 0}

        # Embed chunks
        chunk_contents = [chunk.content for chunk in chunks]
        try:
            embeddings = await self._embed_with_cache(chunk_contents)
        except Exception as e:
            logger.error("embedding_failed",
                        file=rel_path_str,
                        error=str(e))
            return {"success": False, "chunks": 0}

        # Store in database (simplified - full implementation in Phase 2)
        # For now, just log
        logger.debug("file_metadata_stored",
                    file=rel_path_str,
                    hash=content_hash,
                    language=language,
                    size=len(content),
                    chunks=len(chunks))

        # Store vectors in Qdrant (workspace-scoped collection)
        collection_name = self._get_collection_name()

        symbol_by_chunk = {
            symbol.chunk_index: symbol
            for symbol in symbols
            if symbol.chunk_index is not None
        }

        # Create points
        points = []
        vector_ids = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # FIXED #3: Use UUID for point IDs instead of string concatenation
            point_id = str(uuid.uuid4())
            vector_ids.append(point_id)

            # FIXED #4: Store minimal payload, retrieve content from SQLite
            payload = {
                "workspace_id": self.workspace_id,
                "frontend_id": self.frontend_id,
                "file_path": rel_path_str,
                "chunk_index": idx,
                "chunk_type": chunk.chunk_type,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": language
            }

            symbol = symbol_by_chunk.get(idx)
            if symbol:
                payload["symbol_name"] = symbol.name
                payload["symbol_kind"] = symbol.kind

            points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload=payload
            ))

        file_id = await self._upsert_file_record(
            rel_path_str=rel_path_str,
            content_hash=content_hash,
            language=language,
            size_bytes=size_bytes,
            line_count=line_count
        )
        if file_id:
            if existing_record:
                await self._delete_vectors_for_file(file_id)
            await self._delete_chunks_for_file(file_id)
            await self._insert_chunks(
                file_id=file_id,
                chunks=chunks,
                vector_ids=vector_ids,
                embedding_model=self.embedder.get_model_name()
            )
            await self._insert_symbols(
                file_id=file_id,
                symbols=symbols,
                vector_ids=vector_ids
            )

        # Upsert to Qdrant
        try:
            self.vector_store.upsert_vectors(collection_name, points)
            if file_id:
                await self._set_file_index_status(file_id, "indexed")
            logger.info("file_indexed",
                       file=rel_path_str,
                       chunks=len(chunks))
            return {"success": True, "chunks": len(chunks)}

        except Exception as e:
            logger.error("vector_storage_failed",
                        file=rel_path_str,
                        error=str(e))
            if file_id:
                await self._set_file_index_status(file_id, "error", error=str(e))
            return {"success": False, "chunks": 0}

    async def index_workspace(self) -> Dict[str, Any]:
        """
        Index entire workspace

        Returns:
            Statistics about indexing
        """
        logger.info("workspace_indexing_start",
                   workspace_id=self.workspace_id,
                   frontend_id=self.frontend_id)

        # Ensure collection exists
        collection_name = self._get_collection_name()
        self.vector_store.create_collection(
            collection_name=collection_name,
            vector_size=self.embedder.get_dimensions()
        )

        # Discover files
        files = self.discover_files()

        # Index each file
        indexed = 0
        failed = 0
        total_chunks = 0
        total_files = len(files)

        await self._update_workspace_index_stats(
            index_status="indexing",
            total_files=total_files,
            indexed_files=0,
            total_chunks=0,
            index_progress=0.0
        )

        for rel_path in files:
            result = await self.index_file(rel_path)
            if result.get("success"):
                indexed += 1
                total_chunks += result.get("chunks", 0)
            else:
                failed += 1

            progress = (indexed / total_files) if total_files else 1.0
            await self._update_workspace_index_stats(
                indexed_files=indexed,
                total_chunks=total_chunks,
                index_progress=progress
            )

        if self.db:
            existing_paths = set(await self._get_existing_file_paths())
            discovered_paths = set(str(path) for path in files)
            removed_paths = existing_paths - discovered_paths
            for removed in removed_paths:
                await self._delete_file(Path(removed), recalculate=False)

        await self._recalculate_workspace_stats()

        status = "complete" if failed == 0 else "partial"
        await self._update_workspace_index_stats(
            index_status=status,
            index_progress=1.0 if total_files else 1.0,
            last_indexed_at=datetime.now(timezone.utc).isoformat()
        )

        logger.info("workspace_indexing_complete",
                   workspace_id=self.workspace_id,
                   total_files=total_files,
                   indexed=indexed,
                   failed=failed)

        return {
            "workspace_id": self.workspace_id,
            "total_files": total_files,
            "indexed": indexed,
            "failed": failed,
            "total_chunks": total_chunks,
            "frontend_id": self.frontend_id
        }
