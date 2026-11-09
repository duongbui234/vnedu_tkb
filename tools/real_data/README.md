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

**Ô được học của lớp** (tùy chọn, `--class-cells`): CSV `lop,thu,buoi,tiet`, mỗi dòng là một ô lớp đó
được học. Khi có file này, mỗi lớp chỉ được xếp vào các ô của nó (`available_slot_ids`), và mọi tiết
trong lịch thật phải nằm trong ô của lớp. Không có file thì mọi lớp dùng cả khung tiết, nên Core có thể
được xếp vào buổi mà lớp thật không học; khi đó phép so với lịch thật không công bằng.

**Ô của giáo viên và tiết khóa** (tùy chọn): `--teacher-cells` là CSV `ma_gv,thu,buoi,tiet,loai`, với
`loai` là `hop`, `nghi`, `ban` hoặc `hanche`; `--locks` là CSV `ma_gv,thu,buoi,tiet`.

- Loại nằm trong `--teacher-hard` (mặc định `hop`) bị bỏ khỏi `available_slot_ids` của GV.
- Các loại đã biết còn lại thành một rule mềm `TEACHER_AVOID_SLOTS` (S01) cho mỗi GV, priority 2. Lịch
  thật và lịch Core được chấm cùng rule này.
- Mỗi ô khóa khóa tiết chứa nó, tại ô bắt đầu của block. Nếu ô khóa trùng ô hard thì giữ khóa: ô đó vẫn
  mở cho GV, và báo cáo có đếm.
- `--avoid-priority` (mặc định 2) đổi priority của rule `TEACHER_AVOID_SLOTS`.

**Giới hạn tải của GV theo trường** (tùy chọn, `--teacher-limits`): CSV
`ma_gv,max_tiet_buoi,max_tiet_ngay`, ô trống nghĩa là trường không bật giới hạn đó. Khi có file này, S02
và S03 của thang chung được thay bằng giới hạn của trường. GV có bật giới hạn thì có rule đúng mức đó; GV
không bật thì không có rule. Các rule khác giữ nguyên thang chung.

**Khung tiết của GV** (tùy chọn, `--teacher-windows`): CSV `ma_gv,buoi,tu_tiet,den_tiet`, mỗi dòng là
một khung đã bật trong STKB (GV chỉ nên dạy từ tiết `tu_tiet` đến `den_tiet` của buổi đó). Mỗi GV có
khung thêm một rule `TEACHER_AVOID_SLOTS` (id `S01K-<GV>`) phủ các ô của buổi đó nằm ngoài khung, cùng
priority với `--avoid-priority`. Khung phủ cả buổi (1–5) không sinh rule. Ô đã có trong rule S01 của GV
(Nghỉ/Bận/Hạn chế mềm) được bỏ khỏi S01K để không bị phạt hai lần (`cells_also_avoided` trong báo cáo).

## Lấy dữ liệu từ STKB

Chỉ dùng khi người dùng yêu cầu rõ (dữ liệu thật). File và chỉ mục đặt dưới `benchmarks/artifacts/real/`.

```bash
# Quét danh sách file TKB của từng trường (truongTrueLifeId = base64(site_id)); chỉ giữ metadata file
uv run python -m tools.real_data.stkb_api scan --sites docs/site_ids_base64_mapping.csv \
    --years 2023-2026 --output benchmarks/artifacts/real/api/tkb_index.json
# Tải tối đa N file, mỗi trường file mới nhất trước
uv run python -m tools.real_data.stkb_api download benchmarks/artifacts/real/api/tkb_index.json \
    --limit 50 --output benchmarks/artifacts/real/api/files
# .STKB -> <trường>/tkb.csv, class-cells.csv, teacher-cells.csv, locks.csv, teacher-limits.csv,
# teacher-windows.csv
# (GV thành GV###, không lưu bảng đối chiếu tên)
uv run python -m tools.real_data.stkb_to_csv benchmarks/artifacts/real/api/files/*.STKB \
    --output benchmarks/artifacts/real/stkb-v3
```

`stkb_to_csv` dùng bộ đọc nghiên cứu trong `reverse-engineering/scripts` (chỉ đọc). Ô được học của một
lớp là mọi ô của các (thứ, buổi) mà lớp có ít nhất một tiết, trừ ô STKB đánh dấu bằng mã không phải môn
(254/255; nghĩa còn UNKNOWN). Tên lớp trùng nhưng mã lớp khác nhau thì file bị từ chối, không gộp.

Ô của GV và cờ khóa lấy từ phần cuối file (mã theo
[báo cáo 08](../../docs/research/stkb/08-suffix-constraints-and-locks.md): 1000–1006 Họp, 998 Nghỉ,
999 Bận, 997 Hạn chế). Nếu không đọc được phần cuối file thì không ghi `teacher-cells.csv` và
`locks.csv`, và `summary.json` ghi rõ lý do.

Giới hạn tải GV lấy từ record thuộc tính 96 byte của GV (báo cáo 08 §4). Byte +1 bật max tiết/buổi,
giá trị là i32 tại +24. Byte +2 bật max tiết/ngày, giá trị tại +28. Giới hạn không bật được ghi trống,
dù file có lưu giá trị.

Khung tiết GV cũng lấy từ record này: byte +3 bật khung buổi sáng (tiết đầu, tiết cuối là i32 tại +32,
+36), byte +4 bật khung buổi chiều (+40, +44). Nghĩa đã đối chiếu trên binary: `GetValue_FromT1toT2`
(0x6c5a40) cộng một hệ số phạt cho mỗi tiết GV dạy ngoài khung, và trả 0 khi cờ tắt. Ghi vào
`teacher-windows.csv`; chỉ giữ khung bật với 1 ≤ đầu ≤ cuối ≤ 5. Các trường khác của record chưa được
xuất.

## Chạy

```bash
# 1. Chuyển sang input Core và lịch thật dạng assignment (không ghi đè thư mục có sẵn)
uv run python -m tools.real_data.convert_real benchmarks/artifacts/real/SCH01/tkb.csv \
    --output benchmarks/artifacts/real/SCH01/conv --school SCH01 [--frame khung_tiet.csv]

# 2. Kiểm hard và chấm lịch thật bằng evaluator độc lập
uv run python -m tools.real_data.score_real benchmarks/artifacts/real/SCH01/conv

# 3. Cho Core xếp cùng input rồi so (budget 60/120/180 s theo số lớp, 1 worker, seed 42)
uv run --extra solver python -m tools.real_data.compare_real benchmarks/artifacts/real/SCH01/conv \
    --output benchmarks/artifacts/real/SCH01/cmp [--workers 8] [--time-limit 180] [--warm-start]

# 4. Nhiều trường × nhiều mức worker, chạy song song lấp đầy CPU; ghi cách bố trí vào layout.jsonl
# (nhiều thư mục gốc dùng chung một bộ xếp lịch)
uv run --extra solver python -m tools.real_data.run_batch benchmarks/artifacts/real/stkb-v3-hard \
    benchmarks/artifacts/real/stkb-v3-soft --workers 2,4 --time-limit 180
```

`--warm-start` (chẩn đoán) cho Core xuất phát từ lịch thật qua `warm_start.py`: bước tìm lời giải hợp lệ
đầu tiên được thay bằng lịch thật; Core vẫn kiểm hard, chấm độc lập rồi tối ưu từng mức từ đó. Không sửa
code Core; bản vá chỉ tồn tại trong tiến trình đó.

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
