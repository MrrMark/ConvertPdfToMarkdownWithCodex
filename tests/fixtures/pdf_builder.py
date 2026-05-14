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
    graphics: list[str] = field(default_factory=list)
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
        commands = list(spec.graphics)
        commands.extend(_text_command(item) for item in spec.texts)
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


def build_layout_stress_pdf(path: Path) -> None:
    """Build a compact fixture with columns, sidebar text, figure/caption, footnotes, and mixed language."""
    page_one_text = [
        PositionedText("1 Layout Stress", 72, 800, 14),
        PositionedText("Left column requirement shall preserve order.", 72, 760, 10),
        PositionedText("Left column continuation references Figure 1.", 72, 742, 10),
        PositionedText("Right column note should follow left content.", 318, 760, 10),
        PositionedText("Right column completion text.", 318, 742, 10),
        PositionedText("Sidebar: implementation hint", 430, 620, 8),
        PositionedText("Figure 1: Floating state marker", 430, 666, 9),
        PositionedText("[1] Footnote with source detail", 72, 72, 7),
    ]
    page_two_text = [
        PositionedText("1.1 Mixed Language", 72, 800, 14),
        PositionedText("Korean English mixed paragraph follows.", 72, 760, 10),
        PositionedText("Hangul marker with English source text.", 72, 742, 10),
        PositionedText("- mixed bullet item", 72, 706, 10),
        PositionedText("The parser shall keep this sentence.", 72, 670, 10),
    ]
    write_pdf(
        path,
        [
            PageSpec(texts=page_one_text, repeated_image=True),
            PageSpec(texts=page_two_text),
        ],
    )


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


def build_continued_table_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[PositionedText("Table 1: Device fields", 72, 760)],
                tables=[TableSpec([["Field", "Value"], ["alpha", "1"]], 72, 730, [120, 120])],
            ),
            PageSpec(
                tables=[TableSpec([["Field", "Value"], ["beta", "2"]], 72, 730, [120, 120])],
            ),
        ],
    )


def build_repeated_template_table_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(tables=[TableSpec([["Field", "Value"], ["Total", "100"]], 72, 730, [120, 120])]),
            PageSpec(tables=[TableSpec([["Field", "Value"], ["Total", "100"]], 72, 730, [120, 120])]),
        ],
    )


def build_table_accuracy_pack_pdf(path: Path) -> None:
    """Build table fixtures that stress complex fallback and technical row provenance."""
    write_pdf(
        path,
        [
            PageSpec(
                texts=[PositionedText("Table 1: Command timing fields", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["", "Latency", "Latency", "Latency"],
                            ["Command", "Min", "Max", "Typical"],
                            ["Read", "1", "3", "2"],
                            ["Write", "2", "4", "3"],
                            ["Notes: values are cycles", "", "", ""],
                        ],
                        72,
                        760,
                        [120, 80, 80, 80],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 2: Control register bits", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Bits", "Field", "Reset", "Access", "Description"],
                            ["31:16", "RSVD", "0h", "RO", "Reserved bits"],
                            ["15:8", "STATUS", "0h", "RO", "Current status"],
                            ["7:0", "ENABLE", "0h", "RW", "Enable mask"],
                        ],
                        72,
                        760,
                        [72, 92, 70, 70, 180],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 3: Command opcodes", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Command", "Opcode", "Description"],
                            ["Identify", "06h", "Identify command"],
                            ["Sanitize", "84h", "Sanitize command"],
                        ],
                        72,
                        760,
                        [110, 80, 180],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 4: Log identifiers", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Log Identifier", "Description"],
                            ["02h", "SMART information"],
                        ],
                        72,
                        760,
                        [130, 180],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 5: Feature identifiers", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Feature Identifier", "Value", "Description"],
                            ["02h", "Volatile Write Cache", "Feature setting"],
                        ],
                        72,
                        760,
                        [130, 150, 180],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 6: Security methods", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Method", "ProtocolID", "Description"],
                            ["Erase", "01h", "Security method"],
                        ],
                        72,
                        760,
                        [120, 100, 180],
                    ),
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 7: Continued status fields", 72, 790, 10)],
                tables=[TableSpec([["Field", "Value"], ["alpha", "1"]], 72, 760, [120, 120])],
            ),
            PageSpec(
                tables=[TableSpec([["Field", "Value"], ["beta", "2"]], 72, 760, [120, 120])],
            ),
        ],
    )


