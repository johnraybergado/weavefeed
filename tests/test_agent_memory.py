"""
Integration test for agent memory and persistence layer.
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed")))

from database import get_latest_articles, persist_analysis_run, get_connection
from llm import analyze_news
from prompts import PROMPT_VERSION


def test_agent_memory():
   print("=" * 50)
   print("Starting Agent Memory End-to-End Test")
   print("=" * 50)

   # 1. Load latest 5 articles from PostgreSQL
   print("\n[1/5] Loading latest 5 articles from database...")
   articles = get_latest_articles(limit=5)
   if not articles:
      print("FAIL: No articles found in database. Run test_collect_news.py first.")
      return

   print(f"Successfully loaded {len(articles)} articles.")

   # 2. Run analyze_news()
   print("\n[2/5] Running LLM macroeconomic analysis...")
   prediction = analyze_news(articles)
   print("Analysis complete. Structured prediction generated.")

   # 3. Persist results using persist_analysis_run()
   print("\n[3/5] Persisting results to database...")
   persist_analysis_run(prediction, articles)
   print("Persistence workflow complete.")

   # Query database afterward and verify
   print("\n[4/5] Querying database to verify state...")
   with get_connection() as conn:
      with conn.cursor() as cur:
         # Check prompt_templates
         cur.execute("SELECT id FROM prompt_templates WHERE version = %s;", (PROMPT_VERSION,))
         prompt_rows = cur.fetchall()
         prompt_id = prompt_rows[0][0] if prompt_rows else None

         # Check agent_runs
         cur.execute("SELECT id, status FROM agent_runs WHERE prompt_id = %s;", (prompt_id,))
         run_rows = cur.fetchall()
         run_id = run_rows[0][0] if run_rows else None
         run_status = run_rows[0][1] if run_rows else None

         # Check predictions
         cur.execute("SELECT id FROM predictions WHERE run_id = %s;", (run_id,))
         pred_rows = cur.fetchall()
         prediction_id = pred_rows[0][0] if pred_rows else None

         # Check evidence
         cur.execute("SELECT COUNT(*) FROM evidence WHERE prediction_id = %s;", (prediction_id,))
         evidence_count = cur.fetchone()[0]

   # 5. Print results and verify
   print("\n[5/5] Generating Report...")
   print("-" * 30)
   print(f"Prompt ID:      {prompt_id}")
   print(f"Run ID:         {run_id}")
   print(f"Prediction ID:  {prediction_id}")
   print(f"Evidence count: {evidence_count}")
   print("-" * 30)

   # Assertions
   success = True

   if len(prompt_rows) != 1:
      print(f"FAIL: Expected 1 prompt template, found {len(prompt_rows)}")
      success = False

   if run_status != "SUCCESS":
      print(f"FAIL: Expected run status 'SUCCESS', found '{run_status}'")
      success = False

   if len(pred_rows) != 1:
      print(f"FAIL: Expected 1 prediction, found {len(pred_rows)}")
      success = False

   if evidence_count != (len(articles) - len(prediction.ignored_articles)):
      print(f"FAIL: Expected {len(articles) - len(prediction.ignored_articles)} evidence count, found {evidence_count}")
      success = False

   print("\n" + "=" * 50)
   if success:
      print("RESULT: PASS - All assertions passed successfully.")
   else:
      print("RESULT: FAIL - One or more assertions failed.")
   print("=" * 50)


if __name__ == "__main__":
   test_agent_memory()
