from __future__ import annotations

from pathlib import Path

try:
    from unstructured.partition.auto import partition
except ModuleNotFoundError:  # pragma: no cover
    partition = None


def _is_document_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return True
    content_type = content_type.lower()
    return any(
        content_type.startswith(prefix)
        for prefix in (
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument",
            "application/vnd.ms-",
            "text/plain",
        )
    )


def extract_document_blocks(content_path: str, content_type: str | None = None) -> dict:
    path = Path(content_path)
    if partition is None or not path.exists() or not _is_document_content_type(content_type):
        return {
            "document_blocks": [],
            "sections": [],
            "plain_text": "",
            "extractor": "unstructured",
            "content_type": content_type,
        }

    blocks = []
    plain_parts = []
    for element in partition(filename=str(path)):
        text = str(element).strip()
        if text:
            blocks.append({"type": element.__class__.__name__, "text": text})
            plain_parts.append(text)
    return {
        "document_blocks": blocks,
        "sections": blocks,
        "plain_text": "\n\n".join(plain_parts),
        "extractor": "unstructured",
        "content_type": content_type,
    }
