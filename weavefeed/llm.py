"""Generate macroeconomic analysis via an LLM API"""
import logging
from typing import Optional
from datetime import date
from google import genai
from google.genai import types
from google.genai.errors import APIError

from config import settings
from models import NewsArticle, DailyPrediction
from prompts import SYSTEM_PROMPT, generate_analysis_prompt

logger = logging.getLogger(__name__)

def _get_gemini_client() -> genai.Client:
    """Initializes and returns the official Google GenAI Client instance."""
    # The SDK automatically checks for GEMINI_API_KEY environment variable if settings.google_api_key is empty
    return genai.Client(api_key=settings.google_api_key)


def analyze_news(articles: list[NewsArticle]) -> Optional[DailyPrediction]:
    """
    Transforms a list of raw news documents into a unified, structured daily directive
    using the Gemini API with schema enforcement.

    Returns:
        DailyPrediction object if successful; None if an API or validation error occurs.
    """
    if not articles:
        logger.warning("No articles supplied to analyze_news. Generation aborted.")
        return None

    client = _get_gemini_client()
    analysis_prompt = generate_analysis_prompt(articles)

    # Configure request to strictly enforce structural output specifications
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.1, # Low temperature to reduce hallucination and ensure systematic analysis
        response_mime_type="application/json",
        response_schema=DailyPrediction,
    )

    try:
        logger.info(f"Dispatching single analysis payload containing {len(articles)} articles to LLM analyst...")

        response = client.models.generate_content(
            model=settings.llm_model,
            contents=analysis_prompt,
            config=config
        )

        # The new google-genai SDK natively populates response.parsed when response_schema is provided
        if response.parsed:
            prediction = response.parsed
        # Fallback parsing strategy in case of version-specific SDK variances
        elif response.text:
            logger.debug("Falling back to explicit Pydantic JSON parsing execution.")
            prediction = DailyPrediction.model_validate_json(response.text)
        else:
            raise ValueError("Gemini API generated an empty response payload.")

        # enforce daily horizon prediction is the same date 
        # as when the prediciton workflow is ran
        if prediction.horizon == "DAY":
            prediction.prediction_for = date.today()

        return prediction

    except APIError as api_err:
        logger.error(f"Google GenAI SDK Network/API execution fault: {api_err}", exc_info=True)
        return None
    except Exception as parse_err:
        logger.error(f"Critical error converting or validating structured prediction data: {parse_err}", exc_info=True)
        return None