from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, StreamObject, TextStringObject


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


def _unicode_text_operand(text: str) -> str:
    encoded = text.encode("utf-16-be").hex().upper()
    return f"<{encoded}>"


def _text_command(item: PositionedText) -> str:
    operand = _unicode_text_operand(item.text) if item.font_resource == "F3" else _text_operand(item.text)
    return f"BT /{item.font_resource} {item.size} Tf {item.x:.2f} {item.y:.2f} Td {operand} Tj ET"


def _to_unicode_cmap() -> StreamObject:
    cmap = """\
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /pdf2md-fixture-unicode def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
1 beginbfrange
<0000> <FFFF> <0000>
endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""
    stream = StreamObject()
    stream._data = cmap.encode("ascii")  # noqa: SLF001
    return stream


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
    to_unicode_ref = writer._add_object(_to_unicode_cmap())  # noqa: SLF001
    cid_system_info = DictionaryObject(
        {
            NameObject("/Registry"): TextStringObject("Adobe"),
            NameObject("/Ordering"): TextStringObject("Identity"),
            NameObject("/Supplement"): NumberObject(0),
        }
    )
    unicode_font_descriptor = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/FontDescriptor"),
            NameObject("/FontName"): NameObject("/Helvetica"),
            NameObject("/Flags"): NumberObject(4),
            NameObject("/FontBBox"): ArrayObject(
                [NumberObject(0), NumberObject(-200), NumberObject(1000), NumberObject(900)]
            ),
            NameObject("/ItalicAngle"): NumberObject(0),
            NameObject("/Ascent"): NumberObject(900),
            NameObject("/Descent"): NumberObject(-200),
            NameObject("/CapHeight"): NumberObject(700),
            NameObject("/StemV"): NumberObject(80),
        }
    )
    unicode_font_descriptor_ref = writer._add_object(unicode_font_descriptor)  # noqa: SLF001
    unicode_descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType0"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/CIDSystemInfo"): cid_system_info,
            NameObject("/FontDescriptor"): unicode_font_descriptor_ref,
        }
    )
    unicode_descendant_ref = writer._add_object(unicode_descendant)  # noqa: SLF001
    unicode_font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/Identity-H"),
            NameObject("/DescendantFonts"): ArrayObject([unicode_descendant_ref]),
            NameObject("/ToUnicode"): to_unicode_ref,
        }
    )
    unicode_ref = writer._add_object(unicode_font)  # noqa: SLF001
    image_ref = writer._add_object(_image_stream()) if any(spec.repeated_image for spec in pages) else None

    for spec in pages:
        page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        resources = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): helvetica_ref,
                        NameObject("/F2"): courier_ref,
                        NameObject("/F3"): unicode_ref,
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


def build_nvme_base_slice_pdf(path: Path) -> None:
    """Build a sanitized NVMe-shaped slice without copying official specification text."""
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1 NVMe Synthetic Slice", 72, 800, 14),
                    PositionedText("The controller shall report synthetic health status when requested.", 72, 760, 10),
                    PositionedText("NOTE: Synthetic notes are review-only adapter evidence.", 72, 742, 10),
                    PositionedText("Example: A host may issue Identify for demonstration.", 72, 724, 10),
                ]
            ),
            PageSpec(
                texts=[PositionedText("Table 1: Command opcode slice", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Command", "Opcode", "Description"],
                            ["Identify", "06h", "Synthetic identify command"],
                        ],
                        72,
                        760,
                        [120, 80, 210],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 2: Log page identifier slice", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Log Identifier", "Description"],
                            ["02h", "Synthetic health log"],
                        ],
                        72,
                        760,
                        [140, 220],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 3: Feature identifier slice", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Feature Identifier", "Value", "Description"],
                            ["0Ch", "Async Event", "Synthetic event feature"],
                        ],
                        72,
                        760,
                        [140, 120, 210],
                    )
                ],
            ),
            PageSpec(
                texts=[PositionedText("Table 4: Register bitfield slice", 72, 790, 10)],
                tables=[
                    TableSpec(
                        [
                            ["Register", "Offset", "Bits", "Field", "Reset Default", "Access", "Description"],
                            ["CAP", "0x0000", "15:0", "MQES", "0h", "RO", "Synthetic max queue entries"],
                        ],
                        72,
                        760,
                        [72, 76, 54, 64, 92, 60, 150],
                        font_size=8,
                    )
                ],
            ),
        ],
    )


def build_nvme_command_set_slice_pdf(path: Path) -> None:
    """Build a sanitized NVM Command Set-shaped slice without official specification text."""
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1 NVMe Command Set Synthetic Slice", 72, 800, 14),
                    PositionedText("The controller shall process a synthetic read command request.", 72, 760, 10),
                    PositionedText("NOTE: Synthetic command details are adapter-only evidence.", 72, 742, 10),
                ]
            ),
            PageSpec(
                texts=[
                    PositionedText("2 Read Command", 72, 800, 14),
                    PositionedText("Table 1: Command opcode slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Command", "Queue Type", "Opcode", "Description"],
                            ["Read", "I/O", "02h", "Synthetic read command"],
                        ],
                        72,
                        730,
                        [110, 86, 70, 210],
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("2.1 Read Command Dwords", 72, 800, 14),
                    PositionedText("Table 2: Command dword field slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Command Dword", "Bits", "Field", "Description"],
                            ["CDW10", "31:00", "SLBA", "Synthetic starting LBA"],
                        ],
                        72,
                        730,
                        [120, 76, 82, 210],
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("2.2 Read Command Pointers", 72, 800, 14),
                    PositionedText("Table 3: Command pointer slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Pointer", "Field", "Description"],
                            ["Metadata Pointer", "MPTR", "Synthetic metadata pointer"],
                        ],
                        72,
                        730,
                        [140, 86, 220],
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("2.3 Read Command Status", 72, 800, 14),
                    PositionedText("Table 4: Status code slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Status Code Type", "Status Code", "Description"],
                            ["Command Specific Status", "80h", "Synthetic LBA out of range; correct command before retry"],
                        ],
                        72,
                        730,
                        [150, 92, 280],
                        font_size=8,
                    )
                ],
            ),
        ],
    )


def build_ocp_datacenter_nvme_ssd_slice_pdf(path: Path) -> None:
    """Build a sanitized OCP Datacenter NVMe SSD-shaped slice without official specification text."""
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1 OCP Datacenter NVMe SSD Synthetic Slice", 72, 800, 14),
                    PositionedText("This synthetic slice shall preserve requirement traceability metadata.", 72, 760, 10),
                    PositionedText("NOTE: These rows are fixture-only adapter evidence.", 72, 742, 10),
                ]
            ),
            PageSpec(
                texts=[
                    PositionedText("2 NVMe I/O Requirements", 72, 800, 14),
                    PositionedText("Table 1: OCP command requirement slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Requirement ID", "SSD", "Requirement Description", "Section"],
                            [
                                "NVMe-IO-6",
                                "Required",
                                "SSD shall support Write Zeroes command for synthetic compliance.",
                                "NVMe",
                            ],
                        ],
                        36,
                        730,
                        [96, 70, 308, 58],
                        font_size=7,
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("3 Standard Log Requirements", 72, 800, 14),
                    PositionedText("Table 2: OCP log requirement slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Requirement ID", "SSD", "Requirement Description", "Section"],
                            [
                                "STD-LOG-1",
                                "Required",
                                "SSD shall expose Error Information Log Identifier 01h for test collection.",
                                "Logs",
                            ],
                        ],
                        36,
                        730,
                        [96, 70, 308, 58],
                        font_size=7,
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("4 Feature Requirements", 72, 800, 14),
                    PositionedText("Table 3: OCP feature requirement slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Requirement ID", "SSD", "Requirement Description", "Section"],
                            [
                                "NVMe-OPT-2",
                                "Optional",
                                "SSD should support Feature Identifier 0Eh for timestamp handling.",
                                "Feature",
                            ],
                            [
                                "TEL-1",
                                "Required",
                                "SSD shall report telemetry Statistic Identifier 0001h.",
                                "Telemetry",
                            ],
                        ],
                        36,
                        730,
                        [96, 70, 308, 58],
                        font_size=7,
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("5 Security and Form Factor Requirements", 72, 800, 14),
                    PositionedText("Table 4: OCP security requirement slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Requirement ID", "SSD", "Requirement Description", "Section"],
                            ["SEC-43", "Required", "SSD shall support SPDM authentication and TCG handoff.", "Security"],
                            ["FF-1", "Required", "SSD shall fit the E1.S form factor envelope.", "Mechanical"],
                        ],
                        36,
                        730,
                        [96, 70, 308, 58],
                        font_size=7,
                    )
                ],
            ),
        ],
    )


def build_spdm_security_slice_pdf(path: Path) -> None:
    """Build a sanitized SPDM-shaped slice without official specification text."""
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1 SPDM Synthetic Security Slice", 72, 800, 14),
                    PositionedText("Table 1: SPDM message code slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Message", "Message Code", "Description"],
                            ["GET_MEASUREMENTS", "E0h", "Requester shall retrieve measurement blocks."],
                            ["GET_CERTIFICATE", "82h", "Requester shall retrieve certificate chain data."],
                        ],
                        36,
                        730,
                        [145, 110, 277],
                        font_size=7,
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("2 SPDM Algorithms", 72, 800, 14),
                    PositionedText("Table 2: SPDM algorithm slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Algorithm", "Value", "Description"],
                            ["TPM_ALG_SHA_384", "0008h", "Responder shall support negotiated hash algorithms."],
                            ["ECDSA_ECC_NIST_P384", "0010h", "Responder may advertise asymmetric algorithms."],
                        ],
                        36,
                        730,
                        [180, 90, 262],
                        font_size=7,
                    )
                ],
            ),
        ],
    )


def build_caliptra_security_slice_pdf(path: Path) -> None:
    """Build a sanitized Caliptra-shaped RoT/security slice without official specification text."""
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("1 Caliptra Synthetic RoT Slice", 72, 800, 14),
                    PositionedText("Table 1: Caliptra asset and threat slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Asset Category", "Asset", "Security Property", "Attack Profile", "Mitigation"],
                            [
                                "Die unique asset",
                                "Synthetic device identity seed",
                                "Confidentiality",
                                "Logical attack",
                                "Keep derived values inside the key vault.",
                            ],
                            [
                                "Root of trust execution",
                                "Synthetic ROM firmware",
                                "Integrity",
                                "Fault injection",
                                "Use redundant decision checks.",
                            ],
                        ],
                        24,
                        730,
                        [112, 136, 104, 94, 182],
                        font_size=6,
                    )
                ],
            ),
            PageSpec(
                texts=[
                    PositionedText("2 Caliptra Mailbox and Register Slice", 72, 800, 14),
                    PositionedText("Table 2: Caliptra command and register slice", 72, 760, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Mailbox Command", "Interface", "Register", "Field", "Bits", "Description"],
                            [
                                "GET_SYNTHETIC_MEASUREMENT",
                                "Mailbox",
                                "CPTRA_STATUS",
                                "READY",
                                "0",
                                "Synthetic command reports measured boot status.",
                            ],
                            [
                                "SIGN_SYNTHETIC_QUOTE",
                                "Mailbox",
                                "CPTRA_FW_ERROR",
                                "ERROR_CODE",
                                "15:0",
                                "Synthetic command signs attestation evidence.",
                            ],
                        ],
                        24,
                        730,
                        [132, 72, 104, 86, 48, 186],
                        font_size=6,
                    )
                ],
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
    write_pdf(path, [PageSpec(texts=[PositionedText("한글 텍스트 원문", 72, 760, font_resource="F3")])])


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


def build_appendix_clause_requirement_pdf(path: Path) -> None:
    write_pdf(
        path,
        [
            PageSpec(
                texts=[
                    PositionedText("Appendix A Vendor Requirements", 72, 800, 16),
                    PositionedText("1.1 Nested Recovery Clause", 72, 752, 14),
                    PositionedText(
                        "VEND-APP-1 The device shall preserve appendix context when recovering tables.",
                        72,
                        712,
                        10,
                    ),
                    PositionedText("See Appendix A and Table 1 for details.", 72, 692, 10),
                    PositionedText("Table 1: Vendor requirement matrix", 72, 648, 10),
                ],
                tables=[
                    TableSpec(
                        [
                            ["Requirement ID", "Requirement Description", "Status"],
                            [
                                "VEND-APP-2",
                                "The exporter shall keep nested clause headings for vendor tables.",
                                "Mandatory",
                            ],
                        ],
                        72,
                        618,
                        [110, 300, 90],
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
