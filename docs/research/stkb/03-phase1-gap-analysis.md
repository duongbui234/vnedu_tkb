# Gap Analysis — Scheduling Core Phase 1

> Đặc tả tiếp nối: [Phase 2A — registry, ưu tiên và independent score evaluator cho S01–S04](../../superpowers/specs/2026-10-26-phase-2-quality-design.md). Đây là đề xuất thiết kế; các mức hỗ trợ Phase 1 bên dưới chưa thay đổi. Hard variants được tách sang mốc 2B, chỉ triển khai sau yêu cầu và review riêng.

> Chính sách đề xuất mới nhất: [policy0.1 — hard/soft](09-vnedu-hard-soft-policy.md). Bảng35mục bên dưới mô tả implementation Phase1, không phải danh sách rule đã được bật từ policy.

> Cập nhật từ [báo cáo08](08-suffix-constraints-and-locks.md): đã đọc hết8file, map explicit slotlock và một số yêu cầuGV. Khả năng nhập cấu hình vẫn chưa có trong Core. Dữ liệu thực có đủ demand nhưng vẫn vi phạm Nghỉ/max-buổi; không chuyển các yêu cầu này thành hard availability/limit một cách mặc định. Predicate khóa đã map, song8file không có cờ khóa dương, và auto-lock SH/cặp vẫn chưa đối chứngruntime.

Ngày: 2026-10-26. Nguồn trực tiếp: toàn bộ `src/tkb_core/` liên quan contracts, normalize, feasibility, hard model, solve, independent validator, CLI; thiết kế/báo cáo Phase 1; FET source đã dẫn trong báo cáo cùng thư mục; API evidence đã lưu. Đối chiếu implementation bằng đọc source; không sửa Core. Đây là nghiên cứu/đề xuất, không thực hiện phase tiếp theo.

## Cách đọc và ranh giới

**VERIFIED** dưới đây nghĩa đã đọc source/tài liệu được dẫn, không phải kiểm thử mới hay xác minh nghiệp vụ trường thật. **INFERRED** là kiến nghị từ đối chiếu. **UNKNOWN** là dữ kiện còn thiếu. Nhãn độ phủ của một hàng được tính theo mục tiêu cụ thể của hàng, không phải đánh giá toàn sản phẩm:

- **ĐẦY ĐỦ / full:** có implementation cho semantics đã nêu trong phạm vi Phase 1.
- **MỘT PHẦN / partial:** có nền tảng nhưng thiếu các nhánh cần để đạt toàn luồng.
- **CHƯA CÓ / absent:** không có implementation cho nghiệp vụ đó; contract placeholder không tính là đã hỗ trợ.
- **CẦN ĐỔI / change-required:** implementation hiện tại chủ động giới hạn hoặc có semantics khác mục tiêu mở rộng; cần thay đổi đồng bộ khi yêu cầu được duyệt, không chỉ bật cấu hình.
- **CHƯA BIẾT / unknown:** nguồn đầu vào/chính sách chưa đủ để xác định ánh xạ đúng.

Core chỉ nhận **caller-confirmed demand** (`domain/models.py:90`), không sở hữu chương trình môn học, tải phân công, xác thực vnEdu hay persistence cấu hình. Một khả năng CHƯA CÓ ở upstream không phải bug của Phase 1. Tương tự, khả năng bị từ chối rõ là giới hạn được thiết kế, không phải âm thầm thực thi thiếu.

## Luồng từ khởi tạo đến sử dụng lịch

**INFERRED — kiến trúc nghiệp vụ đích:**

`Nguồn danh mục/PCGD → snapshot init → xác minh định mức + override → cấu hình split/calendar/rules → demand đã xác nhận → occurrences → domain/prechecks → hard solve → independent validation → bản nháp/version → giáo vụ sửa/khóa → repair → đối soát/export`.

Các mục trước demand thuộc adapter/application/configuration. Occurrences, placements, constraints, solve/validate thuộc core. Draft/history/sync thuộc application + storage adapters. Không để solver tự biết `so_tiet` hay MySQL/vnEdu.

## Ma trận gap theo nghiệp vụ

Mọi path `src/tkb_core/...` trong bảng là tương đối repository; tên function/class là vị trí đọc trực tiếp. Test dẫn là source evidence về coverage dự kiến, không tuyên bố đã chạy trong nghiên cứu này.

