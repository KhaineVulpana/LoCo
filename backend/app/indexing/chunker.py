"""
Chunker - Splits files into indexable chunks
Uses sliding window approach (tree-sitter for Phase 2)
"""

from typing import List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class Chunk:
    """Represents a chunk of code/text"""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # "heuristic", "function", "class" (tree-sitter later)
    start_offset: int = 0  # Byte offset in file
    end_offset: int = 0


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
