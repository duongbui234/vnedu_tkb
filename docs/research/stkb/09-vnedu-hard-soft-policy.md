# Bộ ràng buộc đề xuất vnEdu — policy 0.1

Ngày 2026-10-26. **INFERRED — chốt phương án đề xuất để thiết kế và review**, chưa phải chính sách đã được nhà trường phê duyệt, chưa triển khai vào Core. Snapshot code đối chiếu: `7f58f710a9901fe2c0457573feaad272e713d7a1`.

Phương án chọn: **hard cho tính hợp lệ và điều kiện bắt buộc đã xác nhận; soft có đơn vị phạt rõ cho nguyện vọng/chất lượng; dữ liệu mơ hồ phải được giải quyết trước khi bật rule**. Không lấy “STKB có thể phá yêu cầu” làm lý do nới occupancy, demand hoặc khóa của sản phẩm mới.

## 1. Căn cứ đã xác minh

| Evidence | VERIFIED, phạm vi cụ thể |
|---|---|
| E1 — [Demand/lịch thực](07-file-demand-recovery.md), [suffix](08-suffix-constraints-and-locks.md) |8 file đọc tớiEOF. MOISH đủ 488 tiết nhưng có25 tiết trên ô GV mã998 và13 buổi vượtmax; MOI19/TKB199/DOT2 có 27 và16. Không dùng đủ tiết làm bằng chứng đạt mọi yêu cầu. |
| E2 — binary STKB, hash tại [README](README.md) |997Hạn chế: `GetValue_Hanche:0x6c46c0`;998Nghỉ:`GetValue_Nghi:0x6c4300`;999Bận:`GetValue_Ban:0x6c4580`; Họp1000..1006:`Common.dll!CSCN::IsHop:0x100073c0`. Chưa biết nghĩa chi tiết mọi mã họp. |
| E3 — thuộc tính GV và khóa |Reader`0x443310`, `IsLocking:0x6bca20`;96byte/GV, cờmax/buổi+1 và limit+24, cờmax/ngày+2 và limit+28; `GetValue_MaxTietBuoi:0x6c5510`, `MaxTietNgay:0x6c55b0`, `FromT1toT2:0x6c5a40`.8 file không có explicit slot lock dương; chưa runtime-check auto-lock SH/cặp. |
| E4 — FET7.12.0 |`ConstraintBasicCompulsoryTime`, `timeconstraint.cpp:9447`; `BasicCompulsorySpace`, `spaceconstraint.cpp:2999`; min-days`timeconstraint.cpp:11729`/`generate.cpp:10635`; maxhoursdaily`timeconstraint.cpp:13695`; gaps`timeconstraint.cpp:15724`. FET có semantics/penalty unit s riêng; [catalogue](../fet/03-constraint-catalog.md) dẫn đầy đủ. |
| E5 — Phase 1 source |`check_capabilities`, `contracts/capabilities.py:7–28`: mọi custom rule enabled đều reject. `build_model`, `solver/model_builder.py:19–31`: ExactlyOne+occupancy. `solve`, `solver/cp_sat.py:27–28`: feasibility, chưa objective/repair. |
| E6 — API đã cung cấp |[API observations](../vnedu-api-live-observations.json):527 PCGD so_tiet đều chuỗi0, đơn vịUNKNOWN;5 tham chiếu GV thiếu;38 record môn -2 chủ nhiệm. Không phải bảng định mức đã xác nhận. |

Các lựa chọn H/S bên dưới là **INFERRED — policy thiết kế mới**, không tuyên bố tương đương STKB/FET. Các tham số của trường còn UNKNOWN không được lấp bằng hằng đoán.

## 2. Cổng dữ liệu — không phải hard constraints của solver

