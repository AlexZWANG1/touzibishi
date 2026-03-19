"""
Text chunking module — splits documents into semantically coherent chunks.

Strategy: split on paragraph boundaries first, then merge paragraphs into
chunks up to chunk_size characters with configurable overlap.
"""

from dataclasses import dataclass


@dataclass
class ChunkInfo:
    content: str
    chunk_index: int
    char_offset_start: int
    char_offset_end: int


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 200,
) -> list[ChunkInfo]:
    """Split text into overlapping chunks, respecting paragraph boundaries.

    Returns a list of ChunkInfo with content and character offsets into the
    original text.
    """
    if not text or not text.strip():
        return []

    # Split into paragraphs (double newline or more)
    paragraphs: list[tuple[int, str]] = []
    start = 0
    for part in text.split("\n\n"):
        stripped = part.strip()
        if stripped:
            # Find the actual start offset in the original text
            actual_start = text.find(stripped, start)
            if actual_start == -1:
                actual_start = start
            paragraphs.append((actual_start, stripped))
            start = actual_start + len(stripped)

    if not paragraphs:
        return [ChunkInfo(content=text.strip(), chunk_index=0, char_offset_start=0, char_offset_end=len(text))]

    # Merge paragraphs into chunks
    chunks: list[ChunkInfo] = []
    current_parts: list[str] = []
    current_len = 0
    chunk_start_offset = paragraphs[0][0]

    for offset, para in paragraphs:
        para_len = len(para)

        if current_len + para_len > chunk_size and current_parts:
            # Flush current chunk
            content = "\n\n".join(current_parts)
            chunks.append(ChunkInfo(
                content=content,
                chunk_index=len(chunks),
                char_offset_start=chunk_start_offset,
                char_offset_end=chunk_start_offset + len(content),
            ))

            # Overlap: keep trailing parts that fit within overlap budget
            overlap_parts: list[str] = []
            overlap_len = 0
            for p in reversed(current_parts):
                if overlap_len + len(p) > overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p)

            if overlap_parts:
                current_parts = overlap_parts
                current_len = sum(len(p) for p in current_parts)
                # Recalculate start offset from the overlap
                chunk_start_offset = offset - current_len - 2 * (len(current_parts) - 1)
                if chunk_start_offset < 0:
                    chunk_start_offset = offset
            else:
                current_parts = []
                current_len = 0
                chunk_start_offset = offset

        current_parts.append(para)
        current_len += para_len
        if not current_parts[:-1]:  # first part in this chunk
            chunk_start_offset = offset

    # Flush remaining
    if current_parts:
        content = "\n\n".join(current_parts)
        chunks.append(ChunkInfo(
            content=content,
            chunk_index=len(chunks),
            char_offset_start=chunk_start_offset,
            char_offset_end=chunk_start_offset + len(content),
        ))

    return chunks
