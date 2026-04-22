"""
补充 /api/sample-movies 接口，供前端评分页调用
将此内容追加到 flaskr/routes.py 末尾
"""

# 在 routes.py 末尾添加：

# @bp.route("/api/sample-movies", methods=["POST"])
# def sample_movies():
#     """根据用户选择的类型，返回10部供评分的电影"""
#     from recommender import get_movie_df
#     import random
#
#     data = request.json
#     genres = data.get("genres", [])
#
#     movie_df = get_movie_df()
#
#     # 筛选包含所选类型的电影
#     if genres:
#         mask = movie_df["genres"].apply(
#             lambda g: any(genre in str(g) for genre in genres)
#         )
#         filtered = movie_df[mask]
#     else:
#         filtered = movie_df
#
#     # 随机抽取10部
#     sample = filtered.sample(min(10, len(filtered)), random_state=random.randint(0, 999))
#
#     movies = [
#         {
#             "movie_id": int(row["movieId"]),
#             "title": str(row.get("title", "")),
#             "genres": str(row.get("genres", "")).split("|"),
#             "poster_url": str(row.get("cover_url", ""))
#         }
#         for _, row in sample.iterrows()
#     ]
#
#     return jsonify({"movies": movies})
