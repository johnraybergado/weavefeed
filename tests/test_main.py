"""
Unit tests for the prediction workflow entrypoint (main.main).

Collector, database and LLM are mocked; no network or DB access.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed"))
)

import main as workflow


@patch("main.persist_analysis_run")
@patch("main.analyze_news", return_value=None)
@patch("main.get_latest_articles", return_value=["article"])
@patch("main.collect_news", return_value=(0, 0, 0))
def test_main_does_not_persist_when_llm_returns_no_prediction(
    _collect, _latest, _analyze, persist
):
    workflow.main()
    persist.assert_not_called()


@patch("main.persist_analysis_run")
@patch("main.analyze_news")
@patch("main.get_latest_articles", return_value=["article"])
@patch("main.collect_news", return_value=(0, 0, 0))
def test_main_persists_prediction(_collect, _latest, analyze, persist):
    workflow.main()
    persist.assert_called_once_with(
        prediction=analyze.return_value, articles=["article"]
    )
