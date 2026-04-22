# 电影推荐系统

基于课程 Demo (RS_demo_2026) 的增强版推荐系统，集成 Qwen 大模型。

## 功能特点

- **增强协同过滤**：User-based KNN + 时间戳衰减权重
- **增强内容过滤**：Genres multi-hot + TF-IDF 剧情概要
- **Qwen 推荐理由**：为每部推荐电影生成自然语言解释
- **自然语言偏好输入**：用一句话描述想看的电影，自动解析类型
- **A/B 测试支持**：URL 参数切换 baseline/enhanced 版本

## 快速开始

### 1. 创建虚拟环境

```bash
conda create -n rs_project python=3.10
conda activate rs_project
```

### 2. 安装依赖

```bash
pip install --upgrade setuptools wheel
conda install -c conda-forge scikit-surprise
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 DashScope API Key
# 获取地址：https://dashscope.aliyun.com/
```

### 4. 放入数据集

将以下文件放入 `data/` 目录：
- `ratings.csv`（MovieLens 格式：userId, movieId, rating, timestamp）
- `movie_info.csv`（movieId, title, genres, year, cover_url, overview）

### 5. 启动服务

```bash
flask --app flaskr run --debug
```

访问 http://127.0.0.1:5000

## 实验开关与 A/B 测试链接

为满足课程要求，系统把“推荐算法”和“界面解释”拆成两个独立开关：

- `algorithm=baseline|enhanced`：只控制核心推荐排序。`baseline` 使用原始 User-based KNN；`enhanced` 使用加入时间衰减权重的 User-based KNN。
- `explain=true|false`：只控制是否展示 Qwen 生成的推荐理由。LLM 不参与推荐排序。

旧版 `version=enhanced|baseline` 仍可使用，但正式评测建议使用下面的控制变量链接。

| 评测目的 | 条件 | 链接 |
|----------|------|------|
| Algorithm Evaluation 对照组 | baseline algorithm + same UI | http://127.0.0.1:5000/?algorithm=baseline&explain=false |
| Algorithm Evaluation 实验组 | enhanced algorithm + same UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation 对照组 | same algorithm + no explanation | http://127.0.0.1:5000/?algorithm=enhanced&explain=false |
| UI Evaluation 实验组 | same algorithm + explanation UI | http://127.0.0.1:5000/?algorithm=enhanced&explain=true |

报告中建议明确写：Qwen 只用于 natural-language preference parsing 和 recommendation explanation，是界面与解释性增强，不属于核心推荐排序算法。

## 项目结构

```
project/
├── app.py                    # 入口
├── requirements.txt
├── .env.example              # API Key 配置模板
├── flaskr/
│   ├── __init__.py           # Flask 初始化
│   └── routes.py             # 所有 API 路由
├── recommender/
│   ├── __init__.py           # 数据加载（单例）
│   ├── collaborative.py      # KNN 协同过滤 + 时间衰减
│   ├── content_based.py      # CBF + TF-IDF
│   ├── engine.py             # 统一推荐入口
│   └── llm_helper.py         # Qwen API 调用
├── templates/
│   └── index.html            # Vue.js 前端页面
├── static/
│   └── app.js                # Vue.js 逻辑
└── data/
    ├── ratings.csv           # (自行放入)
    └── movie_info.csv        # (自行放入)
```

## 分工说明

| 成员 | 主要负责文件 |
|------|-------------|
| A（前端） | templates/index.html, static/app.js |
| B（算法） | recommender/collaborative.py, recommender/content_based.py |
| C（后端） | flaskr/routes.py, recommender/engine.py, recommender/llm_helper.py |

## 依赖说明

- `scikit-surprise`：协同过滤算法
- `scikit-learn`：TF-IDF 文本特征提取
- `openai`：兼容 DashScope API 的调用方式
- `flask`：Web 框架
