"""
Pydantic data models for macroeconomic news articles,
daily market predictions, evaluations, and OHLCV market data.

This module defines the core structured schemas used to parse,
validate, store, and evaluate macro-focused trading inputs and outputs.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

class NewsArticle(BaseModel):
    """Unified data model representing a parsed macroeconomic news article."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: str
    external_id: str
    title: str
    summary: Optional[str] = ""
    content: Optional[str] = ""
    url: str
    published_at: datetime
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hash: str


class DailyPrediction(BaseModel):
    """
    Strongly-typed structure representing the LLM's macroeconomic evaluation
    and directional hypothesis for the Nasdaq-100 market today.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    horizon: str = Field(..., description="Prediction horizon ('DAY', 'WEEK', 'MONTH')")
    prediction_for: datetime = Field(..., description="Date the agent is predicting the move for.")
    bullish_probability: float = Field(
        ..., description="Probability of an upward directional hypothesis for today. Range: 0.0 to 1.0."
    )
    bearish_probability: float = Field(
        ..., description="Probability of a downward directional hypothesis for today. Range: 0.0 to 1.0."
    )
    confidence: float = Field(
        ..., description="The analyst's confidence in this assessment based on data quality. Range: 0.0 to 1.0."
    )
    reasoning: str = Field(
        ..., description="Concise, evidence-based synthesis connecting the macro data directly to the directional hypothesis."
    )
    major_drivers: List[str] = Field(
        ..., description="List of top specific macroeconomic developments driving today's thesis."
    )
    invalidation: List[str] = Field(
        ..., description="Specific, observable market or data conditions that would prove this directional hypothesis wrong."
    )
    ignored_articles: List[str] = Field(
        ..., description="List of Article IDs or Hashes determined to be noise to macro conditions"
    )

    @model_validator(mode="after")
    def enforce_and_normalize_probabilities(self) -> "DailyPrediction":
        """
        Validates that directional probabilities approximate to 1.0.
        Automatically normalizes minor drift to enusre production robustness.
        """
        total = self.bullish_probability + self.bearish_probability

        # Allow a small error tolerance for LLM formatting variance
        if not (0.90 <= total <= 1.10):
            raise ValueError(f"Bullish and Bearish probabilities must sum close to 1.0. Got: {total}")

        # Automatically adjust and normalize to perfectly equal 1.0
        if total != 1.0:
            self.bullish_probability = round(self.bullish_probability / total, 4)
            self.bearish_probability = round(1.0 - self.bullish_probability, 4)

        return self


class Evaluation(BaseModel):
    """
    Evaluation result for a prediction against actual market movement.

    Attributes:
        id: Auto-generated primary key.
        prediction_id: Foreign key to predictions table.
        evaluated_at: Timestamp when evaluation was performed.
        observed_direction: Actual market direction (1 for bullish or -1 for bearish).
        return_points: Actual market close and market open difference.
        predicted_direction: Predicted direction (1 for bullish or -1 for bearish).
        prediction_score: Binary accuracy (0.0 or 1.0).
        notes: Optional context about the evaluation.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    prediction_id: uuid.UUID = Field(..., description="ID of the evaluated predcition")
    evaluated_at: datetime = Field(..., description="Evaluation timestamp")
    observed_direction: int = Field(..., description="Actual market direction")
    return_points: float = Field(..., description="Observed difference between market close and market open")
    predicted_direction: int = Field(..., description="Predicted market direction")
    prediction_score: float = Field(..., description="Binary accuracy score (0.0 or 1.0)")
    notes: Optional[str] = Field(..., description="Optional evaluation notes")


class MarketData(BaseModel):
    """
    OHLCV market data for a single trading day.

    Attributes:
        trading_day: Date of the trading session (primary key).
        open: Opening price.
        high: Highest price of the session.
        low: Lowest price of the session.
        close: Closing price.
        volume: Trading volume.
    """
    trading_day: datetime = Field(..., description="Date of the trading day")
    open: float = Field(..., description="Opening price of the session")
    high: float = Field(..., description="Highest price of the session")
    low: float = Field(..., description="Lowest price of the session")
    close: float = Field(..., description="Closing price of the session")
    volume: int = Field(..., description="Trading volume")
