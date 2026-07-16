"""
Prediction workflow entrypoint.

Workflow:
1. Collect latest macroeconomic news.
2. Store news articles.
3. Retrieve recent articles.
4. Generate directional hypothesis.
5. Persist prediction and evidence.

Does NOT perform evaluation.
"""

import logging

from collector import collect_news
from database import (
    store_articles,
    get_latest_articles,
    persist_analysis_run
)
from llm import analyze_news

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting prediction workflow")

    # --------------------------------------------------
    # News Collection
    # --------------------------------------------------

    articles, inserted, removed = collect_news()

    logger.info(f"Collected{len(articles)} articles")

    inserted = store_articles(articles)

    logger.info(f"Inserted {inserted} new articles")

    # --------------------------------------------------
    # Analysis
    # --------------------------------------------------

    recent_articles = get_latest_articles(limit=20)

    if not recent_articles:
        logger.warning("No articles available for analysis")
        return

    prediction = analyze_news(recent_articles)

    persist_analysis_run(
        prediction=prediction,
        articles=recent_articles
    )

    logger.info(f"Stored prediction for {prediction.prediction_for}")
    logger.info("Prediction workflow complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    main()