| ID | Điều kiện trước solve |
|---|---|
| G01 |Mỗi demand có nguồn, đơn vị/cycle và trạng thái đã xác nhận; unknown khác confirmed-zero. Không tự lấy so_tiet0→0/1, không lấy lịch cũ thiếu tiết làm tổng chuẩn. |
| G02 |Danh mục/namespace GV, lớp/môn/phòng và snapshot nhất quán. Chưa phân GV/IDmất phải báo riêng, không tạo GV giả hoặc gắn giáo viên bất kỳ. |
| G03 |Calendar/break/cycle và split đã chốt, tổng duration=confirmed demand. Số1.5trungbình không thành activity duration 0.5; cần phân phối tuần/học kỳ nguyên. |
| G04 |Rule được bật có threshold/unit/scope/hard-soft, precedence đã giải quyết; dữ liệu mơ hồ chưa đủ để compile. Cờ disabled không có nghĩa ngưỡng 0bắt buộc. |
| G05 |Capability guard được giữ. Schema có field/rule không đồng nghĩa model+validator đã enforce. Lock từ snapshot/split cũ phải remap hoặc báo stale. |

Owner: application/input compiler tương lai. Core tiếp tục nhận demand đã chốt; không cần nhúng curriculum hoặc vnEdu HTTP vào solver. Policy0.1 là phiên bản tài liệu/manifest, **không phải** `ScheduleInput.schema_version` mới đã tồn tại.

## 3. Bộ hard đề xuất

“Luôn” nghĩa luôn trong phạm vi capability đã hỗ trợ. “Khi xác nhận” nghĩa chỉ áp dụng khi có dữ liệu/policy tương ứng; không có default ngầm.

| ID | Hard rule và cách bật | Đơn vị/scope; đối chiếu Phase 1 |
|---|---|---|
| H01 |Đủ đúng demand, mỗi occurrence đúng 1 lần — luôn |Theo requirement/cycle, cộng duration. ĐÃ ĐỦ cho tổng/split xác định; E1/E5. Không bỏ tiết để giảm softcost. |
| H02 |Đúng lớp/môn/GV phân công — luôn |Participants của requirement, không tự chọn GV. ĐÃ ĐỦ một GV+mộtlớp; multi-participant cần đổi đồng bộ. |
| H03 |Không trùng GV hoặc learner resource — luôn |Toàn footprint, cùng thời gian vật lý. ĐÃ ĐỦ cho atomicclass; subgroup chồng lấn chưa có. |
| H04 |Không trùng phòng thật khi có dùng phòng — luôn |RoomID+footprint. ĐÃ ĐỦ trong quản lý phòng đã bật; roomnull không là phòngảo. |
| H05 |Đúng calendar và khoảng **không thể** học/dạy — luôn |Toàn block, availability của từng resource. ĐÃ ĐỦ sau khi upstream biên dịch. Mã998/999 không tự là hard availability. |
| H06 |Đúng duration/continuity của block đã chốt — luôn |Blockđôi cùngday/session,2 tiết; timedblock hiện cần end=start, không qua gap. ĐÃ ĐỦ 1/2; không đồng nhất “thích một cặp” với block 2 bắt buộc. |
| H07 |Giữ explicit lock đã xác nhận — khi có |Khóa start và/hoặcroom độc lập. ĐÃ ĐỦ ở occurrence; auto-locktheoSH/lớp/GV chưa được compile tự động. |
| H08 |Phòng bắt buộc phải có, đúngtype/capacity/availability — khi yêu cầu |ĐÃ ĐỦ với metadata hiện tại. Không bắt mọi môn có phòng; equipment/campus/eligibilitychi tiết chưa có. |
| H09 |Họp/sự kiện bắt buộc không được chồng tài nguyên tham gia — khi xác nhận |Họp có thể compile thành teacherunavailability hiện có. Sự kiện tập thể có nhiều participant/không GV cần mô hình mở rộng; không chặn mọi GV chỉ vì một mã họp. |
| H10 |Giới hạn tải/ngày/buổi, môn/ngày, spacing **bắt buộc** — chỉ trường xác nhận |Ngưỡng và unit được chọn rõ. CHƯA CÓ custom rule. Không tự nâng max/buổi đang là nguyện vọng từ STKB thành hard. |
| H11 |Đủ thời gian di chuyển giữa điểm trường — khi travel thực sự bắt buộc |Minute-based transition theo resource+location. CHƯA CÓ; không coi occupancy không trùng là đã đủtravel. Thiếu dữ liệu thì chưa chứng nhận travel-valid. |
| H12 |Quota theo buổi/tuần, fixed event, membership lớpghép/tách đúng chính sách — khi yêu cầu |MỘT PHẦN qua requirement/availability/locks; jointquota/multiweek/subgroups chưa có. Không ép tất cả trường dùng mô hình 2 B hoặc 10 tiết/ngày. |

