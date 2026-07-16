"""Integration tests for the news collection layer."""
import sys
import os

# Ensure parent directory is in the path to import weavefeed modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed")))

from collector import collect_news

def main():
	# Simulated execution timestamp for logging context
	print("\n========================================")
	print("Execution Context:")
	print("July 14, 2026")
	print("8:45")
	print("America/New_York")
	print("========================================\n")

	print("Starting pipeline test (Limit: 15 articles per source)...\n")

	# Run the collector requesting exactly 15 articles per source
	unique_articles, inserted_count, skipped_count = collect_news(limit_per_source=5)

	print("--- Aritcles Collected ---")
	for article in unique_articles:
		print(f"[{article.source}] {article.published_at.strftime('%Y-%m-%d %H:%M%S UTC')}")
		print(f"Title: {article.title}")
		print(f"URL: {article.url}")
		print("-" * 40)

	print("\n=== Collection Report ===")

	# If the limit works perfectly this should be 15 (3 sources * 5)
	total_fetched = sum(1 for a in unique_articles)

	print(f"Unique articles fetched: {total_fetched}")
	print(f"Articles inserted into DB: {inserted_count}")
	print(f"Articles skipped (DB conflict): {skipped_count}")
	print("=========================\n")

if __name__ == "__main__":
	main()
