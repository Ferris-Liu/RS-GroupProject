# 电影推荐系统 / Movie Recommendation System

> 中文说明见上半部分。English documentation is available in the second half.

## 中文版

基于课程 Demo `RS_demo_2026` 的增强版电影推荐系统，集成 Qwen 大模型，用于自然语言偏好解析与推荐理由生成。

### 功能特点

- **增强协同过滤**：User-based KNN + 时间戳衰减权重
- **增强内容过滤**：Genres multi-hot + TF-IDF 剧情概要
- **Qwen 推荐理由**：为每部推荐电影生成自然语言解释
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
- `explain=true|false`：只控制是否展示 Qwen 生成的推荐理由。LLM 不参与推荐排序。

旧版 `version=enhanced|baseline` 仍可使用，但正式评测建议使用下面的控制变量链接。

| 评测目的 | 条件 | 链接 |
|----------|------|------|
| Algorithm Evaluation 对照组 | baseline algorithm + same UI | http://127.0.0.1:5000/?algorithm=baseline&explain=false |
| Algorithm Evaluation 实验组 | enhanced algorithm + same UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation 对照组 | same algorithm + no explanation | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation 实验组 | same algorithm + explanation UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=true |

说明：Qwen 只用于 natural-language preference parsing 和 recommendation explanation，是界面与解释性增强，不属于核心推荐排序算法。

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
    └── movie_info.csv
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
- **Qwen-powered explanations**: Generates natural-language explanations for recommended movies
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
- `explain=true|false`: Controls only whether Qwen-generated recommendation explanations are displayed. The LLM does not participate in recommendation ranking.

The legacy parameter `version=enhanced|baseline` is still supported, but the following controlled links are recommended for formal evaluation.

| Evaluation Purpose | Condition | Link |
|--------------------|-----------|------|
| Algorithm Evaluation Control Group | baseline algorithm + same UI | http://127.0.0.1:5000/?algorithm=baseline&explain=false |
| Algorithm Evaluation Experiment Group | enhanced algorithm + same UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation Control Group | same algorithm + no explanation | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation Experiment Group | same algorithm + explanation UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=true |

It is recommended to clarify that Qwen is used only for natural-language preference parsing and recommendation explanation. It is an interface and explainability enhancement, not part of the core ranking algorithm.

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
    └── movie_info.csv
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