H01–H08 không được tự nới khi timeout/infeasible. H09–H12 cũng không được tự nới sau khi đã xác nhận là hard. Chẩn đoán relax phải là chế độ riêng, không publish kết quả như lịch hợp lệ. Hard không được biểu diễn bằng một weight rất lớn.

## 4. Bộ soft và đơn vị phạt

Tất cả rule dưới đây **chỉ bật khi có cấu hình đã xác nhận**, mặc định không tự sinh ngưỡng. Profile đề xuất chia3 mức ưu tiên; trong cùng mức, khởi đầu weight=1theo đơn vị đã ghi. Đây là lựa chọn thiết kế, chưa được hiệu chỉnh bằng benchmark/đánh giá giáo vụ. Có thể đổi weight trong phiên bản profile mới, không lấy30 hệ số STKB hoặc95% FET.

Đây là mặc định kích hoạt của **policy tương lai**, không phải thay đổi giá trị `enabled=True` trong Pydantic hiện tại. Phase 1 vẫn phải từ chối custom rule bật. Không dùng `enabled=False` để bỏ preference rồi báo đã áp đủ policy 0.1; nếu chỉ chạy feasibility Phase 1, phải ghi rõ phạm vi đó.

| ID | Soft rule | Mức | Penalty được chốt | Kích hoạt/gap |
|---|---|---|---|---|
| S01 |Ưu tiên không dạy trên ô muốn Nghỉ |P1|Số tiết dạy của GV nằm trên các ô đã chọn; duration 2 có thể phạt 2 |Mã998 sau review→candidate S01; CHƯA CÓ soft compiler/evaluator. |
| S02 |Không vượt tải thoải mái/buổi |P1|`sum(max(0,load_session−limit))` theo GV+ngày+buổi |Dùng flag/limit từng GV, không default 3 cho toàn trường; CHƯA CÓ. |
| S03 |Không vượt tải thoải mái/ngày |P1|`sum(max(0,load_real_day−limit))`, cộng đúng 2 buổi |Chỉ khi bật và có limit; CHƯA CÓ. Không dùng đơn vị “số ngày vi phạm” của FET thay số tiết vượt. |
| S04 |Dạy trong khung tiết mong muốn |P1|Số tiết dạy nằm ngoài khoảng inclusive[start,end] của GV+buổi |Không phải giới hạn start đơn thuần; CHƯA CÓ. |
| S05 |Phân bố components qua ngày |P1|Mỗi unordered pair component trong explicit group: `max(0,k−abs(day_i−day_j))` ngày thiếu |k và group phải có; không tự gom mọi activity cùng tên môn; CHƯA CÓ. Không thêm consecutive/cap cùng ngày ngầm theo FET. |
| S06 |Giảm dồn một môn trong ngày |P1|Số tiết vượt max của class+subject+realday |Chỉ cấu hình riêng; không hardcode 2 tiết/ngày; CHƯA CÓ. |
| S07 |Hạn chế dạy ở các ô ít ưu tiên |P2|Số tiết dạy ở ô Hạn chế đã xác nhận |Mã997→candidate S07; CHƯA CÓ. Cùng GV/slot không tính lặp S01 và S07. |
| S08 |Giảm tổng gap nội bộ của GV |P2|Tổng số tiết idle theo định nghĩa bên dưới |CHƯA CÓ. Phân biệt objective tổng gap với threshold max gap. |
| S09 |Giới hạn chuỗi gap lớn nhất |P2|Theo GV+day+session: `max(0,longest_idle_run−limit)` |Có limit mới bật; CHƯA CÓ. Không phạt bằng số buổi vi phạm thay số period vượt. |
| S10 |Đạt số buổi/ngày nghỉ mong muốn |P2|`max(0,target_free−actual_free)` tính riêng theo unit đã chọn |Không bật cả hai chỉ vì cùng tên; eligible calendar/cycle rõ; CHƯA CÓ. |
| S11 |Tránh GV chỉ dạy 1 tiết trong buổi |P2|1 cho mỗi GV/day/session có teaching load=1 |CHƯA CÓ; không áp lên học sinh/lớp hoặc phạt buổi trống. |
| S12 |Ưu tiên phòng/đầu-cuối buổi/môn đặc thù |P3|Mỗi rule instance chỉ một preference: room cost theo occurrence, time cost theo tiết dạy |Chỉ bật instance có semantics/unit riêng; không bật nhóm S12 mơ hồ; CHƯA CÓ. Required room vẫn hard. |

