# Phase 2A — Mẫu thông tin máy và manifest bàn giao Windows

Theo [checklist Task 2 Windows preflight](phase-2a-windows-preflight-handoff-checklist.md).
Hai khối JSON dưới đây là mẫu điền tay, chưa phải artifacts đã thu hoặc schema của
runner. Windows vẫn **BLOCKED**. Không có approval cài đặt, chạy tests/mini solve
hoặc benchmark trong tài liệu này; approval Linux đã dùng không áp dụng cho Windows.

Chỉ thêm tài liệu mẫu; chưa copy payload, tạo archive/venv, cài đặt hoặc chạy
tests/solver/search/profiling. Không sửa Core, budget hoặc guards.

Khi chuẩn bị bàn giao thực tế, dùng [runbook](phase-2a-windows-task2-runbook.md) và
[inventory sender](windows-task2-payload-inventory.json). Inventory cụ thể bổ sung
cho mẫu manifest trống bên dưới, không thay receiver evidence hoặc cấp approval.
Tên trường inventory tooling (`destination`, `origin`) khác mẫu điền tay; không
truyền mẫu trống vào verifier. Giữ inventory frozen và receiver receipt riêng.

## Mẫu thông tin máy native

Tên gợi ý khi thu thực tế: `windows-machine-intake.json`, lưu ngoài source checkout
tại nơi bàn giao được xác nhận. Dùng ID opaque cho máy/người vận hành, không ghi
hostname/tên tài khoản nếu không cần; không ghi credentials hoặc dữ liệu vnEdu thật.

Mỗi nhóm có `reason` áp dụng cho các trường null trong nhóm; khi điền một phần,
ghi rõ trường còn thiếu và lý do riêng trong `reason`. Không đổi null thành 0/false.
Các trường evidence trỏ tới file tương đối trong gói evidence, không là bằng chứng
đã tồn tại. Ghi command/argv, working directory, UTC, stdout/stderr và exit code
thực khi thu; không suy native Windows hoặc idle chỉ từ lời khai.

```json
{
  "template_version": "1.0",
  "status": "BLOCKED",
  "reason": "WINDOWS_MACHINE_AND_EVIDENCE_NOT_COLLECTED",
  "identity": {
    "machine_id": null,
    "operator_id": null,
    "collected_at_utc": null,
    "reason": "NOT_COLLECTED"
  },
  "os": {
    "edition": null,
    "version": null,
    "build": null,
    "architecture": null,
    "native_windows_verified": null,
    "virtualization": null,
    "evidence_path": null,
    "reason": "NOT_VERIFIED; WSL_OR_LINUX_CROSS_BUILD_IS_NOT_NATIVE_WINDOWS"
  },
  "runtime": {
    "python_path": null,
    "python_exact_version": null,
    "python_architecture": null,
    "uv_version": null,
    "shell_name_and_version": null,
    "evidence_path": null,
    "reason": "NOT_COLLECTED"
  },
  "hardware": {
    "cpu_model": null,
    "logical_cores": null,
    "cpu_topology_and_p_e_cores": null,
    "ram_total_bytes": null,
    "ram_available_bytes": null,
    "pagefile_configuration": null,
    "evidence_path": null,
    "reason": "NOT_COLLECTED; HOST_RAM_IS_NOT_SOLVER_PEAK"
  },
  "operational_context": {
    "observed_at_utc": null,
    "ac_or_battery": null,
    "power_mode": null,
    "competing_workload": null,
    "workload_status": "UNKNOWN",
    "evidence_path": null,
    "reason": "NOT_OBSERVED; DO_NOT_ASSUME_VERIFIED_IDLE"
  },
  "linux_comparability": {
    "same_dual_boot_hardware_verified": null,
    "same_python_patch_verified": null,
    "evidence_path": null,
    "reason": "NOT_VERIFIED; LINUX_REFERENCE_I7_12700H_20_LOGICAL_CORES_PYTHON_3.12.3"
  },
  "paths": {
    "payload_staging_root": null,
    "staging_source_bundle_read_only_by_procedure_confirmed": null,
    "staging_read_only_procedure_evidence_reference": null,
    "dev_venv": null,
    "solver_venv": null,
    "no_solver_venv": null,
    "new_output_root": null,
    "output_root_absent_verified": null,
    "reason": "PATHS_NOT_SELECTED; STAGING_READ_ONLY_PROCEDURE_AND_EVIDENCE_NOT_CONFIRMED; DO_NOT_CREATE_PATHS_OR_COPY_PAYLOAD_YET"
  },
  "handoff": {
    "binary_wheel_availability": null,
    "evidence_capture_method": null,
    "return_location_and_method": null,
    "reason": "NOT_CONFIRMED; NO_INSTALL_OR_EXPORT_ATTEMPTED"
  },
  "task2_approval": {
    "status": "NOT_GRANTED",
    "reference": null,
    "reason": "TEMPLATE_PREPARATION_ONLY; NATIVE_MACHINE_AND_TASK2_SCOPE_REQUIRE_CONFIRMATION"
  }
}
```

Yêu cầu tham chiếu: Windows x64 native, Python 3.12; ưu tiên cùng máy dual-boot,
RAM ≥16 GiB và ≥4 logical cores. Đây không phải guards mới. Khác hardware/Python
patch thì chỉ so hai deployment, không cô lập hiệu ứng OS. Không tự đổi power,
affinity, môi trường hoặc đóng ứng dụng để làm đẹp kết quả.

