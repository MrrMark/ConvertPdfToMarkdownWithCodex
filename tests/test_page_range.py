from pdf2md.utils.page_range import parse_page_range


def test_parse_page_range_all_pages() -> None:
    assert parse_page_range(None, 3) == [1, 2, 3]


def test_parse_page_range_explicit() -> None:
    assert parse_page_range("1-2,4", 5) == [1, 2, 4]


def test_parse_page_range_invalid_out_of_bounds() -> None:
    try:
        parse_page_range("1,6", 5)
    except ValueError as exc:
        assert "out of bounds" in str(exc)
    else:
        raise AssertionError("ValueError expected")
