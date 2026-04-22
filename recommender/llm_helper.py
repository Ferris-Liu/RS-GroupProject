import os
import json
import re
from openai import OpenAI

# DashScope 兼容 OpenAI 接口，只需替换 base_url
_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("未找到 DASHSCOPE_API_KEY，请检查 .env 文件")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    return _client


def _call_qwen(messages: list[dict], max_tokens: int = 150, temperature: float = 0.6) -> str:
    """统一的 Qwen 调用入口，失败时静默返回空字符串"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="qwen-plus",    # 免费额度，速度快，足够课程项目使用
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Qwen API 错误] {e}")
        return ""


# ────────────────────────────────────────────
# 功能一：推荐理由生成（方案一）
# ────────────────────────────────────────────

def generate_recommendation_reason(
    user_genres: list,
    movie_title: str,
    movie_genres: list,
    predicted_score: float | None,
    movie_year: str = "",
    movie_overview: str = ""
) -> str:
    """
    为单部推荐电影生成自然语言解释

    Returns:
        一句话推荐理由，失败时返回空字符串（前端不显示）
    """
    score_text = f"{predicted_score:.1f}/5" if predicted_score else "未知"
    genre_text = ", ".join(user_genres) if user_genres else "未明确说明"
    year_text = movie_year or "未知"
    overview_text = (movie_overview or "").strip()[:280]

    system_prompt = """你是电影推荐应用里的文案助手，负责给单部电影写一句推荐理由。

你的目标不是复述类型标签，而是像真正懂电影的朋友那样，说出这部片为什么可能打动这个用户。

输出规则：
- 只输出一句中文推荐理由，不加引号，不加书名号解释，不加前缀
- 控制在18到36个汉字左右，简洁但不要空泛
- 优先结合用户偏好和电影的具体看点，例如气质、节奏、剧情设定、人物关系、世界观
- 可以自然提到片名，但不要总是照搬模板
- 不要出现“这部电影值得一看”“根据你的喜好”“推荐给你”这类套话
- 不要只罗列类型词，不要只说“很适合你”
"""

    user_prompt = f"""请为下面这部电影生成一句推荐理由。

用户偏好类型：{genre_text}
电影标题：{movie_title}
电影类型：{', '.join(movie_genres)}
电影年份：{year_text}
预测评分：{score_text}
剧情简介：{overview_text or '暂无'}

参考风格：
- 喜欢科幻和悬疑：记忆迷宫层层反转，越往后越上头
- 喜欢爱情和剧情：克制又细腻的情感拉扯，后劲很足
- 喜欢动作和犯罪：节奏凌厉又够狠，追逐与对抗都很带感
"""

    reason = _call_qwen(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=80,
        temperature=0.8
    )

    cleaned = re.sub(r"\s+", " ", reason).strip().strip("“”\"'：:")
    cleaned = re.sub(r"^[Rr]eason[:：]\s*", "", cleaned)
    return cleaned


# ────────────────────────────────────────────
# 功能二：自然语言偏好解析（方案二）
# ────────────────────────────────────────────

VALID_GENRES = [
    "Action", "Comedy", "Drama", "Romance", "Thriller",
    "Sci-Fi", "Horror", "Animation", "Documentary", "Fantasy",
    "Adventure", "Crime", "Mystery", "Family", "Music"
]


def parse_user_preference(user_input: str) -> dict:
    """
    将用户的自然语言描述解析为结构化偏好

    Returns:
        {
            "genres": ["Comedy", "Romance"],
            "mood": "light",
            "keywords": ["搞笑", "温馨"]
        }
    """
    system_prompt = """你是电影偏好解析器。你只做信息抽取，不做聊天。

输出要求：
- 只返回合法 JSON
- 不要输出 markdown 代码块
- genres 只能从给定列表中选 1 到 3 个
- mood 只能是 light / intense / emotional / fun / thought-provoking 之一
- keywords 提取 1 到 3 个最关键的描述词
"""

    user_prompt = f"""用户描述："{user_input}"

可用的 genres 列表：{', '.join(VALID_GENRES)}

请返回以下格式：
{{
  "genres": ["从上方列表中选择1-3个最匹配的类型"],
  "mood": "选择一个：light / intense / emotional / fun / thought-provoking",
  "keywords": ["提取1-3个描述性关键词，用中文或英文均可"]
}}"""

    raw = _call_qwen(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=200,
        temperature=0.2
    )

    # 尝试解析JSON，失败时做容错处理
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试从回复中提取JSON块
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception:
                parsed = {}
        else:
            parsed = {}

    # 过滤无效genres，确保字段存在
    valid_genres = [g for g in parsed.get("genres", []) if g in VALID_GENRES]

    return {
        "genres": valid_genres or ["Drama"],          # 兜底默认值
        "mood": parsed.get("mood", "light"),
        "keywords": parsed.get("keywords", [])
    }
