import pandas as pd
import os

_movie_df = None
_ratings_df = None

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data/ml_data")


def get_movie_df() -> pd.DataFrame:
    """全局加载一次电影信息，避免重复读取"""
    global _movie_df
    if _movie_df is None:
        path = os.path.join(DATA_DIR, "movie_info.csv")
        modern_path = os.path.join(DATA_DIR, "modern_movies.csv")
        # index_col=0 跳过 pandas 导出时产生的行号列
        _movie_df = pd.read_csv(path, index_col=0)
        _movie_df["catalog_source"] = "movielens"

        # modern_movies.csv 是增量电影池，不改动原始 MovieLens 数据集
        if os.path.exists(modern_path):
            modern_df = pd.read_csv(modern_path)
            modern_df["catalog_source"] = "modern"
            _movie_df = pd.concat([_movie_df, modern_df], ignore_index=True)

        # 确保genres字段存在
        if "genres" not in _movie_df.columns:
            raise ValueError("movie_info.csv is missing the genres column.")
        _movie_df["overview"] = _movie_df.get("overview", "").fillna("")
        _movie_df["cover_url"] = _movie_df.get("cover_url", "").fillna("")
        if "popularity" not in _movie_df.columns:
            _movie_df["popularity"] = 0
        _movie_df["popularity"] = _movie_df["popularity"].fillna(0)
    return _movie_df


def get_ratings_df() -> pd.DataFrame:
    """全局加载一次评分数据"""
    global _ratings_df
    if _ratings_df is None:
        path = os.path.join(DATA_DIR, "ratings.csv")
        _ratings_df = pd.read_csv(path)
    return _ratings_df
