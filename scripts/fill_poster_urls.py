#!/usr/bin/env python3
"""
为电影 CSV 补全或校验电影海报 URL。

默认只生成预览文件，不会覆盖原始 CSV。
如果传入 --apply，会先生成 .bak 备份，再覆盖输入文件。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
DEFAULT_INPUT = Path("data/ml_data/modern_movies.csv")


def load_dotenv(path: Path = Path(".env")) -> None:
    """轻量读取 .env，避免为了脚本额外增加依赖"""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def http_json(url: str, timeout: float) -> dict:
    """请求 JSON API 并返回 dict"""
    req = Request(url, headers={"User-Agent": "RS-GroupProject/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_url(url: str, timeout: float) -> bool:
    """检查图片 URL 是否可访问"""
    if not url:
        return False

    req = Request(url, method="HEAD", headers={"User-Agent": "RS-GroupProject/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return 200 <= response.status < 400
    except HTTPError as exc:
        # 有些图片源不支持 HEAD，退回 GET 试一次。
        if exc.code not in {403, 405}:
            return False
    except URLError:
        return False

    try:
        req = Request(url, headers={"User-Agent": "RS-GroupProject/1.0"})
        with urlopen(req, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError):
        return False


def search_tmdb_poster(title: str, year: str, api_key: str, timeout: float) -> str:
    """用 TMDB 搜索电影，并返回 w500 海报 URL"""
    params = {
        "api_key": api_key,
        "query": title,
        "include_adult": "false",
        "language": "en-US",
    }

    year_text = str(year).strip()
    if year_text:
        params["year"] = year_text.split(".")[0]

    data = http_json(f"{TMDB_SEARCH_URL}?{urlencode(params)}", timeout=timeout)
    results = data.get("results", [])

    for result in results:
        poster_path = result.get("poster_path")
        if poster_path:
            return f"{TMDB_IMAGE_BASE}{poster_path}"

    return ""


def read_movies(path: Path) -> tuple[list[dict], list[str]]:
    """读取 CSV，保留原字段顺序"""
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def write_movies(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """写回 CSV"""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill missing or broken cover_url values in a movie CSV using TMDB."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CSV file to read.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Preview output path. Defaults to <input>.preview.csv when --apply is not used.",
    )
    parser.add_argument("--apply", action="store_true", help="Overwrite --input after creating a .bak backup.")
    parser.add_argument("--api-key", default=None, help="TMDB API key. Defaults to TMDB_API_KEY from .env/env.")
    parser.add_argument("--validate", action="store_true", help="Also validate existing non-empty cover_url values.")
    parser.add_argument("--force", action="store_true", help="Replace existing cover_url values too.")
    parser.add_argument(
        "--fix-invalid",
        action="store_true",
        help="When used with --validate, replace only existing cover_url values that fail validation.",
    )
    parser.add_argument("--sleep", type=float, default=0.25, help="Delay between TMDB requests.")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()

    input_path = args.input
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    api_key = args.api_key or os.getenv("TMDB_API_KEY", "")
    rows, fieldnames = read_movies(input_path)
    if "cover_url" not in fieldnames:
        print("CSV must contain a cover_url column.", file=sys.stderr)
        return 1

    filled = 0
    skipped = 0
    invalid_existing = 0

    for row in rows:
        title = row.get("title", "").strip()
        year = row.get("year", "").strip()
        cover_url = row.get("cover_url", "").strip()

        if args.validate and cover_url and not check_url(cover_url, args.timeout):
            invalid_existing += 1
            if args.force or args.fix_invalid:
                cover_url = ""
                row["cover_url"] = ""

        if cover_url and not args.force:
            skipped += 1
            continue

        if not api_key:
            skipped += 1
            continue

        poster_url = search_tmdb_poster(title, year, api_key, args.timeout)
        if poster_url:
            row["cover_url"] = poster_url
            filled += 1
        else:
            skipped += 1

        time.sleep(args.sleep)

    if args.apply:
        backup_path = input_path.with_suffix(input_path.suffix + ".bak")
        shutil.copy2(input_path, backup_path)
        write_movies(input_path, rows, fieldnames)
        output_path = input_path
        print(f"Backup written: {backup_path}")
    else:
        output_path = args.output or input_path.with_suffix(input_path.suffix + ".preview.csv")
        write_movies(output_path, rows, fieldnames)

    print(f"Output written: {output_path}")
    print(f"Filled poster URLs: {filled}")
    print(f"Skipped rows: {skipped}")
    if args.validate:
        print(f"Invalid existing URLs: {invalid_existing}")
    if not api_key:
        print("TMDB_API_KEY was not found, so missing URLs were not filled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
