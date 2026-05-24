"""
KaPak - AI Service
Integrates with OpenAI to provide automated text refinement and style changes.
Provides a mock fallback when OpenAI credentials are not provided.
"""

import logging
from app.core.config import get_settings

try:
    import openai
    from openai import OpenAI
    openai_available = True
except ImportError:
    openai_available = False

logger = logging.getLogger(__name__)
settings = get_settings()


class AIService:
    """Service to handle AI text operations using OpenAI GPT models."""

    def __init__(self):
        self.client = None
        self.is_active = False
        self.model = "gemini-2.5-flash"

        if not openai_available:
            logger.warning("openai package not installed. AI will operate in Mock Mode.")
            return

        api_key = settings.OPENAI_API_KEY or settings.GOOGLE_API_KEY
        base_url = settings.GOOGLE_BASE_URL if settings.GOOGLE_API_KEY else None

        if not api_key:
            logger.info("No AI API key configured. Operating in Mock Mode.")
            return

        try:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)
            self.is_active = True
            logger.info(f"OpenAI client initialized (model={self.model})")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}. AI will operate in Mock Mode.")

    def refine_text(self, text: str, style: str = "casual") -> str:
        """
        Refine post content using generative models or mock fallbacks.
        Supported styles: 'casual', 'professional', 'witty', 'concise'.
        """
        if not text or not text.strip():
            return ""

        # Map desired styles to target prompt instruction
        style_instructions = {
            "professional": "Rewrite this text in a professional, polite, and articulate tone suitable for a business environment.",
            "witty": "Rewrite this text in a clever, humorous, and engaging tone with high readability.",
            "concise": "Rewrite this text in a direct, clear, and extremely concise manner, saving characters.",
            "casual": "Rewrite this text in a friendly, conversational, and natural tone."
        }

        instruction = style_instructions.get(style.lower(), style_instructions["casual"])

        if self.is_active and self.client:
            try:
                prompt = (
                    f"You are a social media copilot. {instruction}\n"
                    f"Ensure any #hashtags and @mentions from the original text are kept intact.\n"
                    f"Return ONLY the refined post text. Do not include any explanation or quote marks.\n\n"
                    f"Original Text: {text}"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional copywriter."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=250,
                    temperature=0.7
                )

                refined_result = response.choices[0].message.content
                if refined_result:
                    return refined_result.strip()
            except Exception as e:
                logger.error(f"OpenAI text refinement API error: {e}. Falling back to mock refinement.")

        # Fallback Mock Refinement
        return self._mock_refine_text(text, style)

    def _mock_refine_text(self, text: str, style: str) -> str:
        """Simulate refinement locally when OpenAI is inactive."""
        # Simple enhancements based on style
        clean_text = text.strip()
        
        if style.lower() == "professional":
            return f"I would like to state: {clean_text} #Professional"
        elif style.lower() == "witty":
            return f"Did you know? {clean_text} 😉 #Witty"
        elif style.lower() == "concise":
            return f"{clean_text[:100]}... #Short"
        else:
            # Default casual
            return f"{clean_text}! 😊"
