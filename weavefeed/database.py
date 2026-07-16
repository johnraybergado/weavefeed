"""PostgreSQL persistence layer"""
import logging
from typing import List
import psycopg2
from psycopg2.extras import (
    execute_values,
    register_uuid,
    DictCursor,
    Json
)
register_uuid()
from datetime import date
from models import DailyPrediction, NewsArticle, Evaluation, MarketData
from config import settings

logger = logging.getLogger(__name__)


def get_connection():
    """Establishes and returns a database connection."""
    return psycopg2.connect(dbname=settings.postgres_db,
                            user=settings.postgres_user,
                            password=settings.postgres_password,
                            host=settings.postgres_host,
                            port=settings.postgres_port)

# ---------------------------------------------------------
# News Storage and Retrieval Helpers
# ---------------------------------------------------------

def store_articles(articles: list[NewsArticle]) -> int:
    """
    Inserts a list of NewsArticle objects into the database in batches.
    Ignores articles with hashes that already exist in the database.

    Returns number of stored articles.
    """
    if not articles:
        return

    query = """
        INSERT INTO news_articles (
            id, source, external_id, title, summary, content,
            url, published_at, collected_at, hash
        ) VALUES %s ON CONFLICT (hash) DO NOTHING
        RETURNING id;
    """

    data = [
        (
            str(article.id), article.source, article.external_id,
            article.title, article.summary, article.content,
            article.url, article.published_at, article.collected_at,
            article.hash
        )
        for article in articles
    ]

    # Context managers automatically handle closing connections/cursors
    # and committing the transaction.
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                execute_values(cursor, query, data)
                # fetchall() will return only the IDs of rows actually inserted
                inserted_rows = cursor.fetchall()
                return len(inserted_rows)
    except Exception as e:
        logger.error(f"store_articles failed: {e}")
        return 0
    finally:
        if conn is not None:
            conn.close()


def get_latest_articles(limit: int = 5) -> List[NewsArticle]:
    """
    Retrieve the most recently published news articles from PostgreSQL.
    Articles are ordered by `published_at` descending, so the first
    element of the returned list is the most recent article.
    Args:
        limit: Maximum number of articles to return.
    Returns:
        A list of NewsArticle objects, ordered newest-first. Returns
        an empty list if no rows are found or if teh query fails
        (the failure is logged rather than raised, so callers can
        decide how to handle an empty result set).
    """
    query = """
        SELECT id, source, external_id, title, summary, content, url,
            published_at, collected_at, hash
        FROM news_articles
        ORDER BY published_at DESC
        LIMIT %s;
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
        articles: List[NewsArticle] = [
            NewsArticle(
                id=row[0],
                source=row[1],
                external_id=row[2],
                title=row[3],
                summary=row[4],
                content=row[5],
                url=row[6],
                published_at=row[7],
                collected_at=row[8],
                hash=row[9],
            )
            for row in rows
        ]
        return articles
    except Exception as e:
        logger.error(f"get_latest_articles failed: {e}")
        return []
    finally:
        if conn is not None:
            conn.close()

# ---------------------------------------------------------
# Agent Memory & Persistence Helpers
# ---------------------------------------------------------

def store_prompt_template(version: str, system_prompt: str, user_prompt: str) -> str:
    """
    Inserts a prompt template if it doesn't exist.
    Returns the prompt_templates.id.
    """
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO prompt_templates (version, system_prompt, user_prompt)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (version) DO NOTHING
                    RETURNING id;
                    """,
                    (version, system_prompt, user_prompt)
                )
                row = cur.fetchone()
                if row:
                    return str(row[0])

                # if it already existed, fetch the existing ID
                cur.execute("SELECT id FROM prompt_templates WHERE version = %s;", (version,))
                return str(cur.fetchone()[0])
    except Exception as e:
        logger.error(f"store_prompt_template failed: {e}")
        return ""
    finally:
        if conn is not None:
            conn.close()


def create_agent_run(prompt_id: str, llm_model: str) -> str:
    """
    Creates a new agent run record with status 'RUNNING'.
    Returns the run_id.
    """
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_runs (prompt_id, llm_model, status, started_at)
                    VALUES (%s, %s, 'RUNNING', NOW())
                    RETURNING id;
                    """,
                    (prompt_id, llm_model)
                )
                return str(cur.fetchone()[0])
    except Exception as e:
        logger.error(f"create_agent_run failed: {e}")
        return ""
    finally:
        if conn is not None:
            conn.close()


def complete_agent_run(run_id: str, status: str, notes: str | None = None):
    """
    Updates an agent run with its final status, finish time, and optional notes.
    """
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_runs
                    SET finished_at = NOW(), status = %s, notes = %s
                    WHERE id = %s;
                    """,
                    (status, notes, run_id)
                )
    except Exception as e:
        logger.error(f"complete_agent_run failed: {e}")
    finally:
        if conn is not None:
            conn.close()


def store_prediction(run_id: str, prediction: DailyPrediction, prediction_for: date) -> str:
    """
    Stores the structured prediction output.
    Returns the prediction_id.
    """

    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO predictions (
                        run_id, horizon, prediction_for,
                        bullish_probability, bearish_probability, confidence,
                        reasoning, major_drivers, invalidation, ignored_articles
                    )
                    VALUES (%s, 'DAY', %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        run_id,
                        prediction.prediction_for,
                        prediction.bullish_probability,
                        prediction.bearish_probability,
                        prediction.confidence,
                        prediction.reasoning,
                        Json(prediction.major_drivers),
                        Json(prediction.invalidation),
                        Json(prediction.ignored_articles)
                    )
                )
                return str(cur.fetchone()[0])
    except Exception as e:
        logger.error(f"store_prediction failed: {e}")
        return ""
    finally:
        if conn is not None:
            conn.close()