| # | Mục tiêu nghiệp vụ | Độ phủ Phase 1 | Evidence VERIFIED | Trách nhiệm và bước cần làm INFERRED |
|---|---|---|---|---|
| 1 | Init danh mục lớp/GV/môn từ vnEdu theo năm/học kỳ/điểm trường | CHƯA CÓ | `contracts/input.py:38` ScheduleInput nhận collections sẵn; `domain/models.py:34` SchoolContext do caller cấp. Thiết kế Phase1 `docs/superpowers/specs/2026-10-26-phase-1-design.md:7` loại HTTP/adapter. | Adapter giải envelope/schema/scope, giữ ID; core tiếp tục độc lập I/O. Không gọi API trong normalize. |
| 2 | Kiểm ID opaque, field lạ/schema version, tham chiếu | ĐẦY ĐỦ | `domain/models.py:17–24` strict IDs/extra=forbid; `contracts/input.py:41,54` version literal, unique/reference checks; `tests/unit/test_contracts.py:23,49,55`. | Upstream vẫn phải chọn đúng source namespace; validation tồn tại không chứng minh mapping semantic. |
| 3 | Xác định raw `so_tiet` thành định mức theo tuần/học kỳ/năm | CHƯA BIẾT | `docs/research/vnedu-api-live-observations.json:29–39` có 527 chuỗi 0, semantic_unit UNKNOWN; collection descriptions không có định mức. `domain/models.py:96` dùng periods_per_cycle, không có so_tiet. | Phải xác minh nguồn/đơn vị/cycle ngoài core. Không map raw 0 thành confirmed 0. |
| 4 | Khởi tạo định mức từ chương trình/khối/môn rồi override theo lớp | CHƯA CÓ | `domain/models.py:79` Subject không có curriculum rules; TeachingRequirement chứa số đã quyết định. | Upstream curriculum/config service hoặc nhập giáo vụ; provenance/version/override; không hardcode chương trình vào solver. |
| 5 | Persist/import/export cấu hình demand, defaults và overrides | CHƯA CÓ | Core không có SQLite/config repository; `cli.py:90` chỉ atomic write kết quả; Core First `docs/VNEDU_TKB_CORE_FIRST_CODEX.md:317` đặt SQLite ở Phase4. | Storage ngoài core lưu trạng thái chưa xác nhận và xác nhận riêng, snapshot input JSON reviewable. Atomic output không thay database lifecycle. |
| 6 | Cho phép demand 0 **được caller xác nhận** | ĐẦY ĐỦ | `domain/models.py:96` NonNegativeInt; `tests/unit/test_contracts.py:237`; normalize không tạo occurrence cho 0 (`preprocessing/normalize.py:48–61`). Empty solve `solver/cp_sat.py:80–101` trả FEASIBLE/EMPTY_PROBLEM, không chạy solver. | Giữ semantics generic; sản phẩm upstream cần completeness gate. Đây không phải bug “solver làm lịch rỗng” khi caller thực sự yêu cầu 0. |
| 7 | Phân biệt “chưa có định mức”, “không học môn”, “không có GV”, “định mức 0 hợp lệ” | CHƯA CÓ | Input chỉ chứa confirmed integer requirement, không có trạng thái draft/unresolved (`domain/models.py:90–113`). | Application có trạng thái unresolved, resolved_zero, confirmed_positive; chặn chuyển sang ScheduleInput khi chưa đủ. Không thêm sentinel teacher hay số tiết giả để vượt parser. |
| 8 | Phát hiện teacher ID không tồn tại/teacher list rỗng | ĐẦY ĐỦ | `domain/models.py:95` min_length=1; `contracts/input.py:76` check teacher references; `tests/unit/test_contracts.py:49,207`. | Đúng phạm vi core: từ chối record. Báo dòng nguồn/giải thích 5 PCGD thiếu GV thuộc adapter và giáo vụ. |
| 9 | Tự gán GV hoặc xếp trước các môn chưa được phân GV | CHƯA CÓ | Requirement bắt buộc teacher_ids, model không có teacher-choice vars; `constraints/hard.py:23` dùng teacher cố định. | Nếu thực sự cần teacher assignment phải thiết kế bài toán khác; hiện giữ unresolved ngoài solver. Không coi thiếu GV là rảnh toàn lịch. |
| 10 | Sinh toàn tiết đơn và stable occurrence IDs | ĐẦY ĐỦ | `preprocessing/normalize.py:31–61`: `<requirement_id>::<ordinal>`, duration=1 nếu split None; revalidate/copy trước expand; `tests/unit/test_preprocessing.py:14`. | Core dùng số đã xác nhận. Upstream chọn stable requirement ID, lưu mapping nguồn. |
| 11 | Pattern đơn/đôi khai báo trước, bảo toàn tổng | ĐẦY ĐỦ | `domain/models.py:99,107–110`; `normalize.py:48–61`; `tests/integration/test_solver.py:203` pattern tổng 5 `[2,1,1,1]`. | UI/config có thể dùng default toàn đơn và cho sửa pattern trước solve; đó là lớp ngoài core. |
| 12 | Solver tự chọn số tiết đôi hoặc lựa chọn nhiều split patterns | CHƯA CÓ | `solver/model_builder.py:19–31` chỉ chọn placement cho occurrences đã dựng; `docs/superpowers/specs/2026-10-26-phase-1-design.md:19` loại alternative split. | Chỉ thêm khi nghiệp vụ cần. Cần identity/mapping lock/validator/penalty cho alternatives, không tự đổi demand decomposition để tìm nghiệm. |
| 13 | Block 3+ tiết hoặc block qua giờ nghỉ được trường cho phép | CẦN ĐỔI | `contracts/capabilities.py:16` từ chối duration>2; `feasibility.py:116–117` timed double phải liên tục phút; validator `independent_validator.py:187` cùng kiểm. | Profile mới phải định nghĩa continuity/break policy rồi cập nhật capability, footprint, validator, tests; không chỉ bỏ guard. |
| 14 | Tiết đôi chiếm hai slots đúng ngày/buổi và availability | ĐẦY ĐỦ | `feasibility.py:104–127` footprint period+delta, cùng day/session, can_teach, teacher/class cả block; `independent_validator.py:171–193`; `tests/unit/test_preprocessing.py:27,37,106`. | Upstream phải khai báo break thật, không để hai slots symbolic liền period che mất nghỉ thực. |
| 15 | Calendar symbolic/timed, resource overlap vật lý | ĐẦY ĐỦ | `normalize.py:62–114` toàn input cùng timeline mode, timed elementary tokens; `constraints/hard.py:10–31`; validator `:68–88,284–328`; `tests/unit/test_validator.py:94`. | Đầy đủ theo contract hiện tại, không có nghĩa tự tải calendar từ vnEdu. Timed minutes phải dùng gốc cycle-wide. |
| 16 | Lịch ngày/buổi/tiết khác nhau từng lớp, các ngày nghỉ | MỘT PHẦN | `ScheduleInput.time_slots` toàn cục (`contracts/input.py:43`); `AvailableResource` có available_slot_ids (`domain/models.py:63`); prepare xét availability cả block. | Có thể biểu diễn miền giờ đã biên dịch bằng availability trên calendar chung. Chưa có class-calendar editor/templates hoặc policy nghỉ tự động. |
| 17 | Tuần cố định, tuần A/B, phân phối theo tuần/chẵn lẻ | CẦN ĐỔI | `SchoolContext` chỉ school/year/term/timezone (`models.py:34–40`), TimeSlot chỉ day/session/period (`43–51`); thiết kế `phase-1-design.md:41` loại A/B. | Chu kỳ dài có thể mã hóa day=1..N nhưng không tạo semantics week parity/repeat/scope rules. Nếu cần tuần A/B thực, thêm contract calendar/cycle có version, mapper/export + independent validator. Không tuyên bố đang hỗ trợ chỉ vì period_per_cycle tổng quát. |
| 18 | Đặt cố định một occurrence vào start slot, room riêng hoặc cả hai | ĐẦY ĐỦ | `LockedAssignment` `models.py:124–135`; reference/ordinal `input.py:86–104`; domain lock `feasibility.py:104–106,159–174`; validator lock `:197–212`; test `test_contracts.py:221`. | Lock là start toàn block; room-only lock vẫn cho chọn thời gian. Upstream mapping occurrence phải ổn định khi sửa split. |
| 19 | Tiết chào cờ/sinh hoạt/chủ nhiệm tự sinh từ dữ liệu trường | MỘT PHẦN | Core đặt được requirement thường + lock nếu đã có GV/lớp/duration. Không có rule chủ nhiệm đặc thù; `capabilities.py:20–28` reject mọi custom rule enabled. | Upstream tạo demand sau khi xác nhận định mức, đối tượng tham gia và slot. Raw môn -2 chỉ là association chủ nhiệm, không tự biến thành 1 tiết. Nếu không GV hoặc toàn trường tham gia cần mở model riêng. |
| 20 | Đồng giảng nhiều GV/lớp ghép | CẦN ĐỔI | Schema có tuples nhưng `capabilities.py:10–15` reject len!=1; `feasibility.py:57,98,175`, `constraints/hard.py:23`, validator `:194` dùng phần tử [0]. | Phải sửa đồng bộ domain/prechecks/occupancy/rooms/validator và tests, không chỉ bỏ MULTIPLE_PARTICIPANTS. Lớp ghép khác với overlapping subgroup membership. |
| 21 | Subgroups có thành viên chồng lấn | CHƯA CÓ | `ClassGroup` docstring `models.py:69–70` coi resource nguyên tử; không membership model; occupancy chỉ class ID. | Cần atomic learners/membership expansion hoặc conflict graph có bằng chứng; không cho IDs khác nhau nghĩa là độc lập. |
| 22 | Không trùng lớp/GV/phòng và đủ tất cả occurrences | ĐẦY ĐỦ | `model_builder.py:19–31` ExactlyOne; `hard.py:15–31` indexed AtMostOne; validator tự đếm `:131–160,307–328`; `tests/unit/test_validator.py:68`. | Guarantee theo snapshot/semantics hỗ trợ. `OPTIMAL` ở feasibility model không có nghĩa lịch đẹp. |
| 23 | Chọn phòng theo capacity/type/availability, nếu bật | ĐẦY ĐỦ | `feasibility.py:59–95,128–137`; requires class.size/candidate.capacity, incompatible room lock lỗi; validator `:89–128,213–266`; tests `test_solver.py:144,161,181`. | Đầy đủ một lớp/occurrence, một phòng. Nguồn phòng vnEdu chưa được cung cấp; equipment/tổ hợp phòng chưa có. |
| 24 | Hard availability đã được xác nhận của GV/lớp/phòng | ĐẦY ĐỦ | `models.py:63–66` None=mọi teaching slots, empty=không slot; `_available` `feasibility.py:31`; validator `:267–278`. | H05 đã đủ sau khi upstream xác nhận/biên dịch availability. Mã998Nghỉ thuộc candidateS01;999Bận chưa tự phân loại. Không chuyển nguyện vọng hoặc unknown availability thành unavailable/empty. |
| 25 | Min-days/cách môn, max môn/ngày, số ngày dạy, gaps, tải buổi | CHƯA CÓ | Rule records chỉ data `models.py:138–166`; `capabilities.py:20` reject enabled hard/soft; model_builder không objective/rule dispatch. | Policy0.1 chốt H10 và S01–S12 với unit/activation rõ, nhưng vẫn chưa có implementation. Phase2 cần registry/model/independent evaluator và quality contract; không kế thừa weight hoặc probability FET. |
| 26 | Travel giữa điểm trường | CHƯA CÓ | Không site/travel model trong domain; occupancy chỉ clash cùng token. | Chốt cơ sở/ma trận thời gian/chuyển buổi trước; shared teacher ID vẫn cần thống nhất ngay khi chưa travel. |
| 27 | Precheck tải/domain và trạng thái giải rõ | ĐẦY ĐỦ | `feasibility.py:183–202` EMPTY_DOMAIN, RESOURCE_CAPACITY, ROOM_CAPACITY; normalize guard `:15–17` UNKNOWN/RESOURCE_LIMIT; `cp_sat.py:16–24` map statuses; test `test_solver.py:29,82,121`. | Đây là necessary checks, không đủ chứng minh feasible. Không có minimal unsat-core explanation hiện tại. |
| 28 | Validate độc lập và chặn kết quả sai/stale | ĐẦY ĐỦ | `independent_validator.py:14` không import preprocessing/solver; `cp_sat.py:154–171` gate export; `contracts/output.py:63–74` không expose assignments nếu unvalidated; CLI `:145–151` fingerprint check. | Đúng input không chứng minh đủ nghiệp vụ trường. Upstream xác nhận source snapshot là điều kiện trước đó. |
| 29 | Xếp lại phần còn lại, giữ explicit locks | MỘT PHẦN | solve nhận lock trong problem; model không biết previous schedule (`cp_sat.py:27–28`); precheck khóa và validator đã có. | Có thể caller khóa ngoài vùng rồi full solve để giữ chúng. Chưa repair API, neighborhood policy, diff hoặc giảm xáo trộn. Boundary rules tương lai phải xét toàn lịch. |
| 30 | Minimize số tiết đổi, hints, vùng repair tự mở rộng | CHƯA CÓ | Không PreviousSchedule/repair API; builder chỉ ExactlyOne/occupancy, không hints/objective. Core First `:229–236,311–315` là roadmap, không implementation. | Phase3 sau khi định nghĩa stable mapping khi demand/split đổi; hard locks ưu tiên hơn mục tiêu ít thay đổi. |
| 31 | Partial schedule để chẩn đoán thiếu tiết | CẦN ĐỔI | Every occurrence ExactlyOne `model_builder.py:28`; validator yêu cầu count đủ `:131–135,307–309`; `output.py:73–74` cấm assignments trên unsuccessful/unvalidated. | Giữ default full-valid. Nếu muốn partial diagnostics phải có chế độ/output riêng với unscheduled/missing demand rõ; không gọi partial là valid full schedule. |
| 32 | Soft objective/score và giải thích chất lượng | CHƯA CÓ | `cp_sat.py:28` no objective; metadata fields objective/bound chỉ schema (`output.py:36–37`), không được tính; enabled soft bị reject. | Phase2 thêm penalty breakdown evaluator độc lập và objective bounds/priority đã chốt. Không suy output có field nghĩa tính năng đã có. |
| 33 | Save draft/history, sửa cấu hình, restore, publish/sync | CHƯA CÓ | CLI JSON atomic output `cli.py:90,179–187`; không app/DB/HTTP. Core First Phase4 `:317–324`. | Lớp application lưu phiên bản/cấu hình/fingerprint/trạng thái sync, không để solve ghi server. Nghiên cứu có thể thiết kế nhưng chưa triển khai. |
| 34 | Worker progress/cancel/IPC/Desktop | CHƯA CÓ | SolveOptions có budget/seed/workers (`solver/options.py:10`), solve đồng bộ, không public callback/cancel; report Phase1 limitations. | Worker/process lifecycle ngoài pure core; cooperative cancellation cần contract riêng, trả incumbent nếu valid; không giả UNKNOWN thành infeasible. |
| 35 | Hiệu năng/Windows/trường thật | CHƯA BIẾT | `docs/phase-1-report.md` ghi chưa benchmark/Windows/trường thật; synthetic correctness tests không đo production capacity. | Benchmark trên synthetic đại diện, sau đó dữ liệu được phép/ẩn danh; đo trước tối ưu. Không claim số lớp hay tốc độ từ report test timing. |

