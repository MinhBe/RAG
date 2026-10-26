"""Load Markdown policy documents and split them into section-aware chunks."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")


@dataclass
class Document:
    doc_id: str
    title: str
    path: Path
    body: str
    meta: dict = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    section: str
    text: str

    @property
    def indexed_text(self) -> str:
        # Prepend the document title and section path so that a chunk like
        # "7 ngày | Không áp dụng" still carries what it is about.
        return f"{self.doc_title} > {self.section}\n{self.text}"


def load_documents(data_dir: Path) -> list[Document]:
    docs = []
    for path in sorted(data_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta: dict = {}
        match = _FRONTMATTER_RE.match(raw)
        if match:
            meta = yaml.safe_load(match.group(1)) or {}
            raw = raw[match.end() :]
        docs.append(
            Document(
                doc_id=meta.get("doc_id", path.stem),
                title=meta.get("title", path.stem),
                path=path,
                body=raw,
                meta=meta,
            )
        )
    return docs


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split on blank lines, keeping tables and lists whole when possible."""
    if len(text) <= max_chars:
        return [text]
    parts, current = [], ""
    for block in re.split(r"\n\s*\n", text):
        if current and len(current) + len(block) > max_chars:
            parts.append(current.strip())
            current = ""
        current += block + "\n\n"
    if current.strip():
        parts.append(current.strip())
    return parts


def chunk_document(doc: Document, max_chars: int = 1200) -> list[Chunk]:
    chunks: list[Chunk] = []
    path: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if not text:
            return
        section = " > ".join(path[1:]) or (path[0] if path else doc.title)
        for piece in _split_long(text, max_chars):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{len(chunks) + 1}",
                    doc_id=doc.doc_id,
                    doc_title=doc.title,
                    section=section,
                    text=piece,
                )
            )

    for line in doc.body.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            path[:] = path[: level - 1] + [heading.group(2).strip()]
            continue
        if line.startswith(">"):
            continue  # disclaimer / editorial notes are not policy content
        buffer.append(line)
    flush()
    return chunks
