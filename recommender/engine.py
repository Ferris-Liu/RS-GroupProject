from concurrent.futures import ThreadPoolExecutor, as_completed
from . import get_movie_df
from .collaborative import get_knn_recommendations
from .content_based import get_cbf
from .llm_helper import generate_recommendation_reason


LIGHT_HEARTED_GENRES = {"Comedy", "Romance", "Animation", "Family", "Music", "Musical"}
INTENSE_GENRES = {"Action", "Thriller", "Crime", "Mystery", "Horror"}


def _fetch_movie_info(movie_id: int) -> dict | None:
    """根据ID从movie_info.csv获取完整电影信息"""
    movie_df = get_movie_df()
    row = movie_df[movie_df["movieId"] == movie_id]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "movie_id": int(r["movieId"]),
        "title": str(r.get("title", "")),
        "genres": str(r.get("genres", "")).split("|"),
        "year": str(r.get("year", "")),
        "poster_url": str(r.get("cover_url", "")),
        "overview": str(r.get("overview", ""))
    }


def _enrich_with_reason(movie: dict, user_genres: list) -> dict:
    """为单部电影生成推荐理由（供并发调用）"""
    reason = generate_recommendation_reason(
        user_genres=user_genres,
        movie_title=movie["title"],
        movie_genres=movie["genres"],
        predicted_score=movie.get("predicted_score"),
        movie_year=movie.get("year", ""),
        movie_overview=movie.get("overview", "")
    )
    movie["reason"] = reason
    return movie


def _high_rated_titles(user_ratings: list) -> list[str]:
    """提取用户高分电影标题，用于解释标签"""
    titles = []
    for rating in user_ratings:
        if float(rating.get("rating", 0)) < 4:
            continue
        movie = _fetch_movie_info(rating.get("movie_id"))
        if movie:
            titles.append(movie["title"])
    return titles[:2]


def _build_reason_tags(
    movie: dict,
    user_genres: list,
    high_rated_titles: list[str] | None = None,
    from_feedback: bool = False
) -> list[str]:
    """为卡片生成结构化推荐原因标签"""
    tags = []
    user_genre_set = set(user_genres)
    movie_genres = set(movie.get("genres", []))
    matched_genres = [genre for genre in user_genres if genre in movie_genres]

    if matched_genres:
        tags.append(f"Matched genre: {', '.join(matched_genres[:2])}")

    if high_rated_titles and from_feedback:
        tags.append("Similar to movies you liked")
    elif high_rated_titles:
        tags.append("Similar to movies you rated highly")

    if movie_genres & user_genre_set & LIGHT_HEARTED_GENRES:
        tags.append("Fits your light-hearted preference")
    elif movie_genres & user_genre_set & INTENSE_GENRES:
        tags.append("Fits your intense-watch preference")

    if from_feedback:
        tags.append("Based on your recent feedback")
    elif movie.get("predicted_score") and movie["predicted_score"] >= 4:
        tags.append("High predicted rating")

    if movie.get("similarity") and "Similar to movies you liked" not in tags:
        tags.append("Similar to movies you liked")

    return tags[:4]


def get_recommendations(
    user_ratings: list,
    user_genres: list,
    algorithm: str = "enhanced",
    include_reasons: bool = True
) -> list:
    """
    推荐主入口

    Args:
        user_ratings: [{"movie_id": int, "rating": float}, ...]
        user_genres:  ["Action", "Comedy", ...]
        algorithm:    "enhanced"（时间衰减）或 "baseline"（原始KNN）
        include_reasons: 是否调用LLM生成解释文案。它只影响展示，不参与排序。

    Returns:
        电影信息列表；include_reasons=True 时附带 reason 字段
    """
    use_decay = (algorithm == "enhanced")
    high_rated_titles = _high_rated_titles(user_ratings)

    # Step 1：协同过滤拿到Top-K ID和预测分
    raw_results = get_knn_recommendations(
        user_ratings=user_ratings,
        top_k=12,
        use_decay=use_decay
    )

    # Step 2：补充电影完整信息
    enriched = []
    for item in raw_results:
        info = _fetch_movie_info(item["movie_id"])
        if info:
            info["predicted_score"] = item["predicted_score"]
            info["reason_tags"] = _build_reason_tags(
                movie=info,
                user_genres=user_genres,
                high_rated_titles=high_rated_titles
            )
            enriched.append(info)

    # Step 3：可选解释增强。LLM 不参与核心推荐排序，便于单独做 UI 评测。
    if include_reasons and enriched:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_enrich_with_reason, movie, user_genres): movie
                for movie in enriched
            }
            results = []
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"[Reason generation failed] {e}")
                    movie = futures[future]
                    movie["reason"] = ""
                    results.append(movie)

        # 按预测分重新排序（并发完成后顺序可能乱）
        results.sort(key=lambda x: x.get("predicted_score", 0), reverse=True)
        return results

    # 不展示解释时直接返回，排序仍由推荐算法决定。
    for movie in enriched:
        movie["reason"] = ""
    return enriched


def get_feedback_recommendations(
    liked_ids: list,
    exclude_ids: list,
    user_genres: list,
    include_reasons: bool = True
) -> list:
    """
    Step 3：基于Like的内容过滤追加推荐

    Returns:
        6部新推荐电影；include_reasons=True 时附带理由
    """
    cbf = get_cbf()
    liked_titles = []
    for movie_id in liked_ids:
        movie = _fetch_movie_info(movie_id)
        if movie:
            liked_titles.append(movie["title"])

    cbf_results = cbf.get_recommendations(
        liked_movie_ids=liked_ids,
        exclude_ids=exclude_ids,
        top_k=6
    )

    enriched = []
    for item in cbf_results:
        info = _fetch_movie_info(item["movie_id"])
        if info:
            info["similarity"] = item["similarity"]
            info["predicted_score"] = None
            info["reason_tags"] = _build_reason_tags(
                movie=info,
                user_genres=user_genres,
                high_rated_titles=liked_titles,
                from_feedback=True
            )
            enriched.append(info)

    # 可选解释增强。内容过滤负责排序，LLM 只负责展示文案。
    if include_reasons and enriched:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_enrich_with_reason, movie, user_genres): movie
                for movie in enriched
            }
            results = []
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception:
                    movie = futures[future]
                    movie["reason"] = ""
                    results.append(movie)

        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return results

    for movie in enriched:
        movie["reason"] = ""
    return enriched