**Định nghĩa gap đề xuất:** xét từng GV/realday/session, chỉ giữa tiết dạy đầu và cuối. Ô calendar không giảng dạy không được tính gap và cắt chuỗi; ô họp bắt buộc đã xác nhận là occupied work, không là idle, nhưng không cộng vào teaching load. Ô GV không thể dạy vẫn là gap nếu là school tiết dạy, nằm giữa hai tiết dạy và không có occupied work; có thể gây lịch không đẹp nhưng không cho xếp vào. Cần cùng calendar/occupied work cho compiler và evaluator độc lập; không gọi `available_slot_ids` của Phase 1 đủ để tự suy hết semantics này.

**Không đếm trùng do kế thừa:** cùng rule/effective scope không giữ bản sao trường+nhóm+GV như 3 penalties. Đếm đồng thời S02 và S03 chỉ khi thực sự chọn 2 mục tiêu khác nhau; policy summary phải hiển thị điều đó. Những preference khác nhau vẫn có thể cộng penalty trong cùng tier, đây là trade-off minh bạch.

**Khoảng cách ngày của S05:** dùng thứ tự ngày thực trong cycle đã xác nhận, tính tuyến tính; không tự thêm điều kiện vòng tuần hoặc dùng half-day thay ngày. Split `[2,1,1,1]` tạo 4 components và 6 cặp, không phải 5 tiết đơn và 10 cặp. Block đôi vẫn chiếm 2 tiết khi tính tải và gap. Quy tắc qua ranh giới tuần cần một policy được xác nhận riêng.

## 5. Quyết định chuyển mã STKB sang policy

| Nguồn STKB | Quyết định đề xuất | Điều kiện bảo vệ |
|---|---|---|
|998Nghỉ|Soft S01/P1 sau khi chọn dùng nguyện vọng |Nếu giáo vụ xác nhận đây là không thể dạy thật, chuyển H05 và bỏ S01 cho cùng ô; không tự đổi chỉ vì nghĩa tiếng Việt. |
|997Hạn chế|Soft S07/P2 sau review |Không lấy weight 2 STKB hay probability FET. |
|999Bận|**Chưa tự phân loại** từ raw code |Phải xác nhận “bắt buộc không dạy”→H05 hoặc “mong muốn tránh”→S01. Chặn compile phần chưa xác nhận, không im lặng bỏ. |
|1000..1006Họp|Candidate H09 |Phải biết lịch họp và đúng GV tham gia; chưa biết mọi subcode thì giữ raw+mapping pending. |
|Slot lock=1|Candidate H07 |Chỉ khi nối được sang occurrence/start/room của snapshot và split đúng; không khóa cả calendar chỉ từ index. |
|Slot lock=0|Không thêm explicit lock này |Không phủ định auto-lock SH/cặp hoặc khóa cấp đối tượng; nếu chức năng đó chưa hiểu thì chưa quảng cáo import đầy đủ locking policy. |
|Max/buổi/max/ngày flag bật|Soft S02/S03 theo GV đã review |Threshold lưu 0 khi flag tắt không có hiệu lực. Nếu flag bật và limit 0 thì giữ 0 rõ ràng, không tự bỏ rule; có thể mâu thuẫn demand nếu nâng hard. |
|15 selector thuộc tính môn|Giữ raw và map từng semantics |Không biến MotCap/HaiCap thành split cứng hoặc mọi cặp component cần cách ngày chỉ từ tên getter. |

Không có API ghi hoặc adapter được triển khai trong policy này. Nguồn demand ưu tiên cấu hình/phân công đã xác nhận của snapshot được chọn; API so_tiet tiếp tục UNKNOWN. Không hợp nhất số tiết 505/488/506 của các file thành một bài toán.