## Các điểm dễ dẫn tới kết luận sai

**VERIFIED — zero demand:** `solve` có nhánh empty nhưng diagnostic gọi rõ “Empty synthetic demand”, metadata executed giữ false. Empty result được validator xác nhận chỉ là “đủ 0 occurrences của input này”. Không có semantic “đã kiểm mọi lớp có đủ chương trình”. **INFERRED:** độ đầy đủ định mức phải là một upstream preflight trước core, có audit trail cho việc xác nhận zero. Đừng thay core thành cấm mọi zero: điều đó làm mất use case generic/draft đã thiết kế và không giải quyết nguồn `so_tiet`.

**VERIFIED — missing teacher và multi-teacher:** trường hợp rỗng/dangling khác với nhiều GV hợp lệ. Cái đầu là contract-invalid, cái sau contract có thể parse nhưng Phase1 unsupported. **INFERRED:** cần hiển thị riêng “chưa phân GV”, “thiếu danh mục/mapping” và “đồng giảng chưa hỗ trợ”; không gom thành vô nghiệm. Khi hỗ trợ nhiều participants, add_occupancy dùng [0] hiện chỉ an toàn nhờ guard; phải mở cả prepare và independent validator, capacity semantics/phòng cho lớp ghép.

**VERIFIED — doubles/fixed:** occurrence ordinal là theo thứ tự `block_durations`; fingerprint giữ thứ tự này. Đổi `[2,1]` sang `[1,2]` đổi identity-duration theo ordinal. **INFERRED:** upstream không giữ lock `r::1` mù quáng qua thay đổi split; phải remap hoặc yêu cầu review lock, vì slot lock hợp lệ kỹ thuật có thể khóa nhầm nội dung.

