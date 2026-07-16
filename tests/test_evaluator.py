"""Integration tests for the evaluation layer."""
import sys
import os
import uuid
from unittest import mock
from datetime import date, datetime
from unittest.mock import patch, MagicMock, create_autospec
import psycopg2
import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed")))
from models import DailyPrediction, Evaluation, MarketData
from evaluator import (
    determine_observed_direction,
    determine_predicted_direction,
    compute_prediction_score,
    evaluate_prediction,
    evaluate_all_pending
)


# ========== Fixtures ==========
@pytest.fixture
def prediction_up():
    return DailyPrediction(
        id=uuid.uuid4(), run_id=1, horizon="DAY", prediction_for=date(2026, 7, 13),
        bullish_probability=0.7, bearish_probability=0.3, confidence=0.8,
        reasoning="Strong tech", invalidation=[], major_drivers=[],
        ignored_articles=[], created_at=datetime(2026, 7, 13, 15, 45, 0)
    )

@pytest.fixture
def prediction_down():
    return DailyPrediction(
        id=uuid.uuid4(), run_id=2, horizon="DAY", prediction_for=date(2026, 7, 14),
        bullish_probability=0.2, bearish_probability=0.8, confidence=0.7,
        reasoning="Fed hike", invalidation=[], major_drivers=[],
        ignored_articles=[], created_at=datetime(2026, 7, 14, 15, 45, 0)
    )

@pytest.fixture
def market_data_up():
    return MarketData(
        trading_day=date(2026, 7, 13),
        open=100.0, high=101.0, low=99.0, close=101.0, volume=1000000
    )

@pytest.fixture
def market_data_down():
    return MarketData(
        trading_day=date(2026, 7, 14),
        open=100.0, high=100.5, low=99.0, close=99.0, volume=1200000
    )

@pytest.fixture
def market_data_updated():
    return MarketData(
        trading_day=date(2026, 7, 13),
        open=102.0, high=103.0, low=101.0, close=102.5, volume=1500000
    )

# ========== Unit Tests ==========
class TestDirectionHelpers:
    def test_observed_up(self):
        assert determine_observed_direction(100.0, 101.0) == 1
        assert determine_observed_direction(100.0, 100.01) == 1

    def test_observed_down(self):
        assert determine_observed_direction(100.0, 99.0) == -1
        assert determine_observed_direction(100.0, 100.0) == -1

    def test_predicted_up(self, prediction_up):
        assert determine_predicted_direction(prediction_up) == 1

    def test_predicted_down(self, prediction_down):
        assert determine_predicted_direction(prediction_down) == -1

class TestScoring:
    def test_score_correct(self):
        assert compute_prediction_score(1, 1) == 1.0
        assert compute_prediction_score(-1, -1) == 1.0

    def test_score_incorrect(self):
        assert compute_prediction_score(1, -1) == 0.0
        assert compute_prediction_score(-1, 1) == 0.0

