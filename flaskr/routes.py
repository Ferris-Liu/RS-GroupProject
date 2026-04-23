import random
from collections import Counter
from flask import Blueprint, request, jsonify, render_template, session
from recommender.engine import get_recommendations, get_feedback_recommendations
from recommender.llm_helper import parse_user_preference
from recommender import get_movie_df

bp = Blueprint("main", __name__)


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


def _experiment_flags():
    """
    拆分算法与界面解释开关，便于分别做 algorithm evaluation 和 UI evaluation。
    旧版 ?version=enhanced/baseline 仍可使用。
    """
    version = request.args.get("version")
    algorithm = request.args.get("algorithm")
    explain = request.args.get("explain")

    if algorithm not in {"baseline", "enhanced"}:
        algorithm = "baseline" if version == "baseline" else "enhanced"

    include_reasons = _parse_bool(explain, default=(version != "baseline"))
    return algorithm, include_reasons


def _movie_by_id(movie_id):
    """根据 movieId 查找电影记录"""
    movie_df = get_movie_df()
    row = movie_df[movie_df["movieId"] == movie_id]
    if row.empty:
        return None
    return row.iloc[0]


def _format_genre_phrase(genres):
    """把类型列表格式化成适合面板展示的短语"""
    if not genres:
        return ""
    if len(genres) == 1:
        return genres[0]
    return f"{', '.join(genres[:-1])} and {genres[-1]}"


def _top_genres_from_movies(movie_ids, limit=2):
    """统计一组电影里最常见的类型"""
    counter = Counter()
    for movie_id in movie_ids:
        row = _movie_by_id(movie_id)
        if row is None:
            continue
        counter.update(str(row.get("genres", "")).split("|"))
    return [genre for genre, _ in counter.most_common(limit) if genre]


def _feedback_summary(liked_ids, disliked_ids, new_recs):
    """生成反馈后展示在推荐列表上方的更新说明"""
    bullets = []
    new_genres = _top_genres_from_movies([m["movie_id"] for m in new_recs], limit=2)
    disliked_genres = _top_genres_from_movies(disliked_ids, limit=1)

    if new_genres:
        bullets.append(f"More {_format_genre_phrase(new_genres)}")

    if disliked_genres:
        bullets.append(f"Fewer {disliked_genres[0]} titles")

    if liked_ids:
        row = _movie_by_id(liked_ids[-1])
        if row is not None:
            bullets.append(f"More movies similar to {row.get('title', 'your liked picks')}")

    return bullets[:3]


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/parse-preference", methods=["POST"])
def parse_preference():
    """
    方案二：自然语言偏好解析
    接收用户输入的自然语言描述，返回结构化偏好
    """
    data = request.json
    user_input = data.get("text", "")
    if not user_input:
        return jsonify({"error": "Input cannot be empty."}), 400

    parsed = parse_user_preference(user_input)
    return jsonify(parsed)


@bp.route("/api/preferences", methods=["POST"])
def preferences():
    """
    Step 1 & 2：接收用户偏好和初始评分，返回推荐列表
    URL参数 ?algorithm=baseline|enhanced 控制算法；?explain=true|false 控制解释展示
    """
    data = request.json
    algorithm, include_reasons = _experiment_flags()

    # 存入session，供后续反馈使用
    session["user_genres"] = data.get("genres", [])
    session["user_ratings"] = data.get("ratings", [])
    session["shown_ids"] = []
    session["liked_ids"] = []
    session["include_reasons"] = include_reasons

    result_payload = get_recommendations(
        user_ratings=data.get("ratings", []),
        user_genres=data.get("genres", []),
        algorithm=algorithm,
        include_reasons=include_reasons
    )
    results = result_payload["recommendations"]

    shown_ids = [m["movie_id"] for m in results]
    session["shown_ids"] = shown_ids
    session["engine_status"] = result_payload["engine_status"]

    return jsonify({
        "recommendations": results,
        "algorithm": algorithm,
        "explain": include_reasons,
        "engine_status": result_payload["engine_status"]
    })


@bp.route("/api/feedback", methods=["POST"])
def feedback():
    """
    Step 3：接收用户Like反馈，返回基于内容的追加推荐
    """
    data = request.json
    liked_ids = data.get("liked_movie_ids", [])
    disliked_ids = data.get("disliked_movie_ids", [])

    # 更新session中的liked列表
    current_liked = session.get("liked_ids", [])
    for movie_id in liked_ids:
        if movie_id not in current_liked:
            current_liked.append(movie_id)
    session["liked_ids"] = current_liked
    session["disliked_ids"] = disliked_ids

    new_recs = get_feedback_recommendations(
        liked_ids=current_liked,
        exclude_ids=session.get("shown_ids", []),
        user_genres=session.get("user_genres", []),
        include_reasons=session.get("include_reasons", True)
    )

    # 更新已展示列表
    new_shown = [m["movie_id"] for m in new_recs]
    session["shown_ids"] = session.get("shown_ids", []) + new_shown

    return jsonify({
        "recommendations": new_recs,
        "feedback_summary": _feedback_summary(current_liked, disliked_ids, new_recs)
    })


@bp.route("/api/sample-movies", methods=["POST"])
def sample_movies():
    """
    根据用户选择的类型，返回10部供初始评分的电影
    """
    data = request.json
    genres = data.get("genres", [])

    movie_df = get_movie_df()

    # 筛选包含所选类型的电影
    if genres:
        mask = movie_df["genres"].apply(
            lambda g: any(genre in str(g) for genre in genres)
        )
        filtered = movie_df[mask]
    else:
        filtered = movie_df

    # 随机抽取10部（每次调用不同，增加趣味性）
    sample = filtered.sample(
        min(10, len(filtered)),
        random_state=random.randint(0, 9999)
    )

    movies = [
        {
            "movie_id": int(row["movieId"]),
            "title": str(row.get("title", "")),
            "genres": str(row.get("genres", "")).split("|"),
            "poster_url": str(row.get("cover_url", ""))
        }
        for _, row in sample.iterrows()
    ]

    return jsonify({"movies": movies})
