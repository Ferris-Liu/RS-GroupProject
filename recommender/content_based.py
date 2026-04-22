import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from . import get_movie_df


class EnhancedContentFilter:
    """
    增强版内容过滤：genres multi-hot + TF-IDF 剧情概要
    Demo原版只用了genres，这里额外加入overview文本特征
    """

    def __init__(self):
        self.movie_df = get_movie_df().copy()
        self.movie_ids = None
        self.feature_matrix = None
        self._build_feature_matrix()

    def _build_feature_matrix(self):
        df = self.movie_df

        # 1. Genres multi-hot（与Demo保持一致）
        genre_dummies = df["genres"].str.get_dummies(sep="|")
        genre_matrix = genre_dummies.values.astype(float)

        # 2. TF-IDF overview（新增）
        overviews = df["overview"].fillna("").tolist()
        has_overview = any(len(o) > 10 for o in overviews)

        if has_overview:
            tfidf = TfidfVectorizer(
                max_features=200,
                stop_words="english",
                ngram_range=(1, 2)
            )
            overview_matrix = tfidf.fit_transform(overviews).toarray()
        else:
            overview_matrix = np.zeros((len(df), 1))

        # 3. 拼接特征：genres权重×2（因为类型对电影的相关性更直接）
        self.feature_matrix = np.hstack([genre_matrix * 2, overview_matrix])
        self.movie_ids = df["movieId"].values

    def get_recommendations(
        self,
        liked_movie_ids: list,
        exclude_ids: list,
        top_k: int = 6
    ) -> list:
        """
        基于用户 Like 的电影，计算余弦相似度并推荐

        Args:
            liked_movie_ids: 用户Like的电影ID列表
            exclude_ids: 已展示过的电影ID（不重复推荐）
            top_k: 返回数量

        Returns:
            [{"movie_id": int, "similarity": float}, ...]
        """
        # 找到liked电影在矩阵中的位置
        liked_indices = []
        for mid in liked_movie_ids:
            idx = np.where(self.movie_ids == mid)[0]
            if len(idx) > 0:
                liked_indices.append(idx[0])

        if not liked_indices:
            return []

        # 用户profile = liked电影特征向量的均值
        user_profile = self.feature_matrix[liked_indices].mean(axis=0, keepdims=True)

        # 计算全部电影的余弦相似度
        similarities = cosine_similarity(user_profile, self.feature_matrix)[0]

        # 排序并过滤
        exclude_set = set(exclude_ids)
        results = sorted(
            zip(self.movie_ids.tolist(), similarities.tolist()),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {"movie_id": int(mid), "similarity": round(sim, 4)}
            for mid, sim in results
            if mid not in exclude_set
        ][:top_k]


# 单例，避免每次请求重新构建特征矩阵
_cbf_instance = None

def get_cbf() -> EnhancedContentFilter:
    global _cbf_instance
    if _cbf_instance is None:
        _cbf_instance = EnhancedContentFilter()
    return _cbf_instance