**VERIFIED — week variants:** core nói periods_per_cycle nhưng chưa có tuần/date/repeat/parity. **INFERRED:** một input cycle dài có thể biểu diễn slots đã expand, nhưng bản thân điều này chưa cung cấp cấu hình tuần A/B, ràng buộc scope theo tuần hay export lịch lặp. Cần phân biệt technical representation với feature nghiệp vụ hoàn chỉnh.

**VERIFIED — partial repair:** khóa toàn bộ occurrences ngoài vùng rồi solve là kỹ thuật đã khả dụng trong API dữ liệu, nhưng không có guarantee vùng sửa nhỏ nhất/số đổi ít nhất. **INFERRED:** đừng quảng cáo là repair tối ưu, và không dùng partial assignments từ solver status UNKNOWN bởi output hiện không cho.

## ĐỀ XUẤT kiến trúc và lộ trình tối thiểu

Không đề nghị viết lại core hay chép FET/STKB. Các mốc dưới đây là thiết kế tiếp theo khi có ủy quyền triển khai; phần upstream có thể được chốt trước soft solver.

| Mốc | Owner và thay đổi tối thiểu | Điều kiện vào/ra |
|---|---|---|
| A — Chốt dữ liệu và từ điển nghiệp vụ | Research/application: xác minh định mức thật, namespace teacher, zero, chủ nhiệm, calendar/break, single/double, quy tắc trường. Đối chiếu serializer STKB với file cung cấp; API evidence chỉ là một nguồn. | Mỗi trường dữ liệu có fact/source và đơn vị, UNKNOWN được ghi rõ; không đưa raw unknown vào confirmed demand. |
| B — Init/config/persistence ngoài core | Adapter + application: catalog snapshot, unresolved demand worksheet, curriculum defaults và overrides có provenance; calendar/rule config và version; synthetic fixtures. | Snapshot đủ danh mục/references; mỗi demand được xác nhận tổng+cycle+split; locks remapped; application có completeness gate. Không cần nhúng service vào `src/tkb_core`. |
| C — Tích hợp Phase1 hiện có | Application biên dịch sang ScheduleInput; core normalize→prepare→solve→validate. Lưu input hash/result/diagnostics thành draft ngoài core. | Tận dụng đơn/đôi, hard availability/locks/phòng sẵn có; user review JSON/sample schedules. Không bật custom rules mà Phase1 sẽ reject. |
| D — Quality/rules được xác nhận | Phase2 core: registry + compiler/evaluator cho từng rule được chọn; phân biệt hard min-days, soft spacing, consecutive, max per-day, gaps và units/priority. | Từng rule có test nhỏ/vét cạn, independent penalty evaluator, score tốt hơn baseline với hard-valid giữ nguyên. Một requirement nhiều components có min-days không tự suy từ môn trùng tên. |
| E — Capability mở rộng khi thật cần | Core contract version + prepare/model/validator đồng bộ cho co-teaching/lớp ghép/A-B/break profiles/alternative splits. Chọn từng nhu cầu đã xác minh, không một bản mở rộng chung trừu tượng. | Có fixtures edge cases, mapping stable IDs và backwards behavior; không chỉ bỏ capability guard; independent validator theo semantics mới. |
| F — Repair + benchmark | Phase3 core + orchestration: previous schedule có fingerprint/mapping, explicit locks, neighborhood và minimize changes; benchmark synthetic nhiều size/seed/CPU. | Validator toàn lịch pass; infeasible vùng sửa khác full-problem infeasible; báo số thay đổi và số liệu đo thực. |
| G — Product lifecycle | Phase4 application/adapters: DB drafts/history/sync transaction, worker/cancel/IPC/UI/Windows packaging và vnEdu write integration sau xác minh payload. | Export/publish tách review; crash/stale job không ghi đè lịch đang dùng. Không coi atomic CLI file là workflow đã hoàn chỉnh. |

