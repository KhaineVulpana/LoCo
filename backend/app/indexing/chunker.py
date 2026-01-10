"""
Chunker - Splits files into indexable chunks.
Supports AST-based chunking with tree-sitter and a sliding-window fallback.
"""

from typing import List, Optional, Dict, Tuple, Any
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

try:
    from tree_sitter import Parser
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
except Exception:
    Parser = None
    tree_sitter_python = None
    tree_sitter_javascript = None
    tree_sitter_typescript = None


@dataclass
class Chunk:
    """Represents a chunk of code/text"""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # "heuristic", "function", "class" (tree-sitter later)
    start_offset: int = 0  # Byte offset in file
    end_offset: int = 0


@dataclass
class SymbolInfo:
    """Represents a parsed code symbol."""
    name: str
    kind: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    signature: Optional[str] = None
    parent_qualname: Optional[str] = None
    chunk_index: Optional[int] = None


@dataclass
class ChunkResult:
    """Chunking output with optional symbol metadata."""
    chunks: List[Chunk]
    symbols: List[SymbolInfo]


class SimpleChunker:
    """
    Simple sliding window chunker
    TODO Phase 2: Replace with tree-sitter AST chunking for better quality
    """

    def __init__(
        self,
        window_size: int = 50,  # lines
        overlap: int = 10        # lines
    ):
        """
        Initialize chunker

        Args:
            window_size: Number of lines per chunk
            overlap: Number of overlapping lines between chunks
        """
        self.window_size = window_size
        self.overlap = overlap

        logger.debug("chunker_initialized",
                    window_size=window_size,
                    overlap=overlap)

    def chunk_file(
        self,
        content: str,
        language: Optional[str] = None,
        file_path: str = ""
    ) -> List[Chunk]:
        """
        Chunk file content into smaller pieces

        Args:
            content: File content as string
            language: Programming language (for future tree-sitter)
            file_path: Path to file (for logging)

        Returns:
            List of Chunk objects
        """
        if not content:
            logger.warning("empty_file_content", file_path=file_path)
            return []

        lines = content.split('\n')
        total_lines = len(lines)

        if total_lines == 0:
            return []

        chunks = []
        step = self.window_size - self.overlap

        # Sliding window
        for i in range(0, total_lines, step):
            end_idx = min(i + self.window_size, total_lines)
            chunk_lines = lines[i:end_idx]

            # Skip empty chunks
            chunk_content = '\n'.join(chunk_lines)
            if not chunk_content.strip():
                continue

            # Calculate byte offsets (approximate)
            start_offset = sum(len(line) + 1 for line in lines[:i])  # +1 for \n
            end_offset = start_offset + len(chunk_content)

            chunks.append(Chunk(
                content=chunk_content,
                start_line=i,
                end_line=end_idx,
                chunk_type="heuristic",
                start_offset=start_offset,
                end_offset=end_offset
            ))

            # Stop if we've reached the end
            if end_idx >= total_lines:
                break

        logger.debug("file_chunked",
                    file_path=file_path,
                    total_lines=total_lines,
                    chunks_created=len(chunks))

        return chunks

    def chunk_text(self, text: str) -> List[Chunk]:
        """
        Chunk arbitrary text (for non-code files)

        Args:
            text: Text content

        Returns:
            List of Chunk objects
        """
        return self.chunk_file(text, language=None, file_path="<text>")


