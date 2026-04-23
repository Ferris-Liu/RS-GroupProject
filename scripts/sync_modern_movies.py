#!/usr/bin/env python3
"""
从 TMDB 同步现代电影增量池 modern_movies.csv。

默认只生成预览文件，不会覆盖原始 CSV。
如果传入 --apply，会先生成 .bak 备份，再覆盖输出文件。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
TMDB_GENRE_URL = "https://api.themoviedb.org/3/genre/movie/list"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
DEFAULT_OUTPUT = Path("data/ml_data/modern_movies.csv")
FIELDNAMES = ["movieId", "title", "genres", "year", "overview", "cover_url", "popularity"]

GENRE_NAME_MAP = {
    "Science Fiction": "Sci-Fi",
    "TV Movie": "",
    "History": "Drama",
    "Western": "Adventure",
}

TARGET_GENRES = [
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "Horror",
    "Music",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "War",
]


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


def http_json(url: str, api_key: str, timeout: float) -> dict:
    """请求 TMDB JSON API"""
    headers = {"User-Agent": "RS-GroupProject/1.0"}
    access_token = os.getenv("TMDB_ACCESS_TOKEN", "")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    separator = "&" if "?" in url else "?"
    request_url = url if access_token else f"{url}{separator}{urlencode({'api_key': api_key})}"
    req = Request(request_url, headers=headers)
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def tmdb_genres(api_key: str, timeout: float) -> tuple[dict[int, str], dict[str, int]]:
    """获取 TMDB 类型映射，并转换成项目使用的类型名"""
    data = http_json(f"{TMDB_GENRE_URL}?{urlencode({'language': 'en-US'})}", api_key, timeout)
    id_to_name = {}
    name_to_id = {}

    for item in data.get("genres", []):
        original_name = item.get("name", "")
        mapped_name = GENRE_NAME_MAP.get(original_name, original_name)
        if not mapped_name:
            continue
        genre_id = int(item["id"])
        id_to_name[genre_id] = mapped_name
        name_to_id[mapped_name] = genre_id

    return id_to_name, name_to_id


def discover_movies(
    api_key: str,
    timeout: float,
    *,
    from_year: int,
    to_year: int,
    page: int,
    genre_id: int | None = None,
    min_vote_count: int = 500,
) -> list[dict]:
    """调用 TMDB discover/movie 获取一页电影"""
    params = {
        "language": "en-US",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "include_video": "false",
        "primary_release_date.gte": f"{from_year}-01-01",
        "primary_release_date.lte": f"{to_year}-12-31",
        "vote_count.gte": str(min_vote_count),
        "page": str(page),
    }
    if genre_id:
        params["with_genres"] = str(genre_id)

    data = http_json(f"{TMDB_DISCOVER_URL}?{urlencode(params)}", api_key, timeout)
    return data.get("results", [])


def movie_to_row(movie_id: int, tmdb_movie: dict, id_to_genre: dict[int, str]) -> dict:
    """把 TMDB 电影记录转换成项目 CSV 行"""
    release_date = tmdb_movie.get("release_date") or ""
    year = release_date.split("-", 1)[0] if release_date else ""
    genres = [
        id_to_genre[genre_id]
        for genre_id in tmdb_movie.get("genre_ids", [])
        if genre_id in id_to_genre
    ]

    poster_path = tmdb_movie.get("poster_path") or ""
    cover_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else ""
    popularity = min(100, round(float(tmdb_movie.get("popularity", 0) or 0)))

    return {
        "movieId": movie_id,
        "title": tmdb_movie.get("title") or tmdb_movie.get("original_title") or "",
        "genres": "|".join(dict.fromkeys(genres)),
        "year": year,
        "overview": tmdb_movie.get("overview", ""),
        "cover_url": cover_url,
        "popularity": popularity,
    }


def movie_quality_key(movie: dict) -> tuple:
    """用于排序候选电影的质量指标"""
    return (
        float(movie.get("popularity", 0) or 0),
        int(movie.get("vote_count", 0) or 0),
        float(movie.get("vote_average", 0) or 0),
        movie.get("release_date", ""),
    )


def collect_movies(args: argparse.Namespace, api_key: str) -> list[dict]:
    """按类型覆盖优先收集电影，再用总体热门补足"""
    id_to_genre, name_to_id = tmdb_genres(api_key, args.timeout)
    candidates_by_tmdb_id = {}

    # 先每个目标类型抓热门候选。不要一够 limit 就停，否则前几个类型会挤占全部名额。
    for genre_name in TARGET_GENRES:
        genre_id = name_to_id.get(genre_name)
        if not genre_id:
            continue

        added_for_genre = 0
        for page in range(1, args.pages_per_genre + 1):
            results = discover_movies(
                api_key,
                args.timeout,
                from_year=args.from_year,
                to_year=args.to_year,
                page=page,
                genre_id=genre_id,
                min_vote_count=args.min_vote_count,
            )
            for movie in results:
                candidates_by_tmdb_id.setdefault(movie["id"], movie)
                added_for_genre += 1
                if added_for_genre >= args.max_per_genre:
                    break
            if added_for_genre >= args.max_per_genre:
                break
            time.sleep(args.sleep)

    # 再从全站热门里补足候选池，提升整体知名度。
    page = 1
    target_candidate_count = max(args.limit * 3, args.limit + len(TARGET_GENRES))
    while len(candidates_by_tmdb_id) < target_candidate_count and page <= args.max_pages:
        results = discover_movies(
            api_key,
            args.timeout,
            from_year=args.from_year,
            to_year=args.to_year,
            page=page,
            min_vote_count=args.min_vote_count,
        )
        for movie in results:
            candidates_by_tmdb_id.setdefault(movie["id"], movie)
            if len(candidates_by_tmdb_id) >= target_candidate_count:
                break
        page += 1
        time.sleep(args.sleep)

    candidates = list(candidates_by_tmdb_id.values())
    candidates.sort(key=movie_quality_key, reverse=True)

    selected_by_tmdb_id = {}

    # 先保证目标类型至少有代表电影。
    for genre_name in TARGET_GENRES:
        genre_id = name_to_id.get(genre_name)
        if not genre_id:
            continue

        for movie in candidates:
            if movie["id"] in selected_by_tmdb_id:
                continue
            if genre_id in movie.get("genre_ids", []):
                selected_by_tmdb_id[movie["id"]] = movie
                break

    # 再按热度补足剩余名额。
    for movie in candidates:
        if len(selected_by_tmdb_id) >= args.limit:
            break
        selected_by_tmdb_id.setdefault(movie["id"], movie)

    movies = list(selected_by_tmdb_id.values())
    movies.sort(key=movie_quality_key, reverse=True)

    return [
        movie_to_row(args.start_id + index, movie, id_to_genre)
        for index, movie in enumerate(movies[: args.limit])
    ]


def write_movies(path: Path, rows: list[dict]) -> None:
    """写出 modern_movies.csv"""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync modern_movies.csv from TMDB discover/movie."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV path to write.")
    parser.add_argument("--apply", action="store_true", help="Overwrite --output after creating a .bak backup.")
    parser.add_argument("--api-key", default=None, help="TMDB API key. Defaults to TMDB_API_KEY from .env/env.")
    parser.add_argument("--limit", type=int, default=50, help="Number of movies to sync.")
    parser.add_argument("--start-id", type=int, default=900001, help="Starting movieId for generated rows.")
    parser.add_argument("--from-year", type=int, default=2016, help="Minimum primary release year.")
    parser.add_argument("--to-year", type=int, default=min(date.today().year, 2024), help="Maximum primary release year.")
    parser.add_argument("--min-vote-count", type=int, default=500, help="Minimum TMDB vote count.")
    parser.add_argument("--pages-per-genre", type=int, default=1, help="TMDB pages to request per genre.")
    parser.add_argument("--max-per-genre", type=int, default=8, help="Maximum candidates to collect per genre.")
    parser.add_argument("--max-pages", type=int, default=10, help="Fallback popular pages to request.")
    parser.add_argument("--sleep", type=float, default=0.25, help="Delay between requests.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()

    api_key = args.api_key or os.getenv("TMDB_API_KEY", "")
    if not api_key and not os.getenv("TMDB_ACCESS_TOKEN"):
        print("TMDB_API_KEY was not found. Add it to .env or pass --api-key.", file=sys.stderr)
        return 1

    rows = collect_movies(args, api_key)
    if not rows:
        print("No movies were returned by TMDB.", file=sys.stderr)
        return 1

    if args.apply:
        if args.output.exists():
            backup_path = args.output.with_suffix(args.output.suffix + ".bak")
            shutil.copy2(args.output, backup_path)
            print(f"Backup written: {backup_path}")
        write_path = args.output
    else:
        write_path = args.output.with_suffix(args.output.suffix + ".preview.csv")

    write_movies(write_path, rows)

    covered_genres = sorted({genre for row in rows for genre in row["genres"].split("|") if genre})
    print(f"Output written: {write_path}")
    print(f"Movies written: {len(rows)}")
    print(f"Movie ID range: {rows[0]['movieId']} - {rows[-1]['movieId']}")
    print(f"Covered genres: {', '.join(covered_genres)}")
    if not args.apply:
        print("Preview only. Re-run with --apply to overwrite modern_movies.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
