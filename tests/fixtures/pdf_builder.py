from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, StreamObject


PAGE_WIDTH = 595
PAGE_HEIGHT = 842


@dataclass(frozen=True)
class PositionedText:
    text: str
    x: float
    y: float
    size: int = 12
    font_resource: str = "F1"


@dataclass(frozen=True)
class TableSpec:
    rows: list[list[str]]
    x: float
    y: float
    column_widths: list[float]
    row_height: float = 24.0
    font_size: int = 9


@dataclass(frozen=True)
class PageSpec:
    texts: list[PositionedText] = field(default_factory=list)
    tables: list[TableSpec] = field(default_factory=list)
    repeated_image: bool = False


def _text_operand(text: str) -> str:
    if all(ord(char) < 128 for char in text):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return f"({escaped})"
    encoded = ("\ufeff" + text).encode("utf-16-be").hex().upper()
    return f"<{encoded}>"


def _text_command(item: PositionedText) -> str:
    return f"BT /{item.font_resource} {item.size} Tf {item.x:.2f} {item.y:.2f} Td {_text_operand(item.text)} Tj ET"


def _table_commands(table: TableSpec) -> list[str]:
    commands = ["1 w"]
    x_positions = [table.x]
    for width in table.column_widths:
        x_positions.append(x_positions[-1] + width)
    y_positions = [table.y - table.row_height * idx for idx in range(len(table.rows) + 1)]

    for x in x_positions:
        commands.append(f"{x:.2f} {y_positions[0]:.2f} m {x:.2f} {y_positions[-1]:.2f} l S")
    for y in y_positions:
        commands.append(f"{x_positions[0]:.2f} {y:.2f} m {x_positions[-1]:.2f} {y:.2f} l S")

    for row_idx, row in enumerate(table.rows):
        text_y = y_positions[row_idx] - table.row_height + 8.0
        for col_idx, cell in enumerate(row):
            text_x = x_positions[col_idx] + 4.0
            commands.append(_text_command(PositionedText(cell, text_x, text_y, table.font_size)))
    return commands


def _image_stream() -> StreamObject:
    raw_rgb = bytes([220, 60, 60]) * (12 * 12)
    image = StreamObject()
    image._data = zlib.compress(raw_rgb)  # noqa: SLF001
    image[NameObject("/Type")] = NameObject("/XObject")
    image[NameObject("/Subtype")] = NameObject("/Image")
    image[NameObject("/Width")] = NumberObject(12)
    image[NameObject("/Height")] = NumberObject(12)
    image[NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
    image[NameObject("/BitsPerComponent")] = NumberObject(8)
    image[NameObject("/Filter")] = NameObject("/FlateDecode")
    return image


def write_pdf(path: Path, pages: list[PageSpec], password: str | None = None) -> None:
    writer = PdfWriter()

    helvetica = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    courier = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Courier"),
        }
    )
    helvetica_ref = writer._add_object(helvetica)  # noqa: SLF001
    courier_ref = writer._add_object(courier)  # noqa: SLF001
    image_ref = writer._add_object(_image_stream()) if any(spec.repeated_image for spec in pages) else None

    for spec in pages:
        page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        resources = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): helvetica_ref,
                        NameObject("/F2"): courier_ref,
                    }
                )
            }
        )
        if spec.repeated_image and image_ref is not None:
            resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Im1"): image_ref})
        page[NameObject("/Resources")] = resources
        commands = [_text_command(item) for item in spec.texts]
        for table in spec.tables:
            commands.extend(_table_commands(table))
        if spec.repeated_image:
            commands.append("q 48 0 0 48 430 690 cm /Im1 Do Q")
        content = StreamObject()
        content._data = "\n".join(commands).encode("utf-8")  # noqa: SLF001
        page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001

    if password:
        writer.encrypt(password)
    with path.open("wb") as fp:
        writer.write(fp)


def build_single_column_pdf(path: Path) -> None:
    write_pdf(path, [PageSpec(texts=[PositionedText("Single column alpha", 72, 760)])])


def build_two_column_pdf(path: Path) -> None:
    left = [PositionedText(f"Left line {idx}", 72, 780 - idx * 18) for idx in range(1, 7)]
    right = [PositionedText(f"Right line {idx}", 330, 780 - idx * 18) for idx in range(1, 7)]
    write_pdf(path, [PageSpec(texts=left + right)])


def build_repeated_header_footer_pdf(path: Path) -> None:
    pages = [
        PageSpec(
            texts=[
                PositionedText("Repeated Header", 72, 810),
                PositionedText(f"Body page {idx}", 72, 760),
                PositionedText("Repeated Footer", 72, 40),
            ]
        )
        for idx in range(1, 4)
    ]
    write_pdf(path, pages)


def build_simple_table_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[PositionedText("Table 1: Simple fields", 72, 760)],
                tables=[TableSpec([["Field", "Value"], ["alpha", "beta"]], 72, 730, [120, 120])],
            )
        ],
    )


def build_complex_table_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[PositionedText("Table 1: Complex fields", 72, 760)],
                tables=[
                    TableSpec(
                        [
                            ["", "Latency", "Latency"],
                            ["Command", "Min", "Max"],
                            ["Read", "1", "3"],
                            ["Write", "2", "4"],
                        ],
                        72,
                        730,
                        [120, 90, 90],
                    )
                ],
            )
        ],
    )


def build_repeated_image_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(texts=[PositionedText("Repeated image page 1", 72, 760)], repeated_image=True),
            PageSpec(texts=[PositionedText("Repeated image page 2", 72, 760)], repeated_image=True),
        ],
    )


def build_image_only_pdf(path: Path) -> None:
    write_pdf(path, [PageSpec(repeated_image=True)])


def build_korean_text_pdf(path: Path) -> None:
    write_pdf(path, [PageSpec(texts=[PositionedText("한글 텍스트 원문", 72, 760)])])


def build_structured_text_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("2.2 Structured Heading", 72, 760),
                    PositionedText("- bullet item", 72, 720),
                    PositionedText("1. ordered item", 72, 690),
                    PositionedText("interoper-", 72, 640),
                    PositionedText("ability", 72, 600),
                ]
            )
        ],
    )


def build_font_heading_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("Architecture Overview", 72, 760, 20),
                ]
            )
        ],
    )


def build_uppercase_body_pdf(path: Path) -> None:
    write_pdf(path, [PageSpec(texts=[PositionedText("THIS IS IMPORTANT BODY TEXT", 72, 760, 10)])])


def build_grouped_list_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("- first item", 72, 760, 10),
                    PositionedText("- second item", 72, 742, 10),
                ]
            )
        ],
    )


def build_code_block_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("value = 1", 108, 760, 10, font_resource="F2"),
                    PositionedText("return value", 108, 742, 10, font_resource="F2"),
                ]
            )
        ],
    )


def build_bottom_footnote_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("Body paragraph.", 72, 760, 10),
                    PositionedText("[1] Device-specific note", 72, 72, 7),
                ]
            )
        ],
    )


def build_password_pdf(path: Path, password: str = "secret") -> None:
    write_pdf(path, [PageSpec(texts=[PositionedText("Encrypted fixture", 72, 760)])], password=password)


def build_multi_page_text_pdf(path: Path, page_count: int) -> None:
    pages = [
        PageSpec(texts=[PositionedText(f"Benchmark page {page_number}", 72, 760)])
        for page_number in range(1, page_count + 1)
    ]
    write_pdf(path, pages)
