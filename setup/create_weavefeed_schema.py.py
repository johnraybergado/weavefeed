#!/usr/bin/env python3
"""
Create the WeaveFeed database schema in PostgreSQL.
Requires the pgvector extension to be available.
"""

import os
import psycopg2
from psycopg2 import sql

# Connection parameters – override with environment variables or edit directly
DB_CONFIG = {
    "dbname": "weavefeed",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432",
}

# SQL statements to create tables (order respects foreign key dependencies)
CREATE_TABLE_STATEMENTS = [
    # 1. prompt_templates
    """
    CREATE TABLE IF NOT EXISTS prompt_templates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        version VARCHAR(32) UNIQUE NOT NULL,
        system_prompt TEXT NOT NULL,
        user_prompt TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,

    # 2. agent_runs
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        prompt_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
        llm_model VARCHAR(64) NOT NULL,
        started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at TIMESTAMPTZ,
        status VARCHAR(20) NOT NULL,
        notes TEXT,
        -- optional index for performance
        CONSTRAINT fk_agent_runs_prompt FOREIGN KEY (prompt_id) REFERENCES prompt_templates(id)
    );
    """,

    # 3. news_articles
    """
    CREATE TABLE IF NOT EXISTS news_articles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source VARCHAR(50) NOT NULL,
        external_id VARCHAR(500) NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        content TEXT,
        url TEXT NOT NULL,
        published_at TIMESTAMPTZ NOT NULL,
        collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        sentiment REAL,
        embedding VECTOR,  -- requires pgvector extension
        hash VARCHAR(64) UNIQUE NOT NULL
    );
    """,

    # 4. predictions
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
        horizon VARCHAR(10) NOT NULL CHECK (horizon IN ('DAY', 'WEEK', 'MONTH')),
        prediction_for DATE NOT NULL,
        bullish_probability REAL NOT NULL CHECK (bullish_probability >= 0 AND bullish_probability <= 1),
        bearish_probability REAL NOT NULL CHECK (bearish_probability >= 0 AND bearish_probability <= 1),
        confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
        reasoning TEXT NOT NULL,
        major_drivers JSONB,
        invalidation JSONB,
        ignored_articles JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,

    # 5. evidence (many-to-many between predictions and news_articles)
    """
    CREATE TABLE IF NOT EXISTS evidence (
        prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
        article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
        relevance REAL NOT NULL CHECK (relevance >= 0 AND relevance <= 1),
        PRIMARY KEY (prediction_id, article_id)
    );
    """,

    # 6. market_data
    """
    CREATE TABLE IF NOT EXISTS market_data (
        trading_day DATE PRIMARY KEY,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume BIGINT NOT NULL
    );
    """,

    # 7. evaluations
    """
    CREATE TABLE IF NOT EXISTS evaluations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
        evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        observed_direction SMALLINT NOT NULL CHECK (observed_direction IN (-1, 1)),
        return_points REAL NOT NULL,
        predicted_direction SMALLINT NOT NULL CHECK (predicted_direction IN (-1, 1)),
        prediction_score REAL NOT NULL,
        notes TEXT
    );
    """,
]

# Additional indexes (optional but recommended)
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_prompt_id ON agent_runs(prompt_id);",
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);",
    "CREATE INDEX IF NOT EXISTS idx_predictions_run_id ON predictions(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_predictions_prediction_for ON predictions(prediction_for);",
    "CREATE INDEX IF NOT EXISTS idx_news_articles_source ON news_articles(source);",
    "CREATE INDEX IF NOT EXISTS idx_news_articles_published_at ON news_articles(published_at);",
    "CREATE INDEX IF NOT EXISTS idx_news_articles_hash ON news_articles(hash);",
    "CREATE INDEX IF NOT EXISTS idx_evidence_article_id ON evidence(article_id);",
    "CREATE INDEX IF NOT EXISTS idx_evaluations_prediction_id ON evaluations(prediction_id);",
]


def create_database_schema():
    """Connect to PostgreSQL and create the schema."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False  # use explicit transaction
        cur = conn.cursor()

        # Enable required extensions
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Create tables
        for stmt in CREATE_TABLE_STATEMENTS:
            cur.execute(stmt)

        # Create indexes
        for stmt in INDEX_STATEMENTS:
            cur.execute(stmt)

        conn.commit()
        print("Database schema created successfully.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    create_database_schema()