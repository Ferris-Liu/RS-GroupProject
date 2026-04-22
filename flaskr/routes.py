import random
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
        return jsonify({"error": "输入不能为空"}), 400

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

    results = get_recommendations(
        user_ratings=data.get("ratings", []),
        user_genres=data.get("genres", []),
        algorithm=algorithm,
        include_reasons=include_reasons
    )

    shown_ids = [m["movie_id"] for m in results]
    session["shown_ids"] = shown_ids

    return jsonify({
        "recommendations": results,
        "algorithm": algorithm,
        "explain": include_reasons
    })


@bp.route("/api/feedback", methods=["POST"])
def feedback():
    """
    Step 3：接收用户Like反馈，返回基于内容的追加推荐
    """
    data = request.json
    liked_ids = data.get("liked_movie_ids", [])

    # 更新session中的liked列表
    current_liked = session.get("liked_ids", [])
    current_liked = list(set(current_liked + liked_ids))
    session["liked_ids"] = current_liked

    new_recs = get_feedback_recommendations(
        liked_ids=current_liked,
        exclude_ids=session.get("shown_ids", []),
        user_genres=session.get("user_genres", []),
        include_reasons=session.get("include_reasons", True)
    )

    # 更新已展示列表
    new_shown = [m["movie_id"] for m in new_recs]
    session["shown_ids"] = session.get("shown_ids", []) + new_shown

    return jsonify({"recommendations": new_recs})


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
