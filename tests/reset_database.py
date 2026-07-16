import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed")))

from database import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
	"""Truncates core Weavefeed tables to reset the development environment."""

	tables_to_truncate = [
		"evidence",
		"evaluations",
		"predictions",
		"agent_runs",
		"news_articles",
		"prompt_templates",
		"market_data"
	]

	# We use CASCADE to drop dependent rows if foreign keys exist.
	# RESTART IDENTITY resets auto-increment sequences
	query = f"TRUNCATE TABLE {', '.join(tables_to_truncate)} RESTART IDENTITY CASCADE;"
	logger.info("Connecting to database...")
	try:
		with get_connection() as conn:
			with conn.cursor() as cursor:
				logger.info("Executing TRUNCATE command...")
				cursor.execute(query)
			logger.info("Database reset successfully. Schema intact.")
	except Exception as e:
		logger.error(f"Failed to reset database: {e}")

if __name__ == "__main__":

	print("WARNING: This will delete ALL data in the Weavefeed tables.")
	confirmation = input("Are you sure you want to proceed? (yes/no):")

	if confirmation.lower() in ["y", "yes"]:
		reset_database()
	else:
		print("Operation cancelled.")
