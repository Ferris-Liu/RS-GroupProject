import os
import json
import re

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None

# DashScope 兼容 OpenAI 接口，只需替换 base_url
_client = None

def _get_client() -> OpenAI:
    global _client
    if OpenAI is None:
        raise RuntimeError("openai package is not installed. Install requirements.txt to enable Qwen features.")
    if _client is None:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY was not found. Please check your .env file.")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    return _client


def _call_qwen(messages: list[dict], max_tokens: int = 150, temperature: float = 0.6) -> str:
    """统一的 Qwen 调用入口，失败时静默返回空字符串"""
    if OpenAI is None:
        return ""

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
        print(f"[Qwen API error] {e}")
        return ""


def is_qwen_available() -> bool:
    """检查 Qwen 调用依赖是否可用"""
    return OpenAI is not None and bool(os.getenv("DASHSCOPE_API_KEY"))


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
    score_text = f"{predicted_score:.1f}/5" if predicted_score else "unknown"
    genre_text = ", ".join(user_genres) if user_genres else "not specified"
    year_text = movie_year or "unknown"
    overview_text = (movie_overview or "").strip()[:280]

    system_prompt = """You are the copy assistant for a movie recommendation app.

Your job is to write one short English recommendation reason for a single movie.

Output rules:
- Output English only.
- Write exactly one sentence, with no quotes, labels, prefixes, or bullet points.
- Keep it concise: about 12 to 22 words.
- Mention a concrete appeal such as mood, pace, premise, character dynamic, setting, or emotional hook.
- Do not merely repeat genre labels.
- Avoid generic lines like "This movie is worth watching", "Based on your taste", or "you will love this".
"""

    user_prompt = f"""Write one recommendation reason for this movie.

User preferred genres: {genre_text}
Movie title: {movie_title}
Movie genres: {', '.join(movie_genres)}
Movie year: {year_text}
Predicted score: {score_text}
Overview: {overview_text or 'Not available'}

Style examples:
- A layered mystery with sharp turns and a tense slow-burn payoff.
- Gentle romantic tension gives the story a warm, lingering aftertaste.
- Fast, gritty confrontations keep the stakes high from scene to scene.
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
            "keywords": ["funny", "warm"]
        }
    """
    system_prompt = """You are a movie preference parser. Extract information only; do not chat.

Output requirements:
- Return valid JSON only.
- Do not output a markdown code block.
- genres must contain 1 to 3 items selected only from the provided list.
- mood must be one of: light / intense / emotional / fun / thought-provoking.
- keywords must contain 1 to 3 concise English descriptors.
"""

    user_prompt = f"""User description: "{user_input}"

Available genres: {', '.join(VALID_GENRES)}

Return this format:
{{
  "genres": ["choose 1-3 best matching genres from the list above"],
  "mood": "choose one: light / intense / emotional / fun / thought-provoking",
  "keywords": ["extract 1-3 descriptive keywords in English"]
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