def link_prediction_evidence(prediction_id: str, articles: list[NewsArticle]):
    """
    Links a prediction to the articles used as evidence.
    MVP implementation sets relevance to 1.0 for all supplied articles.
    """
    if not articles:
        return
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                data = [(prediction_id, article.id, 1.0) for article in articles]
                execute_values(
                    cur,
                    """
                    INSERT INTO evidence (prediction_id, article_id, relevance)
                    VALUES %s
                    ON CONFLICT (prediction_id, article_id) DO NOTHING;
                    """,
                    data
                )
    except Exception as e:
        logger.error(f"link_prediction_evidence failed: {e}")
    finally:
        if conn is not None:
            conn.close()



def persist_analysis_run(prediction: DailyPrediction, articles: list[NewsArticle]):
    """
    End-to-end persistence helper.
    Orchestrates prompt storage, run tracking, prediction storage, and evidence linking.
    """
    from prompts import SYSTEM_PROMPT, generate_analysis_prompt, PROMPT_VERSION

    run_id = None
    try:
        # 1. Store current prompts
        user_prompt_template = generate_analysis_prompt([])
        prompt_id = store_prompt_template(PROMPT_VERSION, SYSTEM_PROMPT, user_prompt_template)

        # 2. Create agent run
        # Fallback to standard model name if config varies
        llm_model = "gemini-3.5-flash"
        try:
            llm_model = getattr(settings, "llm_model", "gemini-3.5-flash")
        except Exception:
            print("llm_model exception")
            pass

        run_id = create_agent_run(prompt_id, llm_model)

        # 3. Store prediction
        prediction_id = store_prediction(run_id, prediction, date.today())

        # 4. Link evidence
        available_articles = {a.hash for a in articles}
        ignored_articles = {
            a for a in prediction.ignored_articles
            if a in available_articles
        }
        supporting_articles = [
            article
            for article in articles
            if article.hash not in ignored_articles
        ]
        link_prediction_evidence(prediction_id, supporting_articles)

        # 5. Mark run SUCCESS
        complete_agent_run(run_id, "SUCCESS")

    except Exception as e:
        if run_id:
            complete_agent_run(run_id, "FAILED", notes=str(e))
        raise

# ---------------------------------------------------------
# Prediction Retrieval & Evaluation Persistence Helpers
# ---------------------------------------------------------

def get_predictions_pending_evaluation() -> List[DailyPrediction]:
    """
    Retrieve all DAY-horizon predictions for past dates without evaluations.

    Returns:
        List[DailyPrediction]: Predictions awaiting evaluation.
    """
    # SELECT p.id, p.run_id, p.horizon, p.prediction_for,
    query = """
        SELECT p.id, p.horizon, p.prediction_for,
               p.bullish_probability, p.bearish_probability,
               p.confidence, p.reasoning, p.major_drivers,
               p.invalidation, p.ignored_articles
        FROM predictions p
        LEFT JOIN evaluations e ON p.id = e.prediction_id
        WHERE e.id IS NULL
        AND p.prediction_for <= CURRENT_DATE
        AND p.horizon = 'DAY'
        ORDER BY p.prediction_for ASC
    """
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query)

                predictions = []

                for row in cursor.fetchall():
                    predictions.append(
                        DailyPrediction(
                            id=row["id"],
                            horizon=row["horizon"],
                            prediction_for=row["prediction_for"],
                            bullish_probability=row["bullish_probability"],
                            bearish_probability=row["bearish_probability"],
                            confidence=row["confidence"],
                            reasoning=row["reasoning"],
                            major_drivers=row["major_drivers"] or [],
                            invalidation=row["invalidation"] or [],
                            ignored_articles=row["ignored_articles"] or []
                        )
                    )
                return predictions
    except Exception as e:
        logger.error(f"get_predictions_pending_evaluation failed: {e}")
        return []
    finally:
        if conn is not None:
            conn.close()


def store_evaluation(evaluation: Evaluation) -> Evaluation:
    """
    Persist an evaluation result to the database.

    Args:
        evaluation: Evaluation object to store.

    Returns:
        Evaluation: Stored evaluation with updated ID.

    Raises:
        psycopg2.Error: On database errors.
    """
    query = """
        INSERT INTO evaluations
        (prediction_id, evaluated_at, observed_direction, return_points,
         predicted_direction, prediction_score, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (
                    evaluation.prediction_id, 
                    evaluation.evaluated_at,
                    evaluation.observed_direction,
                    evaluation.return_points,
                    evaluation.predicted_direction,
                    evaluation.prediction_score,
                    evaluation.notes
                ))
                evaluation.id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"Stored evaluation {evaluation.id} for prediction {evaluation.prediction_id}")
                return evaluation
    except Exception as e:
        logger.error(f"store_evaluation failed: {e}")
        return []
    finally:
        if conn is not None:
            conn.close()


def store_market_data(market_data: MarketData) -> MarketData:
    """
    Persist market data with upsert semantics.

    On conflict (same trading_day), updates all OHLCV fields to the new values.
    Safe to call repeatedly - ensures the latest data is stored.

    Args:
        market_data: MarketData object to store/upsert.

    Returns:
        The input MarketData object (unchanged).
    """
    query = """
        INSERT INTO market_data
        (trading_day, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (trading_day)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    conn = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (
                    market_data.trading_day,
                    market_data.open,
                    market_data.high,
                    market_data.low,
                    market_data.close,
                    market_data.volume
                ))
                conn.commit()
                return market_data
    except Exception as e:
        logger.error(f"store_market_data failed: {e}")
        return None
    finally:
        if conn is not None:
            conn.close()
