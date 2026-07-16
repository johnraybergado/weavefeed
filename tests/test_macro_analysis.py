"""
Integration test for the macro analysis pipeline.
Workflow mirrors production usage:
	1. Load the most recent articles from PostgreSQL via
	   weavefeed.database.get_latest_articles().
	2. Pass those articles into weavefeed.llm.analyze_news().
	3. Print a structured report of the resulting DailyPrediction.
	4. Validate the prediction's numeric fields.
	5. Report timing for each stage.
No SQL is written in this file — all data access goes through
get_latest_articles() so persistence logic stays inside database.py.
"""
import os
import sys
import time
# Ensure parent directory is in the path to import weavefeed modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed")))
from database import get_latest_articles
from llm import analyze_news


ARTICLE_LIMIT = 10
def print_header(title: str) -> None:
	print("\n" + "=" * 50)
	print(title)
	print("\n" + "=" * 50)


def print_list(label: str, items) -> None:
	print(f"{label}:")
	if not items:
		print(" (none)")
		return
	for item in items:
		print(f"- {item}")


def validate_prediction(prediction) -> bool:
	"""Run sanity checks against a DailyPrediction, printing PASS/FAIL for each."""
	print_header("VALIDATION")
	all_passed = True
	prob_sum_threshold = 0.01

	def check(label: str, condition: bool) -> None:
		nonlocal all_passed
		status = "PASS" if condition else "FAIL"
		if not condition:
			all_passed = False
		print(f"[{status}] {label}")
	check("confidence between 0 and 1", 0.0 <= prediction.confidence <= 1.0)
	check("bullish_probability between 0 and 1", 0.0 <= prediction.bullish_probability <= 1.0)
	check("bearish_probability between 0 and 1", 0.0 <= prediction.bearish_probability <= 1.0)
	prob_sum = prediction.bullish_probability + prediction.bearish_probability
	check(
		f"probabilites sum approximately to 1 (got {prob_sum:.4f})",
		abs(prob_sum - 1.0) < prob_sum_threshold,
	)
	return all_passed


def main() -> None:
	total_start = time.perf_counter()
	# --- Load articles ---
	try:
		db_start = time.perf_counter()
		articles = get_latest_articles(limit=ARTICLE_LIMIT)
		db_elapsed = time.perf_counter() - db_start
	except Exception as e:
		print(f"ERROR: failed to load articles from the database: {e}")
		sys.exit(1)
	if not articles:
		print("ERROR: no articles were returned by get_latest_articles().")
		print("Run tests/test_collect_news.py first to populate the database.")
		sys.exit(1)
	# --- Run analysis ---
	try:
		llm_start = time.perf_counter()
		prediction = analyze_news(articles)
		llm_elapsed = time.perf_counter() - llm_start
	except Exception as e:
		print(f"ERROR: LLM analysis request failed: {e}")
		sys.exit(1)
	total_elapsed = time.perf_counter() - total_start
	# --- Report ---
	print_header("MACRO ANALYSIS TEST")
	print(f"Articles supplied: {len(articles)}\n")
	if prediction is None:
		print("ERROR: analyze_news() returned None. No prediction to report.")
		sys.exit(1)
	print(f"Bullish probability: {prediction.bullish_probability:.4f}\n")
	print(f"Bearish probability: {prediction.bearish_probability:.4f}\n")
	print(f"Confidence: {prediction.confidence:.4f}\n")
	print_list("Major Drivers", prediction.major_drivers)
	print()
	print_list("Ignored Articles", prediction.ignored_articles)
	print()
	print("Reasoning:")
	print(prediction.reasoning or "(none provided)")
	print()
	print_list("Invalidation Conditions", prediction.invalidation)
	print("\n" + "=" * 50)
	# --- Validation ---
	passed = validate_prediction(prediction)
	# --- Timing ---
	print_header("TIMING")
	print(f"Database load time: {db_elapsed:.3f}s")
	print(f"LLM request time: {llm_elapsed:.3f}s")
	print(f"Total runtime: {total_elapsed:.3f}s")
	print()
	if passed:
		print("Overall result: PASS")
	else:
		print("Overall result: FAIL")
		sys.exit(1)


if __name__ == "__main__":
	main()