## 6. Precedence và nghiệm thu kết quả

**Quyết định đề xuất:** hard physical/admin đã xác nhận luôn giữ; cấu hình cá nhân không vô hiệu hóa hard cấp trường. Các hard còn lại đồng thời áp dụng: xung đột thì báo, không tự chọn min/max để giấu lỗi. Với **cùng một preference**, chọn cấu hình explicit của đối tượng nếu có; nếu không, kế thừa cấu hình nhóm rồi trường. Nhiều nhóm cùng áp dụng mà khác giá trị phải được resolve trước compile. Product setting tương lai cần phân biệt inherit/disabled/configured; raw flag 0 không chứng minh người dùng đã chủ động tắt rule cấp trường.

Sinh lịch mới: tìm đủ demand và hard-valid trước, rồi giảm vector `(P1,P2,P3)` theo thứ tự. Solve từng tier; chỉ khóa optimum của tier trước khi đã chứng minh, nếu hết budget thì trả incumbent hợp lệ cùng quality status chưa optimal. Không hứa lexicographic optimum khi tier trước chỉ FEASIBLE. Weight 1 ở cùng tier cho phép đánh đổi theo unit đã chốt, không là chuẩn chất lượng phổ quát.

Repair tương lai: đề xuất `(P1, số occurrence đổi, P2, P3)` sau hard locks để có thể sửa vi phạm nguyện vọng mạnh mà không hy sinh hard. Đây là quyết định thiết kế cho Phase 3, không implementation đang có. Không tự giữ mọi slot cũ như hard lock; chỉ locks người dùng xác nhận mới là hard.

Result phải tách: input completeness, demand completion, hard violations, preference breakdown và solver status. Một lịch đủ tiết có P1 > 0 được ghi “hard-valid, còn nguyện vọng chưa đạt” **chỉ sau** independent hard validation; không gọi OPTIMAL ở feasibility model là lịch đẹp nhất. Unsupported rule hoặc unknown policy không được gộp thành INFEASIBLE.

## 7. Đưa vào Phase 2 theo thứ tự nào?

1. Chốt registry và typed parameters/unit/effective scope, output quality status/breakdown và evaluator độc lập. SoftConstraintConfig hiện chỉ có weight, chưa có tier/priority contract; cần quyết định version trước khi thêm field. Không gửi policy 0.1 như unknown field vào ScheduleInput 1.0.
2. Nhóm đầu: S01/S02/S03/S04 và hard variants tương ứng **khi bật explicit**. Dùng ngưỡng synthetic và số đếm quan sát làm case đối chiếu; không đưa PII/file thật vào fixtures.
3. Thêm S05/S06, sau đó S07–S11 và S12 từng instance có use case. Giữ H01–H08 và capability guard trong mọi giai đoạn; không bật full catalogue FET.
4. Travel/multiweek/multi-participant/quota 2B mở theo nhu cầu đã xác nhận, cùng contract+prepare+model+validator; repair làm sau baseline quality và identity mapping.

**Tiêu chí kiểm chứng tương lai:** N=5 split[2,1,1,1] vẫn đủ 5; busy hard không được chiếm; nghỉ soft có thể vi phạm và penalty đúng duration; flag tắt+limit 0 không phạt; flag bật+load 4 limit 3 phạt 1; max day cộng 2 buổi; block 2 không lọt time window qua phần start; min-days không tự thêm consecutive; gaps loại break/meeting theo định nghĩa; stale/unsupported/conflicting policies bị từ chối; validator/score evaluator độc lập tái tính. Đây là case đề xuất, **chưa có tests Phase 2 được viết/chạy trong lượt này**.

## 8. Phạm vi kiểm tra lượt chốt tài liệu

Đối chiếu source Phase 1 và bằng chứng nghiên cứu đã lưu; kiểm tra liên kết, mã rule và diff tài liệu. Không sửa Core, source FET, binary/file STKB gốc; không gọi API hoặc chạy REA mới. Không chạy pytest hoặc benchmark trong lượt chỉ cập nhật tài liệu này; các trường hợp nghiệm thu ở trên là yêu cầu cho bước triển khai tiếp theo.
