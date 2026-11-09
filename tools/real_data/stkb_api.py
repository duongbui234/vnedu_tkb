"""Find and download STKB timetable files through the vnEdu ``stkb`` API (read-only GET calls).

Tooling outside the Scheduling Core, used only on the user's explicit request for real-data intake.
``truongTrueLifeId`` is base64 of the school's site id. The index keeps file metadata only (ids,
year, term, file name, dates); school and user names in the API response are dropped. Files and
indexes belong under ``benchmarks/artifacts/real/`` (gitignored). Credentials are optional: they
are read from a Postman collection's variables, which must stay out of git.

    python -m tools.real_data.stkb_api scan --sites docs/site_ids_base64_mapping.csv \\
        --output benchmarks/artifacts/real/api/tkb_index.json
    python -m tools.real_data.stkb_api download benchmarks/artifacts/real/api/tkb_index.json \\
        --limit 50 --output benchmarks/artifacts/real/api/files
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import http.cookiejar
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

BASE_URL = "https://s19.vnedu.vn/stkb/"
KEPT_FIELDS = ("id", "file_id", "file_name", "ngay_tao", "ngay_cap_nhat")


def true_life_id(site_id: str) -> str:
    return base64.b64encode(site_id.encode()).decode()


def parse_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Files of ``getDSThoikhoabieu``; ``object[0]`` is a JSON string holding ``aRoot``."""
    objects = payload.get("object")
    if not payload.get("success") or not objects:
        return []
    first = objects[0]
    data = json.loads(first) if isinstance(first, str) else first
    if not isinstance(data, dict):
        return []
    return [item for item in data.get("aRoot") or [] if isinstance(item, dict)]


def index_entries(
    site_id: str, year: str, term: str, items: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {"site_id": site_id, "nam_hoc": year, "hoc_ky": term}
        | {k: item.get(k) for k in KEPT_FIELDS}
        for item in items
    ]


def pick(index: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Newest file of every school first, then second-newest, ...; each file id once."""
    by_school: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for entry in sorted(index, key=lambda e: e.get("ngay_cap_nhat") or "", reverse=True):
        if entry["file_id"] not in seen:
            seen.add(entry["file_id"])
            by_school[entry["site_id"]].append(entry)
    picked: list[dict[str, Any]] = []
    depth = 0
    while len(picked) < limit and any(depth < len(v) for v in by_school.values()):
        for site in sorted(by_school):
            if depth < len(by_school[site]) and len(picked) < limit:
                picked.append(by_school[site][depth])
        depth += 1
    return picked


class Client:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 60.0, retries: int = 3) -> None:
        self.base_url, self.timeout, self.retries = base_url, timeout, retries
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(self, name: str, **params: str) -> bytes:
        query = urllib.parse.urlencode({"call": f"thoikhoabieu.{name}", **params})
        for attempt in range(self.retries):
            try:
                with self.opener.open(f"{self.base_url}?{query}", timeout=self.timeout) as resp:
                    return bytes(resp.read())
            except OSError:
                if attempt == self.retries - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))
        raise AssertionError("unreachable")

    def login(self, username: str, password: str) -> None:
        self.call("dangnhap", username=username, password=password)

    def list_files(self, site_id: str, year: str, term: str) -> list[dict[str, Any]]:
        payload = json.loads(
            self.call(
                "getDSThoikhoabieu", truongTrueLifeId=true_life_id(site_id), namHoc=year, hocKy=term
            )
        )
        return parse_list(payload)

    def download(self, site_id: str, year: str, file_id: str) -> bytes:
        return self.call(
            "downloadFile", truongTrueLifeId=true_life_id(site_id), namHoc=year, file_id=file_id
        )


def collection_credentials(path: Path) -> tuple[str, str] | None:
    variables = {v["key"]: v.get("value", "") for v in json.loads(path.read_text())["variable"]}
    if variables.get("username") and variables.get("password"):
        return variables["username"], variables["password"]
    return None


def read_sites(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig") as handle:
        return [row["site_id"].strip() for row in csv.DictReader(handle) if row.get("site_id")]


def scan(
    client: Client, sites: list[str], years: list[str], terms: list[str], concurrency: int
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    jobs = [(s, y, t) for s in sites for y in years for t in terms]

    def one(job: tuple[str, str, str]) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
        try:
            return index_entries(*job, client.list_files(*job)), None
        except (OSError, ValueError) as exc:
            return [], {"site_id": job[0], "nam_hoc": job[1], "hoc_ky": job[2], "error": str(exc)}

    index: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for entries, error in pool.map(one, jobs):
            index += entries
            if error:
                errors.append(error)
    return index, errors


def download_files(
    client: Client, picked: list[dict[str, Any]], folder: Path
) -> list[dict[str, Any]]:
    manifest = []
    for entry in picked:
        name = f"{entry['site_id']}_{entry['nam_hoc']}_{entry['hoc_ky']}_{entry['file_id']}.STKB"
        target = folder / name
        try:
            data = client.download(entry["site_id"], entry["nam_hoc"], entry["file_id"])
        except OSError as exc:
            manifest.append({**entry, "error": str(exc)})
            continue
        with target.open("xb") as handle:
            handle.write(data)
        marker = int.from_bytes(data[:4], "little") if len(data) >= 4 else None
        manifest.append(
            {
                **entry,
                "local": name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "marker": marker,
            }
        )
    return manifest


def _years(text: str) -> list[str]:
    first, _, last = text.partition("-")
    return [str(y) for y in range(int(first), int(last or first) + 1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--collection", type=Path, help="Postman collection holding credentials")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="list the timetable files of every school")
    s.add_argument("--sites", type=Path, required=True, help="CSV with a site_id column")
    s.add_argument("--years", default="2023-2026", help="school years, e.g. 2023-2026")
    s.add_argument("--terms", default="1,2")
    s.add_argument("--concurrency", type=int, default=4)
    s.add_argument("--output", type=Path, required=True, help="new index JSON file")
    d = sub.add_parser("download", help="download files picked from an index")
    d.add_argument("index", type=Path)
    d.add_argument("--limit", type=int, default=50)
    d.add_argument("--output", type=Path, required=True, help="new directory for the files")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output {args.output} already exists; nothing is overwritten")
    client = Client(args.base_url)
    credentials = collection_credentials(args.collection) if args.collection else None
    if credentials:
        client.login(*credentials)
    if args.command == "scan":
        args.output.parent.mkdir(parents=True, exist_ok=True)  # fail before a long scan, not after
        index, errors = scan(
            client,
            read_sites(args.sites),
            _years(args.years),
            args.terms.split(","),
            args.concurrency,
        )
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump({"files": index, "errors": errors}, handle, ensure_ascii=False, indent=1)
        print(
            f"{len(index)} files in {len({e['site_id'] for e in index})} schools; "
            f"{len(errors)} failed calls"
        )
        return 0
    data = json.loads(args.index.read_text(encoding="utf-8"))
    index = data["files"] if isinstance(data, dict) else data
    args.output.mkdir(parents=True)
    manifest = download_files(client, pick(index, args.limit), args.output)
    with (args.output / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=1)
    ok = [m for m in manifest if "sha256" in m]
    print(f"downloaded {len(ok)}/{len(manifest)}; format 84: {sum(m['marker'] == 84 for m in ok)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
