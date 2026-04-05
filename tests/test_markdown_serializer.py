from pdf2md.serializers.markdown import serialize_markdown


def test_serialize_markdown_inserts_blocks_by_anchor() -> None:
    page_text_lines = {1: ["line1", "line2", "line3"]}
    page_blocks_by_page = {
        1: [
            (1, "<!-- block-a -->"),
            (3, "<!-- block-b -->"),
        ]
    }
    rendered = serialize_markdown(
        page_text_lines=page_text_lines,
        keep_page_markers=True,
        page_blocks_by_page=page_blocks_by_page,
    )
    expected = (
        "<!-- page: 1 -->\n\n"
        "line1\n"
        "<!-- block-a -->\n\n"
        "line2\n"
        "line3\n"
        "<!-- block-b -->\n"
    )
    assert rendered == expected