## Mẫu manifest bàn giao payload

Tên gợi ý khi bàn giao thực tế: `payload-handoff-manifest.json`. Hash kỳ vọng dưới
đây lấy từ checklist, không phải hash receiver đã kiểm. Đường dẫn nguồn tính từ
repo Linux; điền đường dẫn đích Windows thực sau khi được phép bàn giao.

```json
{
  "template_version": "1.0",
  "scope": "PHASE_2A_TASK2_WINDOWS_PREFLIGHT",
  "status": "NOT_TRANSFERRED",
  "windows_status": "BLOCKED",
  "reason": "PAYLOAD_NOT_COPIED; RECEIVER_NOT_VERIFIED",
  "transfer": {
    "handoff_id": null,
    "receiver_machine_id": null,
    "sender_root": "/home/ddevtk/code/vnedu_tkb",
    "receiver_root": null,
    "transferred_at_utc": null,
    "reason": "NOT_TRANSFERRED"
  },
  "frozen_source": {
    "core_commit": "4cfa643148b967ad7baf674fe6439699afbe51e2",
    "core_tree": "1efd459b2514f448dcf4ac297989de09eb76a3a1"
  },
  "assets": [
    {
      "kind": "CORE_WHEEL",
      "source_relative_path": ".worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/distribution/vnedu_tkb_core-0.2.0-py3-none-any.whl",
      "expected_sha256": "1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9",
      "sender_sha256": null,
      "receiver_relative_path": null,
      "receiver_sha256": null,
      "status": "NOT_TRANSFERRED",
      "reason": "NO_TRANSFER_HASHES_COLLECTED"
    },
    {
      "kind": "LOCK",
      "source_relative_path": ".worktrees/phase2a-task5/uv.lock",
      "expected_sha256": "e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084",
      "sender_sha256": null,
      "receiver_relative_path": null,
      "receiver_sha256": null,
      "status": "NOT_TRANSFERRED",
      "reason": "NO_TRANSFER_HASHES_COLLECTED"
    },
    {
      "kind": "FULL_DATASET_BUNDLE",
      "source_relative_path": ".worktrees/phase2a-generator/benchmarks/artifacts/phase2a/task1-v1/",
      "hash_target": "manifest.json",
      "expected_sha256": "a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d",
      "expected_dataset_count": 36,
      "sender_sha256": null,
      "receiver_relative_path": null,
      "receiver_sha256": null,
      "receiver_dataset_count": null,
      "all_referenced_file_hashes_verified": null,
      "status": "NOT_TRANSFERRED",
      "reason": "ROOT_MANIFEST_HASH_IS_NOT_ARCHIVE_HASH; FULL_MEMBERSHIP_NOT_VERIFIED_ON_RECEIVER"
    }
  ],
  "supplemental_payload": {
    "required_roles": [
      "FROZEN_CORE_SOURCE_TESTS_FIXTURES_CONFIG",
      "LINUX_PREFLIGHT_MANIFEST_AND_REPORT_REFERENCE_ONLY",
      "PROBE_SOURCES_AND_COMMAND_PROVENANCE"
    ],
    "inventory_complete": false,
    "reason": "SUPPLEMENTAL_FILES_AND_HASHES_NOT_INVENTORIED"
  },
  "file_inventory": [],
  "inventory_status": "NOT_COLLECTED",
  "inventory_reason": "NO_PAYLOAD_PACKAGE_CREATED",
  "receiver_verification": {
    "status": "NOT_RUN",
    "evidence_path": null,
    "reason": "NO_TRANSFER_OR_WINDOWS_VERIFICATION"
  }
}
```

Khi chuẩn bị bàn giao được cho phép, `file_inventory` phải có từng file của **toàn
bộ payload**, kể cả supplemental files và mọi file bundle. Mỗi entry cần
`role`, `source_relative_path`, `receiver_relative_path`, `size_bytes`,
`sender_sha256`, `receiver_sha256`, `verification_status`, `reason`.
Nếu giá trị chưa có, giữ null và reason; không điền checksum dự kiến vào checksum
thực nhận. Inventory trống hiện tại có nghĩa **chưa đủ để bàn giao**, không phải
payload chỉ gồm ba file. Ghi inventory riêng nếu quá lớn và tham chiếu path/hash
của nó trong manifest thực tế; không tạo archive trong lượt lập mẫu.

Sau copy thực tế, đối chiếu sender/receiver hashes, size và membership, không chỉ
ba root hashes. Giữ đủ 36 dataset IDs/fingerprints/raw bytes/witness scores; không
regenerate, sửa bundle, rebuild Core wheel hoặc mang Linux venv sang Windows.
Hash binary dependency wheels Windows có thể khác Linux nhưng versions/pins phải
khớp; chưa resolve/export/download chúng trong bước lập mẫu này.

Không dùng Linux runner để giả Windows PASS. Các mẫu này không thay thế evidence
Task 2: environment manifests, install/package logs, Core suite, tiny solver và
no-solver/registry probes, verification 36 datasets, final report và digest inventory
theo checklist. Missing wheel/import/probe là BLOCKED với reason; hash hoặc
validation mismatch phải dừng, không sửa pin/budget/guards để vượt gate.
Task 2 chưa được thực hiện; Task 3–5 Windows và Phase 2B/2C không nằm trong phạm vi.
