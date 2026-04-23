# 电影推荐系统 / Movie Recommendation System

> 中文说明见上半部分。English documentation is available in the second half.

## 中文版

基于课程 Demo `RS_demo_2026` 的增强版电影推荐系统，集成 Qwen 大模型，用于自然语言偏好解析与推荐理由生成。

### 功能特点

- **增强协同过滤**：User-based KNN + 时间戳衰减权重
- **增强内容过滤**：Genres multi-hot + TF-IDF 剧情概要
- **现代电影增量池**：通过独立的 `modern_movies.csv` 补充 50 部 2016–2024 年更年轻用户熟悉的新片，不修改原始 MovieLens 数据集
- **冷启动新片推荐**：新电影没有历史评分，因此不伪造 `ratings.csv`，而是基于类型匹配、年份新鲜度和 popularity 字段混入少量 modern picks
- **Qwen 推荐理由**：为每部推荐电影生成英文自然语言解释
- **结构化解释标签**：每张推荐卡片展示 2–4 个原因标签，例如匹配类型、高预测评分、相似高分电影、基于近期反馈
- **反馈驱动更新面板**：用户点击 Like / Dislike 后，系统会在推荐列表上方展示反馈如何影响新推荐
- **自然语言偏好输入**：用户可以用一句话描述想看的电影，系统自动解析偏好类型
- **A/B 测试支持**：通过 URL 参数切换 baseline / enhanced 版本

### 快速开始

#### 1. 创建虚拟环境

```bash
conda create -n rs_project python=3.10
conda activate rs_project
```

#### 2. 安装依赖

```bash
pip install --upgrade setuptools wheel
conda install -c conda-forge scikit-surprise
pip install -r requirements.txt
```

#### 3. 配置 API Key

```bash
cp .env.example .env
```

然后编辑 `.env`，填入你的 DashScope API Key。

DashScope 获取地址：https://dashscope.aliyun.com/

#### 4. 放入数据集

将以下文件放入 `data/` 或项目指定的数据目录：

- `ratings.csv`：MovieLens 格式，包含 `userId, movieId, rating, timestamp`
- `movie_info.csv`：电影信息，包含 `movieId, title, genres, year, cover_url, overview`

#### 5. 启动服务

```bash
flask --app flaskr run --debug
```

访问：http://127.0.0.1:5000

### 实验开关与 A/B 测试链接

为满足课程实验要求，系统把“推荐算法”和“界面解释”拆成两个独立开关：

- `algorithm=baseline|enhanced`：只控制核心推荐排序。`baseline` 使用原始 User-based KNN；`enhanced` 使用加入时间衰减权重的 User-based KNN。
- `explain=true|false`：只控制是否展示解释性 UI，包括 Qwen 英文推荐理由和结构化原因标签。LLM 不参与推荐排序。

旧版 `version=enhanced|baseline` 仍可使用，但正式评测建议使用下面的控制变量链接。

| 评测目的 | 条件 | 链接 |
|----------|------|------|
| Algorithm Evaluation 对照组 | baseline algorithm + same UI | http://127.0.0.1:5000/?algorithm=baseline&explain=false |
| Algorithm Evaluation 实验组 | enhanced algorithm + same UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation 对照组 | same algorithm + no explanation | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation 实验组 | same algorithm + explanation UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=true |

说明：Qwen 只用于 natural-language preference parsing 和 recommendation explanation，是界面与解释性增强，不属于核心推荐排序算法。结构化原因标签由后端基于类型匹配、预测分、用户高分电影和反馈状态生成，用于增强解释性但不改变排序。

### 现代电影增量池

为解决原始 MovieLens 数据集电影偏旧的问题，项目新增了独立文件 `data/ml_data/modern_movies.csv`，目前包含 50 部 2016–2024 年电影，覆盖动作、科幻、动画、喜剧、爱情、恐怖、悬疑、音乐、家庭、战争等类型。该文件作为增量电影池使用，原始 `movie_info.csv` 和 `ratings.csv` 不会被修改。

实现方式：

- `recommender/__init__.py` 会在加载电影信息时自动合并 `movie_info.csv` 和 `modern_movies.csv`。
- 新电影使用 `movieId >= 900000`，避免和原始数据集 ID 冲突。
- 新电影不会进入协同过滤评分矩阵训练，因为它们没有真实历史评分。
- `recommender/engine.py` 会在 KNN 推荐结果中混入少量 cold-start modern picks。
- modern picks 的排序依据包括用户选择类型、电影年份新鲜度和 `popularity` 字段。
- modern picks 会带有 `Fresh pick` 等结构化解释标签。

