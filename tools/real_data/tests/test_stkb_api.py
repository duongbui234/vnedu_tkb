"""STKB API helpers without network: response parsing, index privacy, file selection."""

import json
from typing import Any

from tools.real_data import stkb_api as api


def _payload(items: list[dict[str, Any]], as_string: bool = True) -> dict[str, Any]:
    inner = {"aRoot": items}
    return {"success": True, "object": [json.dumps(inner) if as_string else inner]}


def test_true_life_id_is_base64_of_site_id() -> None:
    assert api.true_life_id("123456789") == "MTIzNDU2Nzg5"


def test_parse_list_handles_string_object_and_failures() -> None:
    item = {"file_id": "1", "file_name": "a.STKB"}
    assert api.parse_list(_payload([item])) == [item]
    assert api.parse_list(_payload([item], as_string=False)) == [item]
    assert api.parse_list({"success": False, "object": []}) == []
    assert api.parse_list({"success": True, "object": ['{"aRoot": null}']}) == []
    assert api.parse_list({"success": True, "object": ["[1, 2]"]}) == []


def test_index_drops_names() -> None:
    item = {
        "id": "9",
        "file_id": "1",
        "file_name": "a.STKB",
        "ten_truong": "X",
        "user_id": "u",
        "truong_id": "t",
        "ngay_tao": "d1",
        "ngay_cap_nhat": "d2",
    }
    (entry,) = api.index_entries("5", "2025", "1", [item])
    assert entry == {
        "site_id": "5",
        "nam_hoc": "2025",
        "hoc_ky": "1",
        "id": "9",
        "file_id": "1",
        "file_name": "a.STKB",
        "ngay_tao": "d1",
        "ngay_cap_nhat": "d2",
    }


def _e(site: str, file_id: str, updated: str) -> dict[str, Any]:
    return {"site_id": site, "file_id": file_id, "ngay_cap_nhat": updated}


def test_pick_round_robin_newest_first_without_duplicates() -> None:
    index = [
        _e("A", "a1", "2025-01"),
        _e("A", "a2", "2026-01"),
        _e("B", "b1", "2025-05"),
        _e("A", "a2", "2026-01"),
        _e("C", "c1", "2024-01"),
    ]
    assert [e["file_id"] for e in api.pick(index, 2)] == ["a2", "b1"]
    assert [e["file_id"] for e in api.pick(index, 10)] == ["a2", "b1", "c1", "a1"]


def test_years_range() -> None:
    assert api._years("2023-2026") == ["2023", "2024", "2025", "2026"]
    assert api._years("2025") == ["2025"]