def build_diagram_suite_pdf(path: Path) -> None:
    """Build vector-rendered diagram pages for figure crop fallback provenance."""
    state_machine_graphics = [
        "1 w",
        "90 610 90 44 re S",
        "250 610 90 44 re S",
        "410 610 90 44 re S",
        "180 632 m 250 632 l S",
        "340 632 m 410 632 l S",
        "410 610 m 340 590 l S",
        "340 590 m 250 610 l S",
    ]
    state_machine_text = [
        PositionedText("2.1 State Machine", 72, 800, 14),
        PositionedText("Figure 1: State machine diagram READY ERROR RESET", 72, 720, 10),
        PositionedText("IDLE", 118, 628, 10),
        PositionedText("ACTIVE", 276, 628, 10),
        PositionedText("ERROR", 438, 628, 10),
        PositionedText("READY", 194, 642, 8),
        PositionedText("FAULT", 354, 642, 8),
        PositionedText("RESET", 322, 584, 8),
    ]

    sequence_graphics = [
        "1 w",
        "150 648 m 150 500 l S",
        "400 648 m 400 500 l S",
        "150 612 m 400 612 l S",
        "400 568 m 150 568 l S",
    ]
    sequence_text = [
        PositionedText("2.2 Sequence Flow", 72, 800, 14),
        PositionedText("Figure 2: Sequence diagram Command Completion", 72, 720, 10),
        PositionedText("Host", 134, 662, 10),
        PositionedText("Controller", 372, 662, 10),
        PositionedText("Command", 252, 624, 9),
        PositionedText("Completion", 246, 580, 9),
    ]

    register_graphics = [
        "1 w",
        "88 610 150 54 re S",
        "238 610 120 54 re S",
        "358 610 120 54 re S",
        "88 637 m 478 637 l S",
    ]
    register_text = [
        PositionedText("2.3 Register Layout", 72, 800, 14),
        PositionedText("Figure 3: Register layout bit field RSVD STATUS ENABLE", 72, 720, 10),
        PositionedText("31:16", 132, 646, 9),
        PositionedText("15:8", 280, 646, 9),
        PositionedText("7:0", 406, 646, 9),
        PositionedText("RSVD", 132, 620, 9),
        PositionedText("STATUS", 272, 620, 9),
        PositionedText("ENABLE", 394, 620, 9),
    ]

    write_pdf(
        path,
        [
            PageSpec(texts=state_machine_text, graphics=state_machine_graphics),
            PageSpec(texts=sequence_text, graphics=sequence_graphics),
            PageSpec(texts=register_text, graphics=register_graphics),
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


def build_semantic_requirements_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1 Requirements", 72, 780, 14),
                    PositionedText("The controller shall return SUCCESS.", 72, 742, 10),
                    PositionedText("The host shall not modify reserved bits.", 72, 724, 10),
                    PositionedText("Software should retry the command.", 72, 706, 10),
                    PositionedText("The command may complete asynchronously.", 72, 688, 10),
                    PositionedText("The controller will report status.", 72, 670, 10),
                ]
            )
        ],
    )


def build_semantic_definitions_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("2 Terms", 72, 780, 14),
                    PositionedText("Controller: The device component that processes commands.", 72, 742, 10),
                    PositionedText("Namespace means a formatted collection of logical blocks.", 72, 724, 10),
                ]
            )
        ],
    )


def build_semantic_cross_refs_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1.1 Overview", 72, 780, 14),
                    PositionedText("See Section 2.1 and Table 1 for details.", 72, 742, 10),
                    PositionedText("2.1 Details", 72, 690, 14),
                    PositionedText("Table 1: Fields", 72, 650, 10),
                ],
                tables=[TableSpec([["Field", "Description"], ["Status", "Current status"]], 72, 620, [120, 160])],
            )
        ],
    )


def build_semantic_table_parameters_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[PositionedText("Table 1: Register fields", 72, 760)],
                tables=[
                    TableSpec(
                        [["Field", "Bits", "Description"], ["Status", "3:0", "Current status"]],
                        72,
                        730,
                        [100, 80, 160],
                    )
                ],
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
