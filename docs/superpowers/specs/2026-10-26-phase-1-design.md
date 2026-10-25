# Phase 1 — Scheduling MVP, tiết đơn và tiết đôi

Trạng thái: **đã được người dùng duyệt để triển khai Phase 1**, ngày 2026-10-26. Kết quả triển khai/nghiệm thu xem [phase-1-report](../../phase-1-report.md).

## 1. Ý định và quyết định đã có

Người dùng yêu cầu tiếp tục Phase 1 sau Phase 0 và đã chọn **hỗ trợ cả tiết đơn và tiết đôi**. Giữ Python + OR-Tools CP-SAT local, domain/contract độc lập I/O, không xây Desktop, SQLite, HTTP hoặc vnEdu adapter. [Core First](../../VNEDU_TKB_CORE_FIRST_CODEX.md) là đặc tả nghiệm thu, [thiết kế tổng thể](2026-10-25-scheduling-core-design.md) là định hướng. Phần tiết đôi mở rộng MVP theo lựa chọn người dùng.

Phase 0 đã có contract input/output 1.0, fingerprint, lock references, CLI validate-input và 63 tests; chưa có normalization, prechecks, model hoặc independent validator. Các defaults và policy dưới đây là **đề xuất của người thiết kế**, không phải quy định vnEdu đã xác nhận.

Mục tiêu: CLI xếp được lịch synthetic có tiết đơn/đôi, đủ phân công, đúng availability/khóa/phòng, rồi validator độc lập xác nhận. Dữ liệu vô nghiệm, sai hoặc vượt capability có trạng thái rõ. Không tối ưu gaps/cách môn hoặc số thay đổi; đó là Phase 2/3.

## 2. Approaches và lựa chọn phạm vi

| Phương án | Đánh đổi | Kết luận |
|---|---|---|
| Chỉ tiết đơn | Miền/validator nhỏ nhất; block đôi chưa thực thi | Người dùng chọn mở rộng hơn |
| Tiết đơn + block đôi có split khai báo trước | Kiểm toàn footprint; giữ đúng tổng tiết và khóa; không cần solver quyết định cách chia môn | **Phạm vi được người dùng chọn** |
| Solver tự chọn cách chia đơn/đôi và các độ dài khác | Thêm alternative split, identity và objective; thay đổi nghiệp vụ đáng kể | Không thuộc Phase 1 |

Ví dụ demand 5 tiết, `block_durations=[2,1,1,1]` sinh bốn occurrences với duration 2/1/1/1, tổng 5. Không khai báo split thì sinh toàn tiết đơn. Duration >2 trả UNSUPPORTED_FEATURE, không tự cắt nhỏ. Demand 0/rỗng vẫn là input hợp lệ về cấu trúc; kết quả lịch rỗng chỉ chứng nhận đúng input synthetic được cung cấp, không chứng nhận dữ liệu trường đã đầy đủ.

## 3. Semantics tiết đôi và calendar

Một block đôi là **một occurrence** đặt tại start slot và chiếm hai slot. Môn, lớp, GV và phòng của block giữ nguyên. Hai tiết cùng ngày, cùng buổi, period tăng đúng 1, đều can_teach và mọi resource đều khả dụng trên cả hai. Không vượt buổi/ngày hoặc bước qua một slot nghỉ/period bị thiếu.

**Default đề xuất:** không cho block đôi vượt khoảng nghỉ. Calendar có hai chế độ, áp dụng cho toàn input:

- Tất cả slots thiếu minutes: dùng timeline ký hiệu theo day/session/period. Hai periods kề nhau cùng buổi là liền tiết; nghỉ phải biểu diễn bằng can_teach=false hoặc thiếu period. Không suy ra thời gian vật lý từ tên slot.
- Tất cả slots có minutes: kiểm overlap bằng khoảng phút nửa mở. Block đôi còn yêu cầu `end_minute` tiết trước bằng `start_minute` tiết sau; gap dương không tự được coi là chuyển tiết được phép. Đây là default bảo thủ, cần profile khác nếu trường cho ghép hai bên khoảng nghỉ; không đưa profile đó vào Phase 1.
- Có slot có minutes và slot không có: INPUT_INVALID vì không so sánh timeline an toàn. Mọi minutes cùng gốc đầu chu kỳ như contract Phase 0. Thứ tự minutes trong cùng ngày/buổi phải phù hợp period; ngày khác không được mô tả bằng khoảng phút chồng nhau dưới cùng gốc chu kỳ.

Validator và model kiểm footprint, không chỉ start. Hai block start khác nhau vẫn có thể xung đột ở slot thứ hai. Giờ bắt đầu của lock block là start slot, không phải một tiết bất kỳ trong block.

## 4. Snapshot, normalize và capability

Public API nhận ScheduleInput + SolveOptions. Revalidate bằng data dump rồi tách snapshot riêng, không dùng references mutable của caller hoặc model_construct để bỏ validation. Giữ input fingerprint hiện có; không đổi thuật toán hash Phase 0 vì implementation order.

Normalization sinh occurrence IDs `<requirement_id>::<ordinal>`, ordinal theo split hoặc thứ tự tiết đơn. Các index nội bộ dựng theo ID canonical, độc lập thứ tự danh mục. Lưu quan hệ occurrence→requirement, duration, participants, lock và source_reference.

Phase 1 chỉ hỗ trợ một class/group và một GV cho mỗi requirement, coi class/group là resource nguyên tử. Requirement nhiều GV/lớp, rule enabled chưa hỗ trợ, hoặc block >2 trả UNSUPPORTED_FEATURE; không silently ignore. Đây là giới hạn chức năng, không phải schema invalid. Không thêm membership nhóm, cơ sở/travel, tuần A/B hoặc PreviousSchedule trong phase này.

Built-in hard constraints luôn áp dụng và không tắt bằng rule config. Chưa có registry policy tùy biến: mọi hard/soft declaration enabled trả UNSUPPORTED_FEATURE; disabled declarations được giữ trong fingerprint nhưng không thực thi. Việc phân loại này dùng chung cho solve và validate-schedule.

## 5. Phòng và khóa

- `manage_rooms=false`: không gán phòng, vẫn enforce time/class/GV/khóa giờ. Input có room-required/room lock đã bị contract từ chối như Phase 0.
- `manage_rooms=true`: occurrence room-required hoặc có room lock phải dùng phòng vật lý phù hợp; occurrence không cần phòng và không bị khóa phòng dùng room_id=null. Không coi null là một phòng chung bị giới hạn 1.
- Có required_room_type thì chỉ chọn phòng cùng type. Candidate kiểm availability phòng trên toàn block.
- Với occurrence dùng phòng, cần class.size và capacity của các phòng có thể xét để kiểm chứng sức chứa. Metadata bắt buộc cho việc này bị thiếu trả INPUT_INVALID, không coi phòng là vô hạn. Metadata đủ nhưng không có phòng phù hợp/đủ chỗ là domain rỗng/INFEASIBLE có diagnostic.
- Không yêu cầu capacity/size cho tài nguyên không tham gia xếp phòng. Chỉ xét metadata phòng phù hợp type khi có yêu cầu type; không chặn vì một phòng ngoài scope thiếu dữ liệu.
- Khóa giờ giữ start; khóa phòng giữ room nhưng cho phép chọn start; khóa cả hai giữ cả hai. Nếu room lock gây phát sinh nhu cầu phòng thì áp đầy đủ room eligibility như trên.
- Trùng khóa trên footprint/resource hoặc khóa vào slot cấm được phát hiện trước solve và trả INPUT_INVALID/LOCK_CONFLICT; không tự bỏ khóa. Khóa hợp lệ từng cái nhưng khiến phần còn lại không xếp được là INFEASIBLE, không gán nguyên nhân duy nhất khi chưa chứng minh.

