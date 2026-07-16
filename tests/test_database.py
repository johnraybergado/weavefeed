import os
import sys
import uuid
from datetime import datetime, date
from typing import List
from unittest.mock import patch, MagicMock, create_autospec
import pytest
import psycopg2
from psycopg2.extras import execute_values, DictCursor

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed")))
from models import DailyPrediction, NewsArticle, Evaluation, MarketData
from database import (
    store_evaluation,
    store_market_data,
    store_prompt_template,
    create_agent_run,
    complete_agent_run,
    store_prediction,
    link_prediction_evidence,
    persist_analysis_run,
    get_predictions_pending_evaluation,
    store_evaluation,
    store_market_data
)

# ========== Fixtures ==========

@pytest.fixture
def sample_prediction():
    return DailyPrediction(
        id=uuid.uuid4(),
        horizon="DAY",
        prediction_for=datetime(2026, 7, 15, 9, 30),
        bullish_probability=0.7,
        bearish_probability=0.3,
        confidence=0.8,
        reasoning="Strong tech earnings driving bullish sentiment",
        major_drivers=["Fed pause", "AI capex"],
        invalidation=["Hot CPI", "Yield spike"],
        ignored_articles=["hash_1", "hash_2"],
    )

@pytest.fixture
def sample_evaluation():
    return Evaluation(
        id=uuid.uuid4(),
        prediction_id=uuid.uuid4(),
        evaluated_at=datetime(2026, 7, 15, 10, 0),
        observed_direction=1,
        return_points=1.5,
        predicted_direction=1,
        prediction_score=1.0,
        notes="Perfect prediction",
    )

@pytest.fixture
def sample_market_data():
    return MarketData(
        trading_day=datetime(2026, 7, 15, 9, 30),
        open=100.0,
        high=101.0,
        low=99.30,
        close=101.0,
        volume=1000000,
    )

@pytest.fixture
def sample_news_article():
    return NewsArticle(
        id=uuid.uuid4(),
        source="test",
        external_id="1",
        title="Test 1",
        url="http://test1",
        published_at=datetime.now(),
        hash="hash1",
    )

@pytest.fixture
def mock_conn():
    return create_autospec(psycopg2.extensions.connection, instance=True)

@pytest.fixture
def mock_cursor():
    return create_autospec(psycopg2.extensions.cursor, instance=True)

@pytest.fixture
def mock_dictcursor():
    return create_autospec(DictCursor, instance=True)

# ========== store_prompt_template Tests ==========

