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
        # index_col=0 跳过 pandas 导出时产生的行号列
        _movie_df = pd.read_csv(path, index_col=0)
        # 确保genres字段存在
        if "genres" not in _movie_df.columns:
            raise ValueError("movie_info.csv is missing the genres column.")
        _movie_df["overview"] = _movie_df.get("overview", "").fillna("")
    return _movie_df


def get_ratings_df() -> pd.DataFrame:
    """全局加载一次评分数据"""
    global _ratings_df
    if _ratings_df is None:
        path = os.path.join(DATA_DIR, "ratings.csv")
        _ratings_df = pd.read_csv(path)
    return _ratings_df
