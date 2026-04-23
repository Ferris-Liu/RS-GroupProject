import pandas as pd
import numpy as np
from . import get_ratings_df, get_movie_df

try:
    from surprise import KNNWithMeans, Dataset, Reader
except ModuleNotFoundError:
    KNNWithMeans = None
    Dataset = None
    Reader = None

# 新用户使用固定的临时ID，不与原始数据集冲突
NEW_USER_ID = 999999


def _apply_time_decay(df: pd.DataFrame, decay_factor: float = 0.005) -> pd.DataFrame:
    """
    对评分施加时间衰减权重
    decay_factor: 越大衰减越快，0.005 表示约200天后权重降至 e^(-1) ≈ 0.37
    """
    df = df.copy()
    if "timestamp" not in df.columns:
        return df  # 数据集没有timestamp则不衰减

    now = df["timestamp"].max()
    df["days_ago"] = (now - df["timestamp"]) / 86400
    df["rating"] = df["rating"] * np.exp(-decay_factor * df["days_ago"])

    # 裁剪到合法评分范围
    df["rating"] = df["rating"].clip(0.5, 5.0)
    return df


def get_knn_recommendations(
    user_ratings: list,
    top_k: int = 12,
    use_decay: bool = True
) -> list:
    """
    基于 User-based KNN with Means 的协同过滤推荐

    Args:
        user_ratings: [{"movie_id": int, "rating": float}, ...]
        top_k: 返回推荐数量
        use_decay: 是否使用时间衰减（enhanced版本开启）

    Returns:
        [{"movie_id": int, "predicted_score": float}, ...]
    """
    ratings_df = get_ratings_df().copy()
    movie_df = get_movie_df()

    if KNNWithMeans is None:
        return {
            "items": _fallback_popular_recommendations(user_ratings, movie_df, top_k),
            "engine": "fallback_popular",
            "warning": "scikit-surprise is not installed; using popularity fallback ranking."
        }

    # 施加时间衰减
    if use_decay and "timestamp" in ratings_df.columns:
        ratings_df = _apply_time_decay(ratings_df)

    # 把新用户的评分加入数据集
    new_rows = pd.DataFrame([
        {
            "userId": NEW_USER_ID,
            "movieId": r["movie_id"],
            "rating": float(r["rating"]),
            "timestamp": ratings_df["timestamp"].max() if "timestamp" in ratings_df.columns else 0
        }
        for r in user_ratings
    ])
    combined = pd.concat([ratings_df[["userId", "movieId", "rating"]], 
                          new_rows[["userId", "movieId", "rating"]]], 
                         ignore_index=True)

    # 构建 Surprise 数据集
    reader = Reader(rating_scale=(0.5, 5.0))
    data = Dataset.load_from_df(combined[["userId", "movieId", "rating"]], reader)
    trainset = data.build_full_trainset()

    # 训练 KNN 模型
    algo = KNNWithMeans(
        k=40,
        sim_options={"name": "pearson_baseline", "user_based": True},
        verbose=False
    )
    algo.fit(trainset)

    # 找出新用户未评分的电影
    rated_ids = {r["movie_id"] for r in user_ratings}
    all_movie_ids = set(movie_df["movieId"].tolist())
    unrated_ids = all_movie_ids - rated_ids

    # 预测所有未评分电影
    predictions = []
    inner_uid = trainset.to_inner_uid(NEW_USER_ID)
    for movie_id in unrated_ids:
        try:
            inner_iid = trainset.to_inner_iid(movie_id)
            pred = algo.predict(NEW_USER_ID, movie_id)
            predictions.append((movie_id, pred.est))
        except Exception:
            continue

    # 按预测评分降序，取 Top-K
    predictions.sort(key=lambda x: x[1], reverse=True)
    return {
        "items": [
            {"movie_id": mid, "predicted_score": round(score, 2)}
            for mid, score in predictions[:top_k]
        ],
        "engine": "knn_with_means",
        "warning": ""
    }


def _fallback_popular_recommendations(user_ratings: list, movie_df: pd.DataFrame, top_k: int) -> list:
    """surprise 不可用时的兜底推荐，避免接口直接失败"""
    rated_ids = {r["movie_id"] for r in user_ratings}
    rating_stats = (
        get_ratings_df()
        .groupby("movieId")
        .agg(avg_rating=("rating", "mean"), rating_count=("rating", "size"))
        .reset_index()
    )
    rating_stats = rating_stats[rating_stats["rating_count"] >= 20]
    rating_stats["score"] = rating_stats["avg_rating"] * np.log1p(rating_stats["rating_count"])

    valid_ids = set(movie_df[movie_df.get("catalog_source", "movielens") != "modern"]["movieId"].tolist())
    rating_stats = rating_stats[
        rating_stats["movieId"].isin(valid_ids)
        & ~rating_stats["movieId"].isin(rated_ids)
    ]
    rating_stats = rating_stats.sort_values("score", ascending=False).head(top_k)

    return [
        {"movie_id": int(row["movieId"]), "predicted_score": round(float(row["avg_rating"]), 2)}
        for _, row in rating_stats.iterrows()
    ]