class TestStorePrompTemplate:
    """Test for prompt template storage with upsert behavior."""

    @patch('database.get_connection')
    def test_store_new_prompt_template_returns_uuid(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify new prompt template insert returns UUID string."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        template_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (template_id,)

        version = "v1"
        system_prompt = "System prompt"
        user_prompt = "User prompt"

        result = store_prompt_template(version, system_prompt, user_prompt)

        assert isinstance(result, str)
        uuid.UUID(result)
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO prompt_templates" in args[0]
        assert version in args[1]
        assert system_prompt in args[1]
        assert user_prompt in args[1]

    @patch('database.get_connection')
    def test_store_existing_prompt_template_returns_existing_id(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify existing version returns existing ID without duplicate."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        existing_id = uuid.uuid4()

        mock_cursor.fetchone.side_effect = [None, (existing_id,)]

        version = "v1"
        system_prompt = "System prompt"
        user_prompt = "User prompt"

        result = store_prompt_template(version, system_prompt, user_prompt)

        assert isinstance(result, str)
        assert uuid.UUID(result) == existing_id
        assert mock_cursor.execute.call_count == 2
        second_call_args = mock_cursor.execute.call_args_list[1][0]
        assert "SELECT id FROM prompt_templates WHERE version = %s" in second_call_args[0]

# ========== create_agent_run Tests ==========

class TestCreateAgentRun:
    """Tests for agent run creation."""

    @patch('database.get_connection')
    def test_create_agent_run_returns_uuid(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify new agent run returns UUID string."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        run_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (run_id,)

        prompt_id = str(uuid.uuid4())
        llm_model = "gemini-3.1-flash-lite"

        result = create_agent_run(prompt_id, llm_model)

        assert isinstance(result, str)
        assert uuid.UUID(result) == run_id
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        print(args)
        assert "INSERT INTO agent_runs" in args[0]
        assert prompt_id in args[1]
        assert llm_model in args[1]
        assert "RUNNING" in args[0]

# ========== complete_agent_run Tests ==========

class TestCompleteAgentRun:
    """Tests for agent run completion."""

    @patch('database.get_connection')
    def test_complete_agent_run_updates_status(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify agent run status is updated correctly."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        run_id = str(uuid.uuid4())
        status = "SUCCESS"
        notes = "All good"

        complete_agent_run(run_id, status, notes)

        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        assert "UPDATE agent_runs" in args[0]
        assert args[1][0] == status
        assert args[1][1] == notes
        assert args[1][2] == run_id

    @patch('database.get_connection')
    def test_complete_agent_run_handles_none_notes(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify agent run completion works with None notes."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        run_id = str(uuid.uuid4())
        status = "FAILED"

        complete_agent_run(run_id, status, None)

        args = mock_cursor.execute.call_args[0]
        assert args[1][1] is None

# ========== store_prediction Tests ==========

class TestStorePrediction:
    """Tests for prediction storage with JSONB fields."""

    @patch('database.get_connection')
    def test_store_prediction_returns_uuid(self, mock_get_conn, mock_conn, mock_cursor, sample_prediction):
        """Verify prediction storage returns UUID string."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (prediction_id,)

        run_id = str(uuid.uuid4())

        result = store_prediction(run_id, sample_prediction, date(2026, 7, 15))

        assert isinstance(result, str)
        assert uuid.UUID(result) == prediction_id

        args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO predictions" in args[0]
        params = args[1]
        assert params[0] == run_id
        assert params[2] == sample_prediction.bullish_probability
        assert params[3] == sample_prediction.bearish_probability
        assert params[4] == sample_prediction.confidence
        assert params[5] == sample_prediction.reasoning

    @patch('database.get_connection')
    def test_store_prediction_jsonb_fields_as_list(self, mock_get_conn, mock_conn, mock_cursor, sample_prediction):
        """Verify JSONB fields are passed as Json-wrapped lists."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (prediction_id,)

        run_id = str(uuid.uuid4())
        store_prediction(run_id, sample_prediction, date(2026, 7, 15))

        args = mock_cursor.execute.call_args[0]
        params = args[1]
        assert isinstance(params[6], psycopg2.extras.Json)
        assert params[6].adapted == sample_prediction.major_drivers
        assert isinstance(params[7], psycopg2.extras.Json)
        assert params[7].adapted == sample_prediction.invalidation
        assert isinstance(params[8], psycopg2.extras.Json)
        assert params[8].adapted == sample_prediction.ignored_articles

    @patch('database.get_connection')
    def test_store_prediciton_empty_jsonb_fields(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify empty lists are handled correctly in JSONB fields."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (prediction_id,)

        prediction = DailyPrediction(
            id=uuid.uuid4(),
            horizon="DAY",
            prediction_for=datetime(2026, 7, 15, 9, 30),
            bullish_probability=0.6,
            bearish_probability=0.4,
            confidence=0.7,
            reasoning="Test",
            major_drivers=[],
            invalidation=[],
            ignored_articles=[],
        )
        run_id = str(uuid.uuid4())
        store_prediction(run_id, prediction, date(2026, 7, 15))

        args = mock_cursor.execute.call_args[0]
        params = args[1]
        assert isinstance(params[6], psycopg2.extras.Json)
        assert params[6].adapted == []
        assert isinstance(params[7], psycopg2.extras.Json)
        assert params[7].adapted == []
        assert isinstance(params[8], psycopg2.extras.Json)
        assert params[8].adapted == []

# ========== link_prediction_evidence Tests ==========

class TestLinkPredictionEvidence:
    """Tests for evidence linking with execute_values."""

    @patch('database.get_connection')
    @patch('database.execute_values')
    def test_empty_articles_no_execute_values(self, mock_execute_values, mock_get_conn, mock_conn, mock_cursor):
        """Verify no SQL execution when articles list is empty."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        link_prediction_evidence(str(uuid.uuid4()), [])
        mock_execute_values.assert_not_called()
        mock_cursor.assert_not_called()

    @patch('database.get_connection')
    @patch('database.execute_values')
    def test_link_articles_calls_execute_values(self, mock_execute_values, mock_get_conn, mock_conn, mock_cursor, sample_news_article):
        """Verify execute_values called with correct tuples."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        article1 = sample_news_article
        article2 = NewsArticle(
            id=uuid.uuid4(),
            source="test",
            external_id="2",
            title="Test 2",
            url="http://test2",
            published_at=datetime.now(),
            hash="hash2",
        )

        prediction_id = uuid.uuid4()

        link_prediction_evidence(str(prediction_id), [article1, article2])

        mock_execute_values.assert_called_once()
        call_args = mock_execute_values.call_args
        cursor = call_args[0][0]
        query = call_args[0][1]
        data = call_args[0][2]
        print(data)

        assert "INSERT INTO evidence" in query
        assert "ON CONFLICT (prediction_id, article_id) DO NOTHING" in query
        assert len(data) == 2
        assert data[0] == (str(prediction_id), article1.id, 1.0)
        assert data[1] == (str(prediction_id), article2.id, 1.0)

    @patch('database.get_connection')
    @patch('database.execute_values')
    def test_single_article_linking(self, mock_execute_values, mock_get_conn, mock_conn, mock_cursor, sample_news_article):
        """Verify single article is linked correctly."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()

        link_prediction_evidence(str(prediction_id), [sample_news_article])

        call_args = mock_execute_values.call_args
        data = call_args[0][2]
        assert len(data) == 1
        assert data[0][0] == str(prediction_id)
        assert data[0][1] == sample_news_article.id
        assert data[0][2] == 1.0

# ========== get_predictions_pending_evaluation Tests ==========

class TestGetPredictionsPendingEvaluation:
    """Tests for pending prediction retrieval with JSONB deserialization."""

    @patch('database.get_connection')
    def test_returns_daily_prediction_objects(self, mock_get_conn, mock_conn, mock_dictcursor):
        """Verify database rows are converted to DailyPrediction objects."""
        mock_conn.cursor.return_value = mock_dictcursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_dictcursor.__enter__.return_value = mock_dictcursor
        mock_dictcursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()
        pred_date = date(2026, 7, 15)

        mock_dictcursor.fetchall.return_value = [
            {
                "id": prediction_id,
                "horizon": "DAY",
                "prediction_for": pred_date,
                "bullish_probability": 0.7,
                "bearish_probability": 0.3,
                "confidence": 0.8,
                "reasoning": "Test reasoning",
                "major_drivers": ["Fed pause", "AI capex"],
                "invalidation": ["Hot CPI", "Yield spike"],
                "ignored_articles": ["hash_1", "hash_2"],
            }
        ]

        predictions = get_predictions_pending_evaluation()

        assert len(predictions) == 1
        prediction = predictions[0]
        assert isinstance(prediction, DailyPrediction)
        assert prediction.id == prediction_id
        assert prediction.horizon == "DAY"
        assert prediction.bullish_probability == 0.7
        assert prediction.bearish_probability == 0.3
        assert prediction.confidence == 0.8
        assert prediction.reasoning == "Test reasoning"
        assert prediction.major_drivers == ["Fed pause", "AI capex"]
        assert prediction.invalidation == ["Hot CPI", "Yield spike"]
        assert prediction.ignored_articles == ["hash_1", "hash_2"]

    @patch('database.get_connection')
    def test_null_jsonb_fields_become_empty_lists(self, mock_get_conn, mock_conn, mock_dictcursor):
        """Verify None JSONB fields are converted to empty lists."""
        mock_conn.cursor.return_value = mock_dictcursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_dictcursor.__enter__.return_value = mock_dictcursor
        mock_dictcursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()
        pred_date = date(2026, 7, 15)

        mock_dictcursor.fetchall.return_value = [
            {
                "id": prediction_id,
                "horizon": "DAY",
                "prediction_for": pred_date,
                "bullish_probability": 0.5,
                "bearish_probability": 0.5,
                "confidence": 0.6,
                "reasoning": "Mixed signals",
                "major_drivers": None,
                "invalidation": None,
                "ignored_articles": None,
            }
        ]

        predictions = get_predictions_pending_evaluation()

        assert len(predictions) == 1
        prediction = predictions[0]
        assert prediction.major_drivers == []
        assert prediction.invalidation == []
        assert prediction.ignored_articles == []

    @patch('database.get_connection')
    def test_uuid_preservation_in_query_results(self, mock_get_conn, mock_conn, mock_dictcursor):
        """Verify UUID fields are correctly preserved from query results."""
        mock_conn.cursor.return_value = mock_dictcursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_dictcursor.__enter__.return_value = mock_dictcursor
        mock_dictcursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = uuid.uuid4()
        pred_date = date(2026, 7, 15)

        mock_dictcursor.fetchall.return_value = [
            {
                "id": prediction_id,
                "horizon": "DAY",
                "prediction_for": pred_date,
                "bullish_probability": 0.6,
                "bearish_probability": 0.4,
                "confidence": 0.7,
                "reasoning": "Test",
                "major_drivers": [],
                "invalidation": [],
                "ignored_articles": [],
            }
        ]

        predictions = get_predictions_pending_evaluation()

        assert len(predictions) == 1
        assert predictions[0].id == prediction_id
        assert isinstance(predictions[0].id, uuid.UUID)

    @patch('database.get_connection')
    def test_empty_result_returns_empty_list(self, mock_get_conn, mock_conn, mock_dictcursor):
        """Verify empty query result returns empty list."""
        mock_conn.cursor.return_value = mock_dictcursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_dictcursor.__enter__.return_value = mock_dictcursor
        mock_dictcursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        mock_dictcursor.fetchall.return_value = []

        predictions = get_predictions_pending_evaluation()

        assert predictions == []
        assert isinstance(predictions, list)

    @patch('database.get_connection')
    def test_multiple_predictions_ordered_by_date(self, mock_get_conn, mock_conn, mock_dictcursor):
        """Verify multiple predictions are ordered by prediction_for ascending."""
        mock_conn.cursor.return_value = mock_dictcursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_dictcursor.__enter__.return_value = mock_dictcursor
        mock_dictcursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        pred1_id = uuid.uuid4()
        pred2_id = uuid.uuid4()

        predictions = get_predictions_pending_evaluation()

        query = mock_dictcursor.execute.call_args[0][0]
        assert "ORDER BY p.prediction_for ASC" in query

# ========== store_evaluation Tests ==========

class TestStoreEvaluation:
    """Tests for evaluation storage."""

    @patch('database.get_connection')
    def test_store_evaluation_returns_evaluation_with_id(self, mock_get_conn, mock_conn, mock_cursor, sample_evaluation):
        """Verify evaluation is stored and ID is returned."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        eval_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (eval_id,)

        result = store_evaluation(sample_evaluation)

        assert isinstance(result, Evaluation)
        assert result.id == eval_id
        assert result.prediction_id == sample_evaluation.prediction_id
        assert result.predicted_direction == sample_evaluation.predicted_direction
        assert result.observed_direction == sample_evaluation.observed_direction
        assert result.prediction_score == sample_evaluation.prediction_score

        args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO evaluations" in args[0]
        params = args[1]
        assert params[0] == sample_evaluation.prediction_id
        assert params[1] == sample_evaluation.evaluated_at
        assert params[2] == sample_evaluation.observed_direction
        assert params[3] == sample_evaluation.return_points
        assert params[4] == sample_evaluation.predicted_direction
        assert params[5] == sample_evaluation.prediction_score
        assert params[6] == sample_evaluation.notes

    @patch('database.get_connection')
    def test_store_evaluation_preserves_uuid_fields(self, mock_get_conn, mock_conn, mock_cursor, sample_evaluation):
        """Verify UUID fields are preserved in evaluation storage."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        eval_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (eval_id,)

        result = store_evaluation(sample_evaluation)

        assert isinstance(result.prediction_id, uuid.UUID)
        assert result.prediction_id == sample_evaluation.prediction_id
        assert isinstance(result.id, uuid.UUID)
        assert result.id == eval_id

# ========== store_market_data Tests ==========

class TestStoreMarketData:
    """Tests for market data storage with upsert behavior."""

    @patch('database.get_connection')
    def test_upsert_sql_contains_conflict_clause(self, mock_get_conn, mock_conn, mock_cursor, sample_market_data):
        """Verify SQL contains ON CONFLICT and DO UPDATE SET."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        store_market_data(sample_market_data)

        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        query = args[0]
        assert "ON CONFLICT (trading_day)" in query
        assert "DO UPDATE SET" in query
        assert "open = EXCLUDED.open" in query
        assert "high = EXCLUDED.high" in query
        assert "low = EXCLUDED.low" in query
        assert "close = EXCLUDED.close" in query
        assert "volume = EXCLUDED.volume" in query

    @patch('database.get_connection')
    def test_duplicate_insert_updates_values(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify duplicate trading_day updates OHLCV values."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        trading_day = datetime(2026, 7, 15, 9, 30)

        market_data1 = MarketData(
            trading_day=trading_day,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000000,
        )

        market_data2 = MarketData(
            trading_day=trading_day,
            open=102.0,
            high=103.0,
            low=101.0,
            close=102.5,
            volume=1500000,
        )

        store_market_data(market_data1)
        store_market_data(market_data2)

        assert mock_cursor.execute.call_count == 2

        second_call_args = mock_cursor.execute.call_args_list[1][0]
        params = second_call_args[1]
        assert params[0] == trading_day
        assert params[1] == 102.0
        assert params[2] == 103.0
        assert params[3] == 101.0
        assert params[4] == 102.5
        assert params[5] == 1500000

    @patch('database.get_connection')
    def test_returns_market_data_object(self, mock_get_conn, mock_conn, mock_cursor, sample_market_data):
        """Verify function returns the input MarketData object."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        result = store_market_data(sample_market_data)

        assert result == sample_market_data
        assert isinstance(result, MarketData)

    @patch('database.get_connection')
    def test_no_exception_on_duplicate(self, mock_get_conn, mock_conn, mock_cursor, sample_market_data):
        """Verify duplicate trading_day does not raise exception."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        store_market_data(sample_market_data)
        store_market_data(sample_market_data)

        assert mock_cursor.execute.call_count == 2

    @patch('database.get_connection')
    def test_trading_day_unchanged_in_upsert(self, mock_get_conn, mock_conn, mock_cursor):
        """Verify trading_day is note modified during upsert."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        trading_day = datetime(2026, 7, 15, 9, 30)

        market_data1 = MarketData(
            trading_day=trading_day,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000000,
        )

        market_data2 = MarketData(
            trading_day=trading_day,
            open=102.0,
            high=103.0,
            low=101.0,
            close=102.5,
            volume=1500000,
        )

        store_market_data(market_data1)
        store_market_data(market_data2)

        second_call_args = mock_cursor.execute.call_args_list[1][0]
        params = second_call_args[1]
        assert params[0] == trading_day

# ========== UUID-Specific Tests ==========

class TestUUIDHandling:
    """Tests for UUID preservation across database operations."""

    @patch('database.get_connection')
    def test_store_prediction_preserves_run_id_uuid(self, mock_get_conn, mock_conn, mock_cursor, sample_prediction):
        """Verify run_id UUID is passed as string correctly."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        run_id = uuid.uuid4()
        prediction_id = uuid.uuid4()
        mock_cursor.fetchone.return_value = (prediction_id,)

        result = store_prediction(str(run_id), sample_prediction, date(2026, 7, 15))

        args = mock_cursor.execute.call_args[0]
        params = args[1]
        assert params[0] == str(run_id)
        assert uuid.UUID(params[0]) == run_id

    @patch('database.get_connection')
    def test_store_evaluation_preserves_prediction_id_uuid(self, mock_get_conn, mock_conn, mock_cursor, sample_evaluation):
        """Verify prediction_id UUID is preserved in evaluation storage."""
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        eval_id = uuid.uuid4()
        prediction_id = sample_evaluation.prediction_id
        mock_cursor.fetchone.return_value = (eval_id,)

        result = store_evaluation(sample_evaluation)

        args = mock_cursor.execute.call_args[0]
        params = args[1]
        assert params[0] == prediction_id
        assert isinstance(params[0], uuid.UUID)

    @patch('database.execute_values')
    def test_link_prediction_evidence_preserves_uuid_tuples(self, mock_execute_values, sample_news_article):
        """Verify UUIDs are preserved in evidence linking tuples."""

        prediction_id = uuid.uuid4()

        link_prediction_evidence(str(prediction_id), [sample_news_article])

        call_args = mock_execute_values.call_args
        data = call_args[0][2]
        assert len(data) == 1
        assert data[0][0] == str(prediction_id)
        assert data[0][1] == sample_news_article.id
        assert isinstance(data[0][0], str)
        assert isinstance(data[0][1], uuid.UUID)

    @patch('database.get_connection')
    def test_get_predictions_pending_evaluation_preserves_uuid(self, mock_get_conn, mock_conn, mock_dictcursor, sample_prediction):
        """Verify UUIDs are preserved when fetching predictions."""
        mock_conn.cursor.return_value = mock_dictcursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = False
        mock_dictcursor.__enter__.return_value = mock_dictcursor
        mock_dictcursor.__exit__.return_value = False
        mock_get_conn.return_value = mock_conn

        prediction_id = sample_prediction.id

        mock_dictcursor.fetchall.return_value = [sample_prediction.model_dump()]

        predictions = get_predictions_pending_evaluation()

        assert len(predictions) == 1
        assert predictions[0].id == prediction_id
        assert isinstance(predictions[0].id, uuid.UUID)