# ========== Integration Test ==========
@patch('database.get_connection')
@patch('evaluator.get_predictions_pending_evaluation')
@patch('evaluator.store_evaluation')
@patch('evaluator.store_market_data')
@patch('evaluator.get_nq_daily_data')
def test_evaluate_all_pending_stores_market_data(
    mock_get_data, mock_store_market, mock_store_eval, mock_get_pending, mock_connect,
    prediction_up, prediction_down, market_data_up, market_data_down, capsys
):
    """
    Full workflow test:
    fetch predictions -> store market -> data evaluate -> store evaluation -> report.
    """
    call_order = []

    # Setup mocks
    mock_get_pending.return_value = [prediction_up, prediction_down]
    mock_get_data.side_effect = [market_data_up, market_data_down]

    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    def mock_store_market_side_effect(market_data):
        call_order.append('market')
        return market_data

    def mock_store_eval_side_effect(evaluation):
        call_order.append('eval')
        return evaluation

    mock_store_market.side_effect = mock_store_market_side_effect
    mock_store_eval.side_effect = mock_store_eval_side_effect

    # Execute
    evaluations = evaluate_all_pending()

    # Verify store_market_data was called for each prediction
    assert mock_store_market.call_count ==2, "store_market_data not called for all predictions"

    # Verify store_evaluation was called for each prediction
    assert mock_store_eval.call_count ==2, "store_evaluation not called for all predictions"

    # Verify market data was stored before evaluation for each prediction
    # Check call order: store_market_data calls should precede store_evaluation calls
    assert call_order == ['market', 'eval', 'market', 'eval'], \
        f"Call order incorrect: {call_order}. Expected market before eval for each prediction."

    # Verify existing evaluation logic still works
    assert len(evaluations) == 2
    assert evaluations[0].prediction_score == 1.0 # Correct UP prediction

    # Print report
    total = len(evaluations)
    correct = sum(1 for e in evaluations if e.prediction_score == 1.0)
    accuracy = correct / total if total > 0 else 0
    print("\n=== Evaluation Report ===")
    for e in evaluations:
        print(f"Pred {e.prediction_id}: {e.predicted_direction} vs {e.observed_direction} | Score: {e.prediction_score}")
    print(f"Total: {total} | Correct: {correct} | Accuracy: {accuracy:.2%}")
    print("Market data stored for all predictions")
    print("=========================")

    captured = capsys.readouterr()
    assert "Evaluation Report" in captured.out
    assert "Market data stored" in captured.out


# ========== Market Data Upsert Tests ==========
class TestMarketDataUpsert:
    """Test for market_data upsert behavior."""

    @patch('database.get_connection')
    def test_store_market_data_upsert_same_day(self, mock_connect, market_data_up, market_data_updated):
        """Test that upsert updates existing row on same trading_day."""
        from database import store_market_data

        mock_conn = create_autospec(psycopg2.extensions.connection, instance=True)
        mock_cursor = create_autospec(psycopg2.extensions.cursor, instance=True)

        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False

        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False

        mock_connect.return_value = mock_conn

        # First insert
        store_market_data(market_data_up)

        first_call_args = mock_cursor.execute.call_args[0][1]

        # Second insert
        store_market_data(market_data_updated)
        second_call_args = mock_cursor.execute.call_args[0][1]

        # Verify both calls were made
        assert mock_cursor.execute.call_count == 2

        # Verify the SQL query contains ON CONFLICT
        query = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT (trading_day)" in query
        assert "DO UPDATE SET" in query

        # Verify second call had updated values
        assert second_call_args[1] == 102.0  # open
        assert second_call_args[2] == 103.0  # high
        assert second_call_args[3] == 101.0  # low
        assert second_call_args[4] == 102.5  # close
        assert second_call_args[5] == 1500000  # volume

    @patch('database.get_connection')
    def test_store_market_data_no_exception_on_duplicate(self, mock_connect, market_data_up):
        """Test that duplicate trading_day does not raise an exception."""
        from database import store_market_data

        mock_conn = create_autospec(psycopg2.extensions.connection, instance=True)
        mock_cursor = create_autospec(psycopg2.extensions.cursor, instance=True)

        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False

        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False

        mock_connect.return_value = mock_conn

        # Call twice the same data
        store_market_data(market_data_up)
        store_market_data(market_data_up)

        # Should not raise, and should have made 2 calls
        assert mock_cursor.execute.call_count == 2

    @patch('database.get_connection')
    def test_store_market_data_returns_input(self, mock_connect, market_data_up):
        """Test that store_market_data returns the input object."""
        from database import store_market_data

        mock_conn = create_autospec(psycopg2.extensions.connection, instance=True)
        mock_cursor = create_autospec(psycopg2.extensions.cursor, instance=True)

        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False

        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False

        mock_connect.return_value = mock_conn

        result = store_market_data(market_data_up)
        assert result == market_data_up
