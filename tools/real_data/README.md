# Công cụ đối chiếu thời khóa biểu thật

Bước E của [kế hoạch tiếp nhận dữ liệu thật](../../docs/superpowers/plans/2026-11-07-real-timetable-intake.md).
Đây là tooling ngoài Scheduling Core: không sửa `src/`, không thêm dependency.

**Dữ liệu thật chỉ đặt dưới `benchmarks/artifacts/real/`** (đã gitignore). Không commit thời khóa biểu,
không ghi họ tên thật. Mã GV phải được ẩn danh trước (§3 của kế hoạch). Chỉ xử lý dữ liệu thật khi đã có
RD1 (được phép dùng dữ liệu).

## Định dạng chuẩn

CSV UTF-8, mỗi dòng là một tiết của một lớp: `lop,thu,buoi,tiet,mon,ma_gv`.

- `buoi`: S/C, Sáng/Chiều hoặc AM/PM.
- Tiết đôi là hai dòng liền nhau.
- Chia nhóm hoặc hai GV trong một tiết: mỗi GV một dòng.

Mẫu: [`template/mau-thoi-khoa-bieu.xlsx`](template/mau-thoi-khoa-bieu.xlsx) (có trang hướng dẫn) và
[`template/mau-thoi-khoa-bieu.csv`](template/mau-thoi-khoa-bieu.csv). Tạo lại mẫu bằng
`python -m tools.real_data.make_template tools/real_data/template`.

File của trường ở định dạng khác (Excel theo lớp, theo GV…) cần một bộ đọc nhỏ để chuyển về định dạng
này; bộ đọc đó viết sau khi xem file mẫu.

## Chạy

```bash
# 1. Chuyển sang input Core và lịch thật dạng assignment (không ghi đè thư mục có sẵn)
uv run python -m tools.real_data.convert_real benchmarks/artifacts/real/SCH01/tkb.csv \
    --output benchmarks/artifacts/real/SCH01/conv --school SCH01 [--frame khung_tiet.csv]

# 2. Kiểm hard và chấm lịch thật bằng evaluator độc lập
uv run python -m tools.real_data.score_real benchmarks/artifacts/real/SCH01/conv

# 3. Cho Core xếp cùng input rồi so (budget 60/120/180 s theo số lớp, 1 worker, seed 42)
uv run --extra solver python -m tools.real_data.compare_real benchmarks/artifacts/real/SCH01/conv \
    --output benchmarks/artifacts/real/SCH01/cmp
```

## Cách chuyển đổi (tóm tắt)

- **Phân công:** mỗi bộ (lớp, môn, GV) là một requirement; số tiết = số dòng.
- **Tiết đôi:** tiết liền nhau cùng buổi thành block 2 tiết. Chuỗi dài hơn 2 được tách thành 2+1… và
  ghi vào `split_runs`.
- **Tiết cố định:** "Chào cờ" và "Sinh hoạt" được khóa đúng ô.
- **Không biểu diễn được:**
  - tiết không có GV;
  - một lớp có nhiều dòng trong cùng tiết (chia nhóm);
  - một GV dạy nhiều lớp cùng tiết (lớp ghép).

  Các tiết này bị loại, liệt kê trong `conversion-report.json`, và ô đó bị chặn cho lớp và GV liên quan.
  Nhờ vậy Core và lịch thật giải cùng một bài.
- **Thang chấm chung** (§5 của kế hoạch), không phải quality profile:

  | Rule | Ngưỡng | Priority |
  |---|---|---|
  | S06 môn/lớp/ngày | ≤ 2 | P1 |
  | S02 tải GV/buổi | ≤ 4 | P1 |
  | S03 tải GV/ngày | ≤ 5 | P2 |
  | S09 chuỗi tiết trống | ≤ 1 | P2 |
  | S05 giãn ngày | ≥ 1 | P2 |
  | S08, S11 | chỉ ghi nhận | P3 |

- Khung tiết mặc định gồm mọi thứ có trong lịch × mọi buổi × tiết 1 đến tiết lớn nhất của buổi đó.
  Dùng `--frame` nếu trường có tiết trống không xuất hiện trong lịch.

## Giới hạn đã biết

- Số tiết và tiết đôi suy từ chính lịch thật (RD4), nên lịch thật luôn đủ tiết theo cách tính này.
- Không có nguyện vọng hay ô "không thể dạy" của GV, trừ khi trường cung cấp.
- Mỗi trường chạy n = 1.

## Kiểm thử

```bash
uv run --extra solver python -m pytest tools/real_data/tests
```

Có một test trọn vòng: lịch do Core xếp → xuất thành "file của trường" → chuyển ngược phải ra đúng các
tiết.