class ASTChunker:
    """AST-based chunker using tree-sitter with fallback to SimpleChunker."""

    def __init__(self, fallback: Optional[SimpleChunker] = None):
        self.fallback = fallback or SimpleChunker(window_size=50, overlap=10)
        self.parsers: Dict[str, Parser] = {}

    def chunk_file(
        self,
        content: str,
        language: Optional[str] = None,
        file_path: str = ""
    ) -> ChunkResult:
        if not content or not Parser:
            return ChunkResult(chunks=self.fallback.chunk_file(content, language, file_path), symbols=[])

        parser = self._get_parser(language, file_path)
        if not parser:
            return ChunkResult(chunks=self.fallback.chunk_file(content, language, file_path), symbols=[])

        content_bytes = content.encode("utf-8")
        tree = parser.parse(content_bytes)
        root = tree.root_node

        symbols: List[SymbolInfo] = []
        chunks: List[Chunk] = []

        symbol_nodes = self._collect_symbol_nodes(root, language, file_path, content_bytes)
        for node, kind, parent_qualname in symbol_nodes:
            name = self._get_symbol_name(node, content_bytes)
            if not name:
                continue

            chunk_text = content_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            if not chunk_text.strip():
                continue

            chunk = Chunk(
                content=chunk_text,
                start_line=node.start_point[0],
                end_line=node.end_point[0],
                chunk_type=kind,
                start_offset=node.start_byte,
                end_offset=node.end_byte
            )
            chunks.append(chunk)

            signature = chunk_text.splitlines()[0].strip() if chunk_text else None
            symbols.append(SymbolInfo(
                name=name,
                kind=kind,
                start_line=node.start_point[0],
                start_column=node.start_point[1],
                end_line=node.end_point[0],
                end_column=node.end_point[1],
                signature=signature,
                parent_qualname=parent_qualname,
                chunk_index=len(chunks) - 1
            ))

        if not chunks:
            return ChunkResult(chunks=self.fallback.chunk_file(content, language, file_path), symbols=[])

        return ChunkResult(chunks=chunks, symbols=symbols)

    def _resolve_language_key(self, language: Optional[str], file_path: str) -> Optional[str]:
        ext = file_path.lower()
        if ext.endswith(".tsx"):
            return "tsx"
        if ext.endswith(".jsx"):
            return "jsx"
        if language == "python":
            return "python"
        if language == "typescript":
            return "typescript"
        if language == "javascript":
            return "javascript"
        return None

    def _get_parser(self, language: Optional[str], file_path: str) -> Optional[Parser]:
        key = self._resolve_language_key(language, file_path)
        if not key:
            return None

        if key in self.parsers:
            return self.parsers[key]

        lang = self._load_language(key)
        if not lang:
            return None

        parser = Parser()
        parser.set_language(lang)
        self.parsers[key] = parser
        return parser

    def _load_language(self, key: str):
        try:
            if key == "python" and tree_sitter_python:
                return tree_sitter_python.language()
            if key in ("javascript", "jsx") and tree_sitter_javascript:
                return tree_sitter_javascript.language()
            if key == "typescript" and tree_sitter_typescript:
                return tree_sitter_typescript.language_typescript()
            if key == "tsx" and tree_sitter_typescript:
                return tree_sitter_typescript.language_tsx()
        except Exception as e:
            logger.warning("tree_sitter_language_load_failed", language=key, error=str(e))
        return None

    def _collect_symbol_nodes(
        self,
        root,
        language: Optional[str],
        file_path: str,
        content_bytes: bytes
    ) -> List[Tuple[Any, str, Optional[str]]]:
        symbols = []
        key = self._resolve_language_key(language, file_path)

        if key == "python":
            targets = {
                "function_definition": "function",
                "async_function_definition": "function",
                "class_definition": "class"
            }
        else:
            targets = {
                "function_declaration": "function",
                "class_declaration": "class",
                "method_definition": "method",
                "interface_declaration": "interface",
                "enum_declaration": "enum"
            }

        def walk(node, parent_qualname: Optional[str] = None):
            node_type = node.type
            if node_type in targets:
                name = self._get_symbol_name(node, content_bytes)
                qualname = f"{parent_qualname}.{name}" if parent_qualname and name else name
                symbols.append((node, targets[node_type], parent_qualname))
                next_parent = qualname or parent_qualname
            else:
                next_parent = parent_qualname

            for child in node.children:
                walk(child, next_parent)

        walk(root)
        return symbols

    def _get_symbol_name(self, node, content_bytes: Optional[bytes]) -> Optional[str]:
        name_node = None
        try:
            name_node = node.child_by_field_name("name")
        except Exception:
            name_node = None

        if name_node and content_bytes is not None:
            return content_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
        if name_node:
            return name_node.text.decode("utf-8", errors="ignore") if hasattr(name_node, "text") else None
        return None
