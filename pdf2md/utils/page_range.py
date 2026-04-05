from __future__ import annotations


from typing import Optional


def parse_page_range(raw: Optional[str], total_pages: int) -> list[int]:
    """Parse 1-based page ranges such as '1-3,5' into sorted unique pages."""
    if total_pages <= 0:
        return []
    if raw is None or raw.strip() == "":
        return list(range(1, total_pages + 1))

    selected: set[int] = set()
    for token in raw.split(","):
        part = token.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            if not start_text.strip() or not end_text.strip():
                raise ValueError(f"Invalid page range token: '{part}'")
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid page range token: '{part}'")
            for page in range(start, end + 1):
                if page < 1 or page > total_pages:
                    raise ValueError(f"Page out of bounds: {page}")
                selected.add(page)
        else:
            page = int(part)
            if page < 1 or page > total_pages:
                raise ValueError(f"Page out of bounds: {page}")
            selected.add(page)

    if not selected:
        raise ValueError("No valid pages selected")
    return sorted(selected)