Đây là policy safety đề xuất cho Phase 1; room fields optional của Phase 0 vẫn parse được, nhưng bật chức năng xếp phòng có thêm yêu cầu dữ liệu ở preflight.

## 6. Prechecks và model

Prechecks theo thứ tự: contract → capability → timeline/room metadata → occurrence/domain → khóa → các điều kiện cần về tải resource. Return diagnostics có code/resource/slot/occurrence/source liên quan, không in input records hoặc credential.

Kiểm tải lớp/GV theo tổng duration và tập slot thật có thể dùng; không đếm chung sáng/chiều thành cùng slot. Domain rỗng của một occurrence là bằng chứng vô nghiệm trong scope đã mô hình, sau khi loại hết lỗi input/capability. Metadata không đủ không được gọi là vô nghiệm.

Tạo Boolean `x[occurrence, placement]`, placement gồm start, covered slots, thời gian thật nếu có và room khi cần. Chỉ tạo candidate thỏa hard eligibility. Mỗi occurrence ExactlyOne. Index theo resource/footprint, AtMostOne trên từng slot ký hiệu hoặc đoạn phút nguyên tử khi dùng minutes. Không kiểm cặp toàn bộ occurrences một cách không cần thiết.

Khóa giới hạn các thành phần placement tương ứng. Bảo toàn tổng duration theo requirement. Dùng một model feasibility, **không có soft objective**. Nếu CP-SAT trả OPTIMAL ở bài không objective, diễn giải là đã hoàn tất feasibility, không quảng cáo chất lượng lịch tối ưu.

Theo dõi số occurrences/placements; có resource guard vận hành cấu hình được để dừng trước cấp phát quá lớn, không cắt miền hoặc bỏ constraint. Nếu chạm guard, trả trạng thái chưa kết luận cùng diagnostic RESOURCE_LIMIT; không trả INFEASIBLE. Giá trị giới hạn ban đầu là engineering config được ghi rõ trong plan, không phải giới hạn nghiệp vụ của trường.

## 7. Independent validator

`validate_schedule(problem, assignments)` nhận raw assignments typed và input, trả ValidationReport. Không import OR-Tools, không dùng CP-SAT variable, candidate domain hoặc footprint/eligibility helper của model làm oracle. Có thể dùng cùng domain types và error codes; tự dựng danh sách occurrences và footprint từ requirements/calendar.

Kiểm: ID occurrence/slot/room hợp lệ, không dư/trùng/thiếu occurrence, đúng participants theo phân công, duration/split, can_teach/availability mọi resource trên mọi slot, block adjacency/break, toàn bộ locks, room type/capacity và overlap lớp/GV/phòng. Dựng occupancy độc lập từ assignments, không tin danh sách covered slots do solver báo.

Result chỉ có assignments và valid_schedule=true sau validator pass. CP-SAT feasible nhưng validator fail là MODEL_INVALID kèm diagnostic INTERNAL_VALIDATION_FAILED; không xuất assignments sai hoặc mô tả input vô nghiệm. Không tin validation report hay valid_schedule=true từ result file người dùng đưa vào CLI; luôn recompute.

`validate-schedule` thêm kiểm fingerprint của result so với problem. Hash lệch là stale result và lỗi input. Validator raw assignments không tự có lịch sử/version; wrapper kiểm fingerprint trước khi gọi. Capability/room/timeline không hỗ trợ được trả lỗi có loại rõ, không report valid với rule bị bỏ qua.

Ở API validator, input/capability không hợp lệ được biểu diễn bằng ValidationReport.valid=false với violation code INPUT_INVALID hoặc UNSUPPORTED_FEATURE tương ứng; CLI map sang exit 2. Không dùng kết quả này để kết luận vô nghiệm. `solve` bắt lỗi revalidation/options ở boundary và trả ScheduleResult.INPUT_INVALID, không để exception validation thành một lịch rỗng hợp lệ.

## 8. API, output và CLI

Public functions:

```text
solve(problem: ScheduleInput, options: SolveOptions | None = None) -> ScheduleResult
validate_schedule(problem: ScheduleInput, assignments: Sequence[ScheduleAssignment]) -> ValidationReport
```

SolveOptions: time_limit_seconds=60, num_workers=1, seed=42, cùng resource guards. Defaults chỉ cho thử nghiệm, không phải cam kết production. Kiểu/range/finite được validate; invalid options là INPUT_INVALID. Budget time-limit được truyền cho CP-SAT; wall_time đo end-to-end và solver_wall_time đo riêng. Không hứa end-to-end <= time_limit khi preprocessing/validation cũng tốn thời gian.

Input vẫn schema **1.0** và fingerprint Phase 0. Output solver phát **1.1** để thêm run metadata mà không gọi đó là payload 1.0 tương thích với parser strict cũ. Parser mới đọc output 1.0/1.1; giữ các guardrails Phase 0. Assignment vẫn lưu start slot; covered slots suy từ duration/context, không nhân đôi block thành hai assignment.

Metadata 1.1 có solver_version, seed, num_workers, time_limit_seconds, wall_time, solver_wall_time, solver_executed; objective_value/best_bound null nếu không có mục tiêu. Nếu chưa chạy solver vì lỗi/precheck hoặc input rỗng, ghi rõ solver_executed=false và không chế số đo solver. Empty problem được validator xác nhận vacuous schedule, trả FEASIBLE với diagnostic EMPTY_PROBLEM, không giả là CP-SAT đã chứng minh OPTIMAL.

Các status: INPUT_INVALID, UNSUPPORTED_FEATURE, INFEASIBLE, UNKNOWN, MODEL_INVALID, FEASIBLE, OPTIMAL. Nếu timeout chưa có nghiệm thì UNKNOWN; có nghiệm đã validate thì FEASIBLE nếu chưa hoàn tất. Không đọc assignments từ solver ở status không có nghiệm. Seed/workers/version/budget được lưu, không hứa deterministic khi nhiều workers.

CLI mở rộng argparse hiện có:

```sh
tkb-core validate-input problem.json
tkb-core solve problem.json --time-limit 60 --workers 1 --seed 42 --output result.json
tkb-core validate-schedule problem.json result.json
```

`validate-input` giữ nguyên ý nghĩa contract-only. Solve/validate-schedule stdout một JSON object; log stderr. `--output` ghi đầy đủ JSON result, không đè input và dùng ghi atomic để tránh file nửa chừng. Ghi file thất bại phải exit lỗi, không giả thành công.

Kiểm tra không đè input phải xét đường dẫn resolve và cùng file/inode nếu đã tồn tại, không chỉ so chuỗi pathname; có test symlink/hardlink phù hợp platform.

Exit 0: solve có lịch được validator xác nhận hoặc validate-schedule pass. Exit 2: input/usage/unsupported/stale/invalid schedule. Exit 3: INFEASIBLE. Exit 4: UNKNOWN/resource limit. Exit 5: MODEL_INVALID/internal error. Input/file lỗi không echo raw values. Help vẫn là help text argparse. Benchmark/repair/worker IPC chưa có.

OR-Tools vẫn ở optional extra `solver`; cài bằng uv sync --locked --extra solver cho tests Phase 1. Import contract và validator không đòi import OR-Tools; chỉ tuyến solve cần extra. Nếu thiếu dependency, solve trả UNSUPPORTED_FEATURE/SOLVER_NOT_INSTALLED, không giả nghiệm.

## 9. Kiểm thử và nghiệm thu

Giữ 63 tests Phase 0, cập nhật test command/version khi có hành vi mới có chủ ý. Thêm tests có expected độc lập, không chỉ so solver với helper của chính model.

