"""
KaPak - OpenAI Client
Wraps the OpenAI SDK pointed at Google AI Studio's OpenAI-compatible endpoint.
Provides helpers for hashtag suggestion, sentiment analysis, and interest profiling.
"""

import json
import logging
from typing import Optional

from app.core.config import get_settings

try:
    from openai import OpenAI
    openai_available = True
except ImportError:
    openai_available = False

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenAIClient:
    """LLM client using OpenAI SDK via Google AI Studio endpoint."""

    def __init__(self):
        self.client = None
        self.is_active = False
        self.model = "gemini-2.5-flash"

        if not openai_available:
            logger.warning("openai package not installed. AI features will use mock fallbacks.")
            return

        api_key = settings.OPENAI_API_KEY or settings.GOOGLE_API_KEY
        base_url = settings.GOOGLE_BASE_URL if settings.GOOGLE_API_KEY else None

        if not api_key:
            logger.info("No AI API key configured. AI features will use mock fallbacks.")
            return

        try:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)
            self.is_active = True
            logger.info(f"OpenAI client initialized (model={self.model}, base_url={base_url})")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}. Using mock fallbacks.")

    def _call_ai(self, system_prompt: str, user_prompt: str, max_tokens: int = 80, temperature: float = 0.7) -> Optional[str]:
        if not self.is_active or not self.client:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                logger.warning("Rate limited — using mock fallback")
            else:
                logger.error(f"AI call failed: {err_str[:200]}")
            return None

    def _extract_json(self, text: str):
        import re
        md = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        clean = md.group(1).strip() if md else text.strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass
        arr = re.findall(r"\[([^\]]*)\]", clean)
        if arr:
            try:
                return json.loads(f"[{arr[-1]}]")
            except json.JSONDecodeError:
                pass
        obj = re.search(r"\{[^{}]*\}", clean)
        if obj:
            try:
                return json.loads(obj.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def suggest_hashtags(self, post_text: str) -> list[str]:
        system = (
            "Given a social media post, output exactly 3-5 relevant lowercase hashtags as a JSON array. "
            "Output ONLY the array, no markdown, no other text."
        )
        user = f"Post: {post_text}\n\nJSON array:"

        result = self._call_ai(system, user, max_tokens=500, temperature=0.5)

        if result:
            data = self._extract_json(result)
            if isinstance(data, list):
                return [str(t).lower().strip("#") for t in data if isinstance(t, str)][:5]
            logger.info(f"AI suggest_hashtags unparseable: {result[:200]}")

        return self._mock_suggest_hashtags(post_text)

    def analyze_sentiment(self, post_text: str) -> dict:
        system = (
            "Analyze the sentiment of this post. Output a JSON object with keys: "
            "sentiment (positive/negative/neutral), confidence (0-1), mood_tags (1-3 words). "
            "Output ONLY the JSON, no markdown, no other text."
        )
        user = f"Post: {post_text}\n\nJSON:"

        result = self._call_ai(system, user, max_tokens=500, temperature=0.3)

        if result:
            data = self._extract_json(result)
            if isinstance(data, dict):
                return data
            logger.info(f"AI analyze_sentiment unparseable: {result[:200]}")

        return self._mock_analyze_sentiment(post_text)

    # ── Mock fallbacks ─────────────────────────────────────

    def _mock_suggest_hashtags(self, post_text: str) -> list[str]:
        import re
        existing = re.findall(r"#(\w+)", post_text.lower())
        words = re.findall(r"\b[a-z]{4,}\b", post_text.lower())
        stopwords = {"this", "that", "with", "from", "have", "been", "were", "they", "your", "just", "what", "when", "about", "some", "than", "then", "over", "also", "into", "after", "before", "being", "doing"}
        keywords = [w for w in words if w not in stopwords]
        combined = list(dict.fromkeys(existing + keywords))  # deduplicate preserving order
        defaults = ["kapak"]
        return (combined or defaults)[:5]

    def _mock_analyze_sentiment(self, post_text: str) -> dict:
        positive_words = ["love", "great", "amazing", "happy", "awesome", "good", "excited"]
        negative_words = ["hate", "bad", "terrible", "sad", "angry", "awful", "worst"]

        lower = post_text.lower()
        pos_count = sum(1 for w in positive_words if w in lower)
        neg_count = sum(1 for w in negative_words if w in lower)

        if pos_count > neg_count:
            return {"sentiment": "positive", "confidence": 0.7, "mood_tags": ["happy"]}
        elif neg_count > pos_count:
            return {"sentiment": "negative", "confidence": 0.7, "mood_tags": ["upset"]}
        return {"sentiment": "neutral", "confidence": 0.5, "mood_tags": ["neutral"]}