这相当于在原始推荐系统上增加一层 modern catalog layer，既保留课程实验的数据集基础，又改善用户看到的电影年代分布。

### 解释性推荐与反馈机制

推荐结果页现在包含两层解释：

- **自然语言解释**：Qwen 为每部电影生成一句英文推荐理由。
- **结构化原因标签**：后端为每部电影生成 `reason_tags`，例如 `Matched genre: Comedy, Romance`、`Similar to movies you rated highly`、`Fits your light-hearted preference`、`Based on your recent feedback`。

用户反馈行为：

- 点击 **Like**：记录正反馈，用于后续基于内容的相似推荐。
- 点击 **Dislike**：隐藏当前电影，取消该电影的 Like 状态，并把不喜欢的电影类型传给后端。
- 点击 **Find More Like These** 或在已有 Like 后点击 Dislike：系统会请求 `/api/feedback`，追加相似推荐，并返回 `feedback_summary`。

反馈后页面会显示 `Updated based on your feedback` 面板，例如：

- `More Comedy and Romance`
- `Fewer Horror titles`
- `More movies similar to La La Land`

### 项目结构

```text
project/
├── app.py                    # 入口
├── requirements.txt
├── .env.example              # API Key 配置模板
├── flaskr/
│   ├── __init__.py           # Flask 初始化
│   └── routes.py             # 所有 API 路由
├── recommender/
│   ├── __init__.py           # 数据加载
│   ├── collaborative.py      # KNN 协同过滤 + 时间衰减
│   ├── content_based.py      # CBF + TF-IDF
│   ├── engine.py             # 统一推荐入口
│   └── llm_helper.py         # Qwen API 调用
├── templates/
│   └── index.html            # Vue.js 前端页面
├── static/
│   └── app.js                # Vue.js 逻辑
└── data/
    ├── ratings.csv
    ├── movie_info.csv
    └── modern_movies.csv       # 增量新片池，不修改原始数据集
```

### 分工说明

| 成员 | 主要负责文件 |
|------|-------------|
| 梁皓哲 | `templates/index.html`, `static/app.js` |
| 刘飞宇 | `recommender/collaborative.py`, `recommender/content_based.py` |
| 李劲 | `flaskr/routes.py`, `recommender/engine.py`, `recommender/llm_helper.py` |

### 依赖说明

- `scikit-surprise`：协同过滤算法
- `scikit-learn`：TF-IDF 文本特征提取
- `openai`：兼容 DashScope API 的调用方式
- `flask`：Web 框架

---

## English Version

This project is an enhanced movie recommendation system based on the course demo `RS_demo_2026`. It integrates the Qwen large language model for natural-language preference parsing and recommendation explanations.

### Features

- **Enhanced collaborative filtering**: User-based KNN with timestamp decay weights
- **Enhanced content-based filtering**: Genre multi-hot encoding + TF-IDF movie overview features
- **Modern movie catalog layer**: Adds 50 newer 2016–2024 movies through an independent `modern_movies.csv` file without modifying the original MovieLens dataset
- **Cold-start modern picks**: New movies have no historical ratings, so the system does not fake `ratings.csv`; instead, it mixes in a few modern picks using genre matches, recency, and popularity
- **Qwen-powered explanations**: Generates English natural-language explanations for recommended movies
- **Structured reason tags**: Each recommendation card shows 2–4 explanation tags, such as matched genres, high predicted rating, similar high-rated movies, or recent feedback
- **Feedback update panel**: After users click Like / Dislike, the recommendation page explains how the feedback influenced the new recommendations
- **Natural-language preference input**: Users can describe what they want to watch in one sentence, and the system parses genre preferences automatically
- **A/B testing support**: Switch between baseline and enhanced versions through URL parameters

### Quick Start

#### 1. Create a Virtual Environment

```bash
conda create -n rs_project python=3.10
conda activate rs_project
```

#### 2. Install Dependencies

```bash
pip install --upgrade setuptools wheel
conda install -c conda-forge scikit-surprise
pip install -r requirements.txt
```

#### 3. Configure the API Key

```bash
cp .env.example .env
```

Then edit `.env` and add your DashScope API Key.

DashScope website: https://dashscope.aliyun.com/

#### 4. Add the Dataset

Place the following files into `data/` or the configured data directory:

- `ratings.csv`: MovieLens-style ratings file with `userId, movieId, rating, timestamp`
- `movie_info.csv`: Movie metadata with `movieId, title, genres, year, cover_url, overview`

#### 5. Run the Server

```bash
flask --app flaskr run --debug
```

Open: http://127.0.0.1:5000

### Experiment Switches and A/B Testing Links