## Kiểm tra thực tế của lượt nghiên cứu

Đã đọc bằng `rg`, `sed`, `nl`; đọc source tests và report/spec, không chạy lại suite. Báo cáo Phase1 ghi 143 passed và lệnh lint/type/build của lượt triển khai trước; **không dùng các số này như kết quả chạy mới**. Không chạy uv sync/pytest/ruff/mypy vì không thay source/config/tests, không tuyên bố nghiệm thu implementation mới.

Bản nghiên cứu chi tiết gốc được lưu local trong `reverse-engineering/reports/full-study/fet-vnedu/`; bản này tổng hợp trong docs. Không sửa Core hoặc sao chép FET implementation vào sản phẩm. Gap phân loại dựa snapshot source hiện tại; mapping STKB/raw API và policy trường còn UNKNOWN phải được đối chiếu với kết quả nhóm khác.

## Bổ sung từ REA tiếp tục — 2026-10-26

**VERIFIED binary/tài liệu:** [nguồn định mức](01-demand-provenance.md) đã bổ sung các dialog chuẩn thường/2B/Excel, staging API và một tuyến tạo demand từ bảng nội bộ; [30 hệ số](06-score-defaults.md) có mapping assembly. Những phát hiện này củng cố gap upstream (#3–7), không tự bổ sung tính năng vào Core.

**INFERRED — điều chỉnh thiết kế cần ưu tiên:** tách assignment association khỏi resolved demand; thêm completeness/provenance ở application trước gọi core. Giữ `periods_per_cycle=0` cho zero đã xác nhận. Không sửa nó thành auto1 hoặc cấm0 để che nguồn dữ liệu chưa rõ.

**INFERRED — 2b/2B:** Phase1 biểu diễn được các requirement sáng/chiều bằng miền availability và tổng đã biên dịch. Tuy nhiên `TeachingRequirement` chưa có business session quota/curriculum/default propagation; `ClassGroup` chưa lưu kiểu2b/2B. Đây là hỗ trợ một phần về biểu diễn, chưa phải workflow2b/2B. Nên giải quyết policy ở compiler/application trước, chỉ mở contract khi per-requirement domain hoặc quota rule không thể diễn đạt đúng bằng capability hiện tại. Không ép toàn trường cùng một kiểu chỉ vì lệnh2B của STKB có chốt đó.

**INFERRED — constraint precedence:** cần policy resolver được version trước registry/compiler. HelpSTKB có mâu thuẫn về min/max/override; không đem sự mơ hồ vào model. `enabled` custom rules hiện bị reject đúng thiết kế; vẫn giữ guard cho đến khi model và evaluator thực thi đủ.

**UNKNOWN:** parity nhiều tuần, catalogue default hiện hành của trường, ngữ nghĩa mọi field/legacyprofile .STKB và runtime override; cấu trúc8file đã đọc đúngEOF ở báo cáo08. Hàng #35 vẫn unknown: kiểm tra source và143tests lịch sử không là benchmark trường thật.

## Ma trận cập nhật sau khi chốt policy 0.1

**VERIFIED source / INFERRED phân loại theo mục tiêu:** nguồn code tương ứng nằm trong bảng 35 mục và E 5 của policy; bằng chứng binary/file trong E1–E3. Việc đã giải mã được input không tự bổ sung constraint vào model.

| Nhóm policy | Phân loại Phase1 | Bằng chứng và việc còn thiếu |
|---|---|---|
| H01/H02, đúng demand/phâncông với một GV+mộtlớp | **1. Đã hỗ trợ đầy đủ** trong capability | `normalize.py::normalize:31–61`, `model_builder.py::build_model:19–31`, validator`independent_validator.py:131–160`. Không tự xác minh đủ chương trình học từraw API. |
| H03/H04, không trùng GV/atomicclass/phòng | **1. Đã hỗ trợ đầy đủ** trong capability | `hard.py::add_occupancy:10–31`, footprint/tokens và validator. Subgroupschồnglấn không nằm trong phạm vi này. |
| H05/H06/H07, calendar/availability/block1–2/lock occurrence | **1. Đã hỗ trợ đầy đủ** khi input đã biên dịch | `feasibility.py:104–137,159–174`; validator tựdựngfootprint/lock. Không bao gồm tự nhập mã STKB hoặc tự khóaSH/cặp. |
| H08, phòngrequired/type/capacity/availability | **1. Đã hỗ trợ đầy đủ** theo metadatahiệncó | `feasibility.py:59–95,128–137`. Nguồnphòng/type/sizevẫn phải có; không phải đã hỗ trợmọi eligibility/travel. |
| H09, họpbắt buộc | **2. Hỗ trợ một phần** | Có hardavailability để chặn GV đãxác nhận; chưa có importer/participantresolver hoặc eventtậpthể. Không tự áp mãhọp lên mọi GV. |
| H12, quota theo buổi và fixed event đơn giản | **2. Hỗ trợ một phần** | Có thể biên dịch một số trường hợp thành requirement s/availability/locks. Jointquota cần rule; multiweek/co-teaching cần mở model. |
| Nguồn `.STKB` → inputCore hoàn chỉnh | **2. Hỗ trợ một phần của toàn dự án**, **Core chưa có adapter** | Readernghiêncứu đã đọc 8 file; chưa có application compiler/provenance gate/curriculumoverride và occurrence remapping. Không nhúng serializer STKB vào solver. |
| H10 và toàn bộ S01–S12 | **3. Chưa hỗ trợ** | `capabilities.py::check_capabilities:20–28` reject mọi enabled custom rule; `cp_sat.py::solve:27–28` chưa objective; chưa penalty evaluator. Cấu hình weight trongschema không phải implementation. |
| G01–G04 completeness, xác nhận nguồn/unit và resolver precedence | **3. Chưa hỗ trợ ở application** | Core chỉ nhận confirmedinteger demand; không có trạng thái unresolved/worksheet/resolver. Đây là hạngmục upstream, không bug của normalize. |
| Quality tier s/breakdown/version profile | **4. Thiết kế cần điều chỉnh trước Phase2** | `models.py:149–166` chỉ code/scope/parameters/enabled/weight, chưa tier. Cần chốt typedparameters/unit và contractversion; không lén thêm field vào input1.0 hoặc xài weight khổnglồ nhưhard. |
| H03 mở rộng learneroverlap/H12 multi-participant, A/B | **4. Thiết kế cần điều chỉnh** | Participantguard hiệnreject, prepare/model/validator dùng[0]; domainchưa membership/week semantics. Phải sửa đồng bộ và versionđúng khi đượcduyệt. |
| H11 travel | **4. Thiết kế cần điều chỉnh** để hỗ trợ nghiệp vụnày | Chưa có location/traveltime/domain; occupancy hiệnkhôngchứngminh đủ thời gian di chuyển. |
| Repair priority và stable mapping khi đổi split | **3. Chưa hỗ trợ repair**, mở rộngthiết kế ởPhase3 | Có explicit lock s nhưngkhôngPreviousSchedule/hints/change objective. Policyđềxuất(P1,changes,P2,P3) chưađượcimplement. |
| Raw999, mọi subtypeHọp, auto-lock và kếthừaconfig STKB | **5. Chưa đủ bằng chứng để kết luận mapping đầy đủ** | Giữ raw/provenance và mapping pending; không đẩy nhầm thành hard/soft mặcđịnh. Không còn blockerđọcEOF; đây là semantic/runtimegap. |
| Ngưỡng thực tế của trường và performanceQuality | **5. Chưa đủ bằng chứng** | Cấu hình3/4/2 tiết chỉ thuộc những GV/snapshot đã đọc; chưa được nhà trườngxác nhận làm profile mới, chưa cóbenchmarktươngđương. |

### Các thay đổi ưu tiên được chốt trong tài liệu, chưa thực hiện

1. **P0 upstream:** completeness gate và policyresolver; chọn snapshot, xác nhận demand/split/cycle, phân loại Nghỉ/Bận/Họp vàlocks. Không sửa `periods_per_cycle=0` thành fallback1 hoặc cấm0 để chữa dữ liệu thiếu.
2. **P1 thiết kếPhase2:** registry/schema/unit/tier contract và evaluator độc lập. Nhóm triển khai đầu là S01–S04 và hard variants khi bật explicit; giữcapabilityreject tới khi enforceđúng.
3. **P2 chất lượng:** spacing/maxmônngày, gaps/ngàybuổinghỉ theo semantics policy; sau đó benchmarkvà repair. Không viếtlạiPhase1 feasibility hoặc bật toàn bộ FET catalogue.

**Chốt ranh giới:** Phase1 vẫn đạt phạm vi hard feasibility đã thiết kế. Nó chưa phải engine đủnghiệp vụ/quality; không coi thiếu soft compiler làlỗi testcũ, và không coi decoderfile mới là đã có adapterproduction. Không có source/test/config/dependencyCore nào thay đổi trong lượt cập nhật này.
