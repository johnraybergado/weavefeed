"""
Evaluation workflow entrypoint.
"""

import logging

from evaluator import evaluate_all_pending

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting evaluation workflow")

    evaluations = evaluate_all_pending()

    logger.info(f"Completed {len(evaluations)} evaluations")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    main()
