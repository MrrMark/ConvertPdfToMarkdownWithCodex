from pdf2md.serializers.markdown import repair_hyphenated_lines, serialize_markdown, serialize_markdown_result


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
        "\n"
        "<!-- block-a -->\n\n"
        "line2\n"
        "line3\n"
        "\n"
        "<!-- block-b -->\n"
    )
    assert rendered == expected


def test_serialize_markdown_keeps_single_blank_line_around_structure_and_blocks() -> None:
    rendered = serialize_markdown(
        page_text_lines={
            1: [
                "2.2.1 Command Completion",
                "Paragraph line one",
                "Paragraph line two",
                "Figure 1: Sample caption",
                "Tail paragraph",
            ]
        },
        keep_page_markers=False,
        page_blocks_by_page={1: [(3, "<!-- table: page=1 index=1 mode=html -->\n<table></table>")]},
    )

    assert "2.2.1 Command Completion\n\nParagraph line one\nParagraph line two" in rendered
    assert "Paragraph line two\n\n<!-- table: page=1 index=1 mode=html -->\n<table></table>\n\nFigure 1: Sample caption" in rendered
    assert "Figure 1: Sample caption\n\nTail paragraph\n" in rendered


def test_serialize_markdown_result_reports_conservative_structure_counts() -> None:
    result = serialize_markdown_result(
        page_text_lines={
            1: [
                "2.2.1 Command Completion",
                "- bullet item",
                "1. ordered item",
                "    register = value",
                "ordinary paragraph",
            ]
        },
        keep_page_markers=False,
    )

    assert "### 2.2.1 Command Completion" in result.markdown
    assert "```text\n    register = value\n```" in result.markdown
    assert result.heading_count == 1
    assert result.list_item_count == 2
    assert result.code_block_count == 1


def test_repair_hyphenated_lines_is_opt_in_helper() -> None:
    result = repair_hyphenated_lines(["interoper-", "ability", "non-", "Breaking"])

    assert result.lines == ["interoperability", "non-", "Breaking"]
    assert result.repair_count == 1
