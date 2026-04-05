from __future__ import annotations


def serialize_markdown(
    page_texts: dict[int, str],
    keep_page_markers: bool,
    table_blocks_by_page: dict[int, list[str]] | None = None,
    image_blocks_by_page: dict[int, list[str]] | None = None,
) -> str:
    """Serialize extracted page texts into deterministic markdown."""
    lines: list[str] = []
    table_blocks_by_page = table_blocks_by_page or {}
    image_blocks_by_page = image_blocks_by_page or {}

    for page in sorted(page_texts):
        if keep_page_markers:
            lines.append(f"<!-- page: {page} -->")
            lines.append("")

        text = page_texts[page]
        if text:
            lines.append(text)

        for table_block in table_blocks_by_page.get(page, []):
            lines.append(table_block)
            lines.append("")

        for image_block in image_blocks_by_page.get(page, []):
            lines.append(image_block)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
