"""Evaluation layer for Weavefeed predictions.

Compares DailyPredictions against actual NQ futures market movements.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List
import yfinance as yf
from models import DailyPrediction, Evaluation, MarketData
from database import (
    get_predictions_pending_evaluation,
    store_evaluation,
    store_market_data
)

logger = logging.getLogger(__name__)

NQ_TICKER = "NQ=F" # Nasdaq-100 E-mini futures on Yahoo Finance
MARKET_DATA_SOURCE = "Yahoo Finance (yfinance)"

def get_nq_daily_data(target_date: date) -> Optional[MarketData]:
    """
    Fetch NQ futures OHLCV data for a specific date.

    Args:
        target_date: Date to fetch market data for.

    Returns:
        MarketData object or None if unavailable.
    """
    try:
        nq = yf.Ticker(NQ_TICKER)
        # Fetch a small range to handle date alignment
        start = target_date - timedelta(days=2)
        end = target_date + timedelta(days=1)
        df = nq.history(start=start, end=end)

        if df.empty:
            logger.warning(f"No market data for {target_date} from {MARKET_DATA_SOURCE}")
            return None

        for idx, row in df.iterrows():
            if idx.date() == target_date.date():
                return MarketData(
                    trading_day=target_date,
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume'])
                )
        logger.warning(f"Target date {target_date} not found in market data")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch data for {target_date}: {e}")
        return None


def determine_observed_direction(open_price: float, close_price: float) -> int:
    """
    Derive market direction from open/close prices.

    Returns:
        1 if close > open, else -1.
    """
    return 1 if close_price > open_price else -1


def determine_predicted_direction(prediction: DailyPrediction) -> int:
    """
    Derive predicted direction from prediction probabilities.

    Returns:
        1 if bullish_probability > bearish_probability, else -1
    """
    return 1 if prediction.bullish_probability > prediction.bearish_probability else -1


def compute_prediction_score(predicted: str, observed: str) -> float:
    """
    Compute binary accuracy score.

    Returns:
        1.0 if predicted == observed, else 0.0.
    """
    return 1.0 if predicted == observed else 0.0


def evaluate_prediction(prediction: DailyPrediction, market_data: MarketData) -> Optional[Evaluation]:
    """
    Evaluate a single prediction against market data.

    Returns:
        Evaluation object if market data available, else None.
    """
    observed = determine_observed_direction(market_data.open, market_data.close)
    predicted = determine_predicted_direction(prediction)
    return_points = market_data.close - market_data.open
    return Evaluation(
        prediction_id=prediction.id,
        evaluated_at=datetime.now(),
        observed_direction=observed,
        return_points=return_points,
        predicted_direction=predicted,
        prediction_score=compute_prediction_score(predicted, observed),
        notes=f"Evaluated using {MARKET_DATA_SOURCE} for {NQ_TICKER}"
    )


def evaluate_all_pending() -> List[Evaluation]:
    """
    Evaluate all pending predictions and store results.

    Returns:
        List[Evaluation]: Successfully stored evaluations.
    """
    predictions = get_predictions_pending_evaluation()
    evaluations = []

    for prediction in predictions:
        logger.info(f"Evaluating prediction {prediction.id} for {prediction.prediction_for}")
        market_data = get_nq_daily_data(prediction.prediction_for)
        if not market_data:
            logger.warning(f"Skipping prediction {prediction.id}: no market data for {prediction.prediction_for}")
            continue
        # Store market data BEFORE any evaluation calculations
        store_market_data(market_data)
        try:
            eval_result = evaluate_prediction(prediction, market_data)
            if eval_result:
                stored = store_evaluation(eval_result)
                evaluations.append(stored)
        except Exception as e:
            logger.error(f"Error evaluating prediction {prediction.id}: {e}")

    return evaluations