To support the course evaluation requirements, the system separates the recommendation algorithm and the explanation UI into two independent switches:

- `algorithm=baseline|enhanced`: Controls only the core recommendation ranking. `baseline` uses the original User-based KNN, while `enhanced` uses User-based KNN with timestamp decay weights.
- `explain=true|false`: Controls only whether the explanation UI is displayed, including Qwen-generated English recommendation reasons and structured reason tags. The LLM does not participate in recommendation ranking.

The legacy parameter `version=enhanced|baseline` is still supported, but the following controlled links are recommended for formal evaluation.

| Evaluation Purpose | Condition | Link |
|--------------------|-----------|------|
| Algorithm Evaluation Control Group | baseline algorithm + same UI | http://127.0.0.1:5000/?algorithm=baseline&explain=false |
| Algorithm Evaluation Experiment Group | enhanced algorithm + same UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation Control Group | same algorithm + no explanation | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation Experiment Group | same algorithm + explanation UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=true |

It is recommended to clarify that Qwen is used only for natural-language preference parsing and recommendation explanation. It is an interface and explainability enhancement, not part of the core ranking algorithm. Structured reason tags are generated by the backend from genre matches, predicted scores, highly rated movies, and feedback status; they improve explainability but do not change ranking.

### Modern Movie Catalog Layer

To address the issue that the original MovieLens catalog contains many older movies, the project adds an independent file: `data/ml_data/modern_movies.csv`. It currently contains 50 movies from 2016–2024, covering action, sci-fi, animation, comedy, romance, horror, mystery, music, family, war, and other genres. This file is used as an incremental movie pool, while the original `movie_info.csv` and `ratings.csv` remain unchanged.

Implementation details:

- `recommender/__init__.py` automatically merges `movie_info.csv` and `modern_movies.csv` when loading movie metadata.
- Modern movies use `movieId >= 900000` to avoid ID collisions with the original dataset.
- Modern movies are not added to the collaborative filtering rating matrix because they do not have real historical ratings.
- `recommender/engine.py` mixes a small number of cold-start modern picks into the KNN recommendation results.
- Modern picks are ranked by selected genres, movie recency, and the `popularity` field.
- Modern picks can show structured reason tags such as `Fresh pick`.

This creates a modern catalog layer on top of the original recommender, preserving the course dataset while improving the age distribution of movies shown to users.

### Explainable Recommendations and Feedback

The recommendation page now contains two explanation layers:

- **Natural-language explanation**: Qwen generates one short English reason for each recommended movie.
- **Structured reason tags**: The backend returns `reason_tags` for each movie, such as `Matched genre: Comedy, Romance`, `Similar to movies you rated highly`, `Fits your light-hearted preference`, and `Based on your recent feedback`.

User feedback behavior:

- Clicking **Like** records positive feedback for later content-based recommendations.
- Clicking **Dislike** hides the current movie, removes its Like state, and sends disliked movie IDs to the backend.
- Clicking **Find More Like These**, or clicking Dislike after at least one Like exists, calls `/api/feedback`, appends similar recommendations, and returns `feedback_summary`.

After feedback, the page displays an `Updated based on your feedback` panel, for example:

- `More Comedy and Romance`
- `Fewer Horror titles`
- `More movies similar to La La Land`

### Project Structure

```text
project/
├── app.py                    # Entry point
├── requirements.txt
├── .env.example              # API key configuration template
├── flaskr/
│   ├── __init__.py           # Flask initialization
│   └── routes.py             # API routes
├── recommender/
│   ├── __init__.py           # Data loading
│   ├── collaborative.py      # KNN collaborative filtering + timestamp decay
│   ├── content_based.py      # Content-based filtering + TF-IDF
│   ├── engine.py             # Unified recommendation entry
│   └── llm_helper.py         # Qwen API calls
├── templates/
│   └── index.html            # Vue.js frontend page
├── static/
│   └── app.js                # Vue.js logic
└── data/
    ├── ratings.csv
    ├── movie_info.csv
    └── modern_movies.csv       # Incremental modern movie pool
```

### Team Responsibilities

| Member | Main Files |
|--------|------------|
| Haozhe LIANG | `templates/index.html`, `static/app.js` |
| Feiyu LIU | `recommender/collaborative.py`, `recommender/content_based.py` |
| Jing LI | `flaskr/routes.py`, `recommender/engine.py`, `recommender/llm_helper.py` |

### Dependencies

- `scikit-surprise`: Collaborative filtering algorithms
- `scikit-learn`: TF-IDF text feature extraction
- `openai`: DashScope-compatible API calls
- `flask`: Web framework