| Nhóm | Ca bắt buộc |
|---|---|
| Normalize | 5 tiết [2,1,1,1] → 4 occurrences, tổng 5; ID ổn định khi đảo danh mục; input caller không bị sửa |
| Block | Hai slot hợp lệ; start cuối buổi; qua ngày/buổi; thiếu period; can_teach=false; GV/lớp/phòng bận ở tiết thứ hai |
| Timeline | Symbolic AM/PM khác nhau; actual minutes có hai slot ID chồng; mixed minutes bị từ chối; gap dương cấm block theo default |
| Khóa | Giờ/phòng/cả hai; double lock giữ start và chiếm cả footprint; khóa trùng resource hoặc khóa vào bận |
| Phòng | Room-required và không cần phòng; room type; capacity đủ/thiếu; metadata thiếu không bị coi là vô nghiệm |
| Validator sai chủ động | Thiếu/dư/trùng occurrence; sai participants; slot/phòng lạ; teacher/class/room overlap; sai lock; report/file tự nhận valid không được tin |
| Status | Input sai, unsupported, precheck vô nghiệm, CP-SAT vô nghiệm, feasible, unknown/time-limit, model invalid; không xuất lịch chưa validate |
| CLI | Solve → JSON/file → validate-schedule; stale fingerprint; malformed JSON; output trùng input/gặp lỗi ghi; không lộ nội dung input |
| Hồi quy | Empty/zero demand; opaque IDs; duplicate keys; serialization; pin/import/packaging không chứa dữ liệu local |

Có fixture infeasible_teacher, locked_lessons, feasible_double, double_blocked, room_required và một bài nhiều lớp/GV/môn. Tạo bài nhỏ có điều kiện cần đều pass nhưng toàn bài vô nghiệm để thật sự chạy nhánh CP-SAT INFEASIBLE; không chỉ test precheck.

Đối chứng bài rất nhỏ bằng enumerator/brute force thuần Python trong tests, cùng hard semantics nhưng không gọi model helper. Timeout integration không dựa lịch máy tình cờ nhanh/chậm: kiểm mapping bằng test deterministic và smoke time-limit ghi rõ giới hạn; không tuyên bố một fixture chắc chắn timeout nếu không kiểm soát.

Nghiệm thu: uv run pytest, ruff, format-check, mypy, uv build, installed-wheel CLI solve/validate-schedule thực; mọi lịch nhận phải qua validator độc lập. Báo số test/lệnh/file/giới hạn thực tế. Không benchmark so FET/STKB hoặc claim production speed trong Phase 1.

## 10. Phạm vi file và phần chưa làm

Thêm preprocessing/{normalize,feasibility}, solver/{options,model_builder,cp_sat}, constraints/hard, validation/independent_validator và các init cần import. Chỉnh contracts/output, domain/enums nếu cần mã status/diagnostics, CLI và tests. Không tạo scaffolding soft/repair/worker rỗng. Tên file chi tiết và giới hạn resource vận hành có thể được chốt trong implementation plan.

Tài liệu cập nhật: assumptions, domain-model, solver-design, constraint-catalog, README và phase-1-report. Không sửa source/data nghiên cứu. Thực thi ở feature branch/worktree sau khi thiết kế được duyệt; không thay main hoặc tự push code trong giai đoạn brainstorm.

Chưa có từ người dùng: policy tiết đôi qua nghỉ, capacity metadata trường thực, actual calendar và nhu cầu tiết thật. Thiết kế đề xuất default bảo thủ ở trên, dùng fixtures synthetic; không coi đó là chính sách vnEdu. Trước khi cắm dữ liệu thật phải xác nhận coverage/schema/nguồn riêng.

Sau duyệt thiết kế mới viết implementation plan và thực hiện Phase 1. Phase 2/3/4 không được bắt đầu tự động.

## 11. Kiểm tra thiết kế

Một reviewer độc lập đã đối chiếu tài liệu với AGENTS.md, Core First và code Phase 0; không phát hiện blocker quan trọng để lập implementation plan. Đây là review tài liệu, chưa phải chạy solver hoặc nghiệm thu Phase 1. Lượt này không cài OR-Tools hoặc thay đổi production code.
