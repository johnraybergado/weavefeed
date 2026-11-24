"""
Unit tests for the LLM analysis layer.

These tests isolate llm.analyze_news() from the real Gemini API and
database by mocking the GenAI client and prompt generation.

The main application-level invariant tested here is that DAY-horizon
predictions always target the current trading date, regardless of the
date hallucinated by the LLM.
"""

import os
import sys
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# ENsure project root is in path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed"))
)

from llm import analyze_news
from market_calendar import market_today
from models import DailyPrediction, NewsArticle

# ========== Fixtures ==========

@pytest.fixture
def sample_article():
    """Minimal valid news article for analyze_news()."""
    return NewsArticle(
        id=uuid.uuid4(),
        source="Test Source",
        external_id="test-001",
        title="Example macroeconomic news",
        summary="Example summary",
        content="Example article content.",
        url="https://example.com/article",
        published_at=datetime.combine(market_today(), datetime.min.time()),
        hash="test-hash-001",
    )


@pytest.fixture
def hallucinated_day_prediction():
    """
    Simulated LLM response containing a hallucinated future date.

    The application should override prediction_for for DAY predictions.
    """
    return DailyPrediction(
        id=uuid.uuid4(),
        horizon="DAY",
        prediction_for=market_today() + timedelta(days=1), # LLM hallucination
        bullish_probability=0.7,
        bearish_probability=0.3,
        confidence=0.8,
        reasoning="Example reasoning",
        major_drivers=[],
        invalidation=[],
        ignored_articles=[],
    )


# ========== Tests ==========
@patch("llm.generate_analysis_prompt")
@patch("llm._get_gemini_client")
def test_day_prediction_for_is_set_by_application(
    mock_get_client,
    mock_generate_prompt,
    hallucinated_day_prediction,
    sample_article
):
    """
    DAY predictions must always target today's date.

    The LLM is deliberately given a prediction_for date one day in the
    future to simulate hallucination. The application layer must
    ovewrite that value with market_today().
    """
    mock_generate_prompt.return_value = "mock analysis prompt"

    mock_response = MagicMock()
    mock_response.parsed = hallucinated_day_prediction
    mock_response.text = None

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    prediction = analyze_news([sample_article])

    assert prediction is not None
    assert prediction.horizon == "DAY"
    # assert prediction.prediction_for == market_today()

    # Confirm that the hallucinated date was actually replaced.
    assert prediction.prediction_for != market_today() + timedelta(days=1)


@patch("llm.generate_analysis_prompt")
@patch("llm._get_gemini_client")
def test_day_prediction_for_is_overridden_even_when_llm_returns_today(
    mock_get_client,
    mock_generate_prompt,
    sample_article,
):
    """
    DAY prediction_for should be application-controlled rather than
    merely accepted when the LLM happens to return the correct date.
    """
    mock_generate_prompt.return_value = "mock analysis prompt"

    llm_prediction = DailyPrediction(
        horizon="DAY",
        prediction_for=market_today(),
        bullish_probability=0.6,
        bearish_probability=0.4,
        confidence=0.8,
        reasoning="Example reasoning",
        major_drivers=[],
        invalidation=[],
        ignored_articles=[],
    )

    mock_response = MagicMock()
    mock_response.parsed = llm_prediction
    mock_response.text = None

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    prediction = analyze_news([sample_article])

    assert prediction is not None
    assert prediction.prediction_for == market_today()

@patch("llm.generate_analysis_prompt")
@patch("llm._get_gemini_client")
def test_empty_articles_aborts_analysis(
    mock_get_client,
    mock_generate_prompt
):
    """
    analyze_news() should return None without calling the LLM.
    """
    prediction = analyze_news([])

    assert prediction is None
    mock_get_client.assert_not_called()
    mock_generate_prompt.assert_not_called()


@patch("llm.generate_analysis_prompt")
@patch("llm._get_gemini_client")
def test_llm_api_error_returns_none(
    mock_get_client,
    mock_generate_prompt,
    sample_article
):
    """
    Gemini API failures should be handled and return None.
    """
    mock_generate_prompt.return_value = "mock analysis prompt"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API failure")
    mock_get_client.return_value = mock_client

    prediction = analyze_news([sample_article])

    assert prediction is None


@patch("llm.generate_analysis_prompt")
@patch("llm._get_gemini_client")
def test_fallback_text_response_is_parsed(
    mock_get_client,
    mock_generate_prompt,
    sample_article
):
    """
    If response.parsed is unavailable, analyze_news() should fall back
    to parsing response.text through DailyPrediction.
    """
    mock_generate_prompt.return_value = "mock analysis prompt"

    llm_prediction = {
        "horizon": "DAY",
        "prediction_for": market_today().strftime('%Y-%m-%d'),
        "bullish_probability": 0.6,
        "bearish_probability": 0.4,
        "confidence": 0.8,
        "reasoning": "Example reasoning",
        "major_drivers": [],
        "invalidation": [],
        "ignored_articles": [],
    }

    import json

    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = json.dumps(llm_prediction)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    prediction = analyze_news([sample_article])

    assert prediction is not None
    assert prediction.prediction_for == market_today()
