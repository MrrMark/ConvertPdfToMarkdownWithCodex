from __future__ import annotations


def serialize_markdown(
    page_texts: dict[int, str],
    keep_page_markers: bool,
    page_blocks_by_page: dict[int, list[str]] | None = None,
) -> str:
    """Serialize extracted page texts into deterministic markdown."""
    lines: list[str] = []
    page_blocks_by_page = page_blocks_by_page or {}

    for page in sorted(page_texts):
        if keep_page_markers:
            lines.append(f"<!-- page: {page} -->")
            lines.append("")

        text = page_texts[page]
        if text:
            lines.append(text)

        for block in page_blocks_by_page.get(page, []):
            lines.append(block)
            lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
