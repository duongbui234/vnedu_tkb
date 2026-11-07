"""Write the Excel template for exporting a school's timetable in the canonical format.

Standard library only (a minimal .xlsx with inline strings), so no dependency or lock change.
Run ``python -m tools.real_data.make_template <dir>`` to write the .xlsx and a .csv sample.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HEADER = ("lop", "thu", "buoi", "tiet", "mon", "ma_gv")
SAMPLE: tuple[tuple[str | int, ...], ...] = (
    ("6A1", 2, "S", 1, "Chào cờ", "GV01"),
    ("6A1", 2, "S", 2, "Toán", "GV01"),
    ("6A1", 2, "S", 3, "Toán", "GV01"),
    ("6A1", 2, "S", 4, "Ngữ văn", "GV02"),
    ("6A1", 3, "S", 1, "Tiếng Anh", "GV03"),
    ("6A2", 2, "S", 1, "Chào cờ", "GV04"),
    ("6A2", 2, "S", 2, "Ngữ văn", "GV02"),
    ("6A2", 2, "S", 3, "Tiếng Anh", "GV03"),
    ("6A2", 3, "C", 1, "Toán", "GV01"),
)
GUIDE = (
    ("Cột", "Ý nghĩa"),
    ("lop", "Mã lớp như trường đang dùng (6A1, 10A2…)"),
    ("thu", "Thứ trong tuần: 2 = thứ Hai … 7 = thứ Bảy"),
    ("buoi", "S = sáng, C = chiều"),
    ("tiet", "Số thứ tự tiết trong buổi: 1, 2, 3…"),
    ("mon", "Tên môn hoặc hoạt động (Toán, Chào cờ, Sinh hoạt lớp…)"),
    ("ma_gv", "Mã giáo viên đã ẩn danh (GV01…). KHÔNG ghi họ tên thật"),
    ("", ""),
    ("Quy tắc", "Mỗi dòng là một tiết của một lớp. Tiết đôi ghi thành hai dòng liền nhau."),
    ("Quy tắc", "Một lớp chia nhóm hay có hai GV trong cùng tiết: ghi mỗi GV một dòng."),
    ("Quy tắc", "Không ghi ngày sinh, điện thoại, email, CCCD hay họ tên của bất kỳ ai."),
)


def _cell(ref: str, value: str | int) -> str:
    if isinstance(value, int):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'


def _sheet(rows: tuple[tuple[str | int, ...], ...]) -> str:
    body = "".join(
        f'<row r="{i}">'
        + "".join(_cell(f"{chr(65 + j)}{i}", v) for j, v in enumerate(row))
        + "</row>"
        for i, row in enumerate(rows, 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{body}</sheetData></worksheet>"
    )


def write_xlsx(path: Path) -> None:
    sheets = (("thoi_khoa_bieu", (HEADER, *SAMPLE)), ("huong_dan", GUIDE))
    ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    office = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="{office}.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            f'ContentType="{office}.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{ns}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'xmlns:r="{ns}"><sheets>'
        + "".join(
            f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _) in enumerate(sheets, 1)
        )
        + "</sheets></workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{ns}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Relationships>"
    )
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for i, (_, rows) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet(rows))


def sample_csv() -> str:
    return "\n".join(",".join(str(v) for v in row) for row in (HEADER, *SAMPLE)) + "\n"


def main(argv: list[str] | None = None) -> int:
    target = Path((argv if argv is not None else sys.argv[1:])[0])
    target.mkdir(parents=True, exist_ok=True)
    write_xlsx(target / "mau-thoi-khoa-bieu.xlsx")
    (target / "mau-thoi-khoa-bieu.csv").write_text(sample_csv(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
