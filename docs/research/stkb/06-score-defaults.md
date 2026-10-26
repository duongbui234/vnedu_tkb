# STKB: 30 hệ số của CAlgAutoSFNew

Ngày 2026-10-26. **VERIFIED**: mapping getter → byte offset → hệ số được ghi trong constructor `CAlgAutoSFNew(CWnd*, int)` VA `0x6bdf00`, cùng hash STKB.exe trong [README](README.md). Kiểm tra tự động cả 30 getter với assembly: `reverse-engineering/reports/full-study/evidence/map_score_defaults.py`, kết quả `score-defaults.json`; mỗi getter có REA Evidence JSON và pseudocode trong `evidence/criteria/`. `score-initialize.objdump.txt` giữ các store tại VA ghi trong bảng.

Đây là hệ số nội bộ của một engine và một tuyến constructor; **UNKNOWN** giá trị có bị ghi đè bởi cấu hình/runtime/engine 2b khác không. Không phải constraint IDs, không phải bảng định mức môn, không phải thang hard/soft. Getter có thể dùng hệ số trong biểu thức phi tuyến/phép chia integer; ví dụ `GetValue_MotCap` có nhánh chia hệ số. Vì vậy không nhập nguyên các số này làm trọng số CP-SAT. Một hệ số lớn không chứng minh hard constraint.

| Function | VA | this + byte offset | Constructor value | Write VA |
|---|---|---|---:|---|
| GetValue_MotCap | 0x6c4170 | 0x74b304 | 300 | 0x6be131 |
| GetValue_HocCuoiTuan | 0x6c4250 | 0x74b334 | 2 | 0x6be1bd |
| GetValue_Nghi | 0x6c4300 | 0x74b2d4 | 30 | 0x6be0c3 |
| GetValue_Hop | 0x6c4440 | 0x74b2d0 | 1000 | 0x6be0b9 |
| GetValue_Ban | 0x6c4580 | 0x74b2d8 | 5 | 0x6be0cd |
| GetValue_Hanche | 0x6c46c0 | 0x74b2dc | 2 | 0x6be0d7 |
| GetValue_HaiCap | 0x6c4800 | 0x74b308 | 200 | 0x6be13b |
| GetValue_ChiMotTiet | 0x6c48d0 | 0x74b30c | 300 | 0x6be145 |
| GetValue_QuaHaiTiet | 0x6c49a0 | 0x74b310 | 300 | 0x6be14f |
| GetValue_CachMon | 0x6c4a80 | 0x74b2c0 | 300 | 0x6be1d1 |
| GetValue_KhongHocTiet5 | 0x6c4b40 | 0x74b314 | 60 | 0x6be159 |
| GetValue_TrongTietGiua | 0x6c4c10 | 0x74b2c4 | 60 | 0x6be1db |
| GetValue_KhongHocTiet45 | 0x6c4d20 | 0x74b318 | 30 | 0x6be163 |
| GetValue_KhongHocTiet1 | 0x6c4e90 | 0x74b31c | 60 | 0x6be16d |
| GetValue_KhongHocTiet12 | 0x6c4f60 | 0x74b320 | 30 | 0x6be177 |
| GetValue_HocCachNgay | 0x6c50d0 | 0x74b324 | 5 | 0x6be181 |
| GetValue_HocCachHaiNgay | 0x6c51b0 | 0x74b328 | 2 | 0x6be18b |
| GetValue_ChiHocTiet1 | 0x6c5290 | 0x74b338 | 10 | 0x6be195 |
| GetValue_ChiHocTiet5 | 0x6c5330 | 0x74b33c | 10 | 0x6be19f |
| GetValue_ChiHocTiet1Hoac5 | 0x6c53d0 | 0x74b32c | 10 | 0x6be1a9 |
| GetValue_HocDauTuan | 0x6c5460 | 0x74b330 | 2 | 0x6be1b3 |
| GetValue_MaxTietBuoi | 0x6c5510 | 0x74b2e0 | 5 | 0x6be0e1 |
| GetValue_MaxTietNgay | 0x6c55b0 | 0x74b2e4 | 3 | 0x6be0eb |
| GetValue_MaxEmpty | 0x6c56b0 | 0x74b2e8 | 100 | 0x6be0f5 |
| GetValue_TotalEmpty | 0x6c5880 | 0x74b2ec | 4 | 0x6be0ff |
| GetValue_FromT1toT2 | 0x6c5a40 | 0x74b2f0 | 4 | 0x6be109 |
| GetValue_SoBuoiNghi | 0x6c5bd0 | 0x74b2f4 | 30 | 0x6be113 |
| GetValue_SoNgayNghi | 0x6c5e20 | 0x74b2f8 | 20 | 0x6be11d |
| GetValue_ChiDayNgay | 0x6c60a0 | 0x74b2fc | 30 | 0x6be127 |
| GetValue_ChiCoMotTiet | 0x6c6160 | 0x74b300 | 20 | 0x6be1c7 |

## 15 selector thuộc tính môn đã nối với getter

**VERIFIED — phạm vi call site:** các getter dưới đây truyền selector tương ứng cho `CAlgorithmBase::LopCoTCM`, VA `0x6d08f0`. Đối chiếu literal push và đích call trong assembly, cùng REA pseudocode. Evidence `subject-property-selectors.json`; helper `map_score_defaults.py` có assert đủ1..15. Đây là mã thuộc tính ở một API nội bộ, không phải mã vnEdu hoặc mọi ID ràng buộc toàn phần mềm. Ngữ nghĩa sư phạm chi tiết phải đọc body và policy, không chỉ tên hàm.

| Selector | Getter | VA |
|---:|---|---|
| 1 | GetValue_MotCap | 0x6c4170 |
| 2 | GetValue_HaiCap | 0x6c4800 |
| 3 | GetValue_ChiMotTiet | 0x6c48d0 |
| 4 | GetValue_KhongHocTiet5 | 0x6c4b40 |
| 5 | GetValue_KhongHocTiet45 | 0x6c4d20 |
| 6 | GetValue_KhongHocTiet1 | 0x6c4e90 |
| 7 | GetValue_KhongHocTiet12 | 0x6c4f60 |
| 8 | GetValue_HocCachNgay | 0x6c50d0 |
| 9 | GetValue_ChiHocTiet1 | 0x6c5290 |
| 10 | GetValue_ChiHocTiet5 | 0x6c5330 |
| 11 | GetValue_QuaHaiTiet | 0x6c49a0 |
| 12 | GetValue_HocCachHaiNgay | 0x6c51b0 |
| 13 | GetValue_ChiHocTiet1Hoac5 | 0x6c53d0 |
| 14 | GetValue_HocDauTuan | 0x6c5460 |
| 15 | GetValue_HocCuoiTuan | 0x6c4250 |

**VERIFIED binary:** `LopCoTCM` kiểm cờ trực tiếp và có nhánh tra theo nhóm; còn có nhánh selector29/30. **UNKNOWN:** tên/ngữ nghĩa đầy đủ29/30, mọi nguồn setter/UI/file index, xung đột precedence giữa từng loại constraint và chế độ2b/2B. Không gọi bảng15selector là full mapping toàn ứng dụng. Pseudocode complete của query giữ ở `evidence/subject-property-query.json/.pseudo.txt`.
