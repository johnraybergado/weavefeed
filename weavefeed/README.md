# Weavefeed

Weavefeed is a prototype agentic system that generates and continuously evaluates macroeconomic directional hypotheses for the NQ futures market within the first 30 minutes of the Regular Trading Hours (RTH) open (New York time). The system analyzes financial and macroeconomic news to estimate bullish/bearish market bias over three forecasting horizons:

- Current trading day
- Next trading week
- Next trading month

The project is intended as an R&D prototype for exploring agentic AI workflows, LLM-assisted financial reasoning, and continuous evaluation of macroeconomic hypotheses.

---

# Architecture

Weavefeed follows a simple agentic pipeline:

1. News collection
2. Information storage
3. LLM analysis
4. Agent memory persistence
5. Prediction evaluation

The system is intentionally modular:

| Module | Responsibility |
|----------|----------------|
| collector.py | Retrieve news from external sources |
| database.py | PostgreSQL persistence layer |
| llm.py | Generate macroeconomic analysis |
| prompts.py | Prompt templates and versioning |
| evaluator.py | Compare predictions to market outcomes |
| models.py | Pydantic data models for weavefeed inputs and outputs |
| config.py | Centralized configuration management |
| main.py | Prediction workflow script |
| evaluate.py | Evaluation workflow script |

---

# Database Schema

## news_articles

Stores raw collected news.

## prompt_templates

Stores versioned prompts used by the agent.

## agent_runs

Tracks each execution of the agent.

## predictions

Stores generated directional hypotheses.

## evidence

Links predictions to supporting news articles.

## market_data

Stores OHLCV market outcomes used during evaluation.

## evaluations

Stores prediciton performance metrics.

---

# Agent Workflow

1. Collect macroeconomic news from RSS feeds and APIs.

2. Store all retrieved articles.

3. Retrieve the most recent articles.

4. Submit articles to the LLM.

5. Generate a structured DailyPrediction.

6. Store:
  - Prediction
  - Prompt version
  - Agent run metadata
  - Supporting evidence

7. Once the prediction horizon has completed:

  - Retrieve market data
  - Store market data
  - Compute realized direction
  - Compare prediction against reality
  - Store evaluation

This creates a continuous learning and measurement loop.

---

# Evaluation Methodology

The MVP uses a binary directional accuracy metric.

Predicted Direction:

- Bullish if bullish_probability > bearish_probability
- Bearish otherwise

Observed Direction:

- Bullish if Close > Open
- Bearish otherwise

Prediction Score:

- 1.0 if predicted direction matches observed direction
- 0.0 otherwise

For now, the score intentionally ignores magnitude of movement and focuses only on directional correctness.

# Limitations

The current MVP has several limitations.

## Limited News Coverage

Only a small number of RSS and API sources are used.

## No Historical Context

Predictions are generated using only recent news and do not leverage historical analogues.

## Binary Evaluation

The evaluation framework measures directional accuracy only and ignores move magnitude.

## Single-Horizon Focus

Only daily predictions are currently implemented.

## LLM-Based Reasoning

Predictions depend entirely on the reasoning capabilities of the selected LLM and are not backed by a more transparent statistical forecasting model.

## No Position Sizing

The system does not generate actionable trading signals, position sizes, or risk management recommendations.

---

# Future Work

The long-term objective is to transition from an LLM-centric prediction engine toward a hybrid architecture:

1. LLMs perform information extraction.
2. Structured macroeconomic factors are stored.
3. Statistical models generate forecasts.
4. Historical retrieval and memory provide context.
5. Agentic planning coordinates analysis workflows.

This should improve reproducibility, explainability, and evaluation rigor.

---

# Project Roadmap

## Version 1 (MVP)

### Project Setup

- [X] Initialize project structure
- [X] Configure Python environment
- [X] Configure PostgreSQL database
- [X] Create database schema
- [X] Create configuration management (`config.py`)

---

### News Collection

- [X] Integrate Finnhub API
- [X] Integrate Market Watch and Yahoo Finance RSS
- [X] Collect financial and macroeconomic news
- [-] Remove duplicate articles
- [X] Store raw articles in PostgreSQL

---

### LLM Agent

- [X] Integrate an LLM API
- [X] Design system prompts
- [X] Design analysis prompts
- [X] Generate structured macroeconomic analysis
- [X] Estimate bullish/bearish probabilities for:
  - Daily horizon
- [X] Generate confidence score
- [X] Generate supporting reasoning
- [X] Generate invalidation conditions

---

### Agent Memory

- [X] Store agent runs
- [X] Store predictions
- [X] Link predictions to supporting news articles
- [X] Version prompts used for each run

---

### Evaluation

- [X] Retrieve market data for completed prediction horizons
- [X] Store above market data
- [X] Compare predicted vs observed market direction
- [X] Compute prediction score
- [X] Store evaluation results

---

### Documentation

- [X] Document architecture
- [X] Document database schema
- [X] Document agent workflow
- [X] Document evaluation methodology
- [X] Document limitations
- [X] Document future work

---

# Planned Version 2

* [ ] Implement scheduler to run prediction workflow 15–30 minutes after RTH open
* [ ] Implement separate scheduler for delayed evaluation after market close
* [ ] Add weekly and monthly horizon directional hypothesis estimates
* [ ] Transition daily evaluation target from full-session futures movement to RTH open -> RTH close movement
* [ ] Define evaluation targets for weekly and monthly horizons (prediction timestamp -> horizon close)
* [ ] Expand market data storage to include both:

  * RTH OHLCV
  * Full futures session OHLCV
* [ ] Store overnight gap and session-return statistics
* [ ] Replace free-form LLM predictions with structured macroeconomic factor extraction
* [ ] Define a standardized macroeconomic feature set
* [ ] Store extracted factors in PostgreSQL
* [ ] Backfill 3–5 years of historical NQ market data
* [ ] Build historical news archive
* [ ] Generate historical factor dataset from archived news
* [ ] Train a local statistical prediction model using accumulated historical data
* [ ] Separate information extraction (LLM) from prediction (local model)
* [ ] Introduce return-weighted evaluation metrics in addition to binary accuracy
* [ ] Expand multi-LLM provider/version support with automatic fallback on provider unavailability

---

# Planned Version 3

* [ ] Semantic retrieval using embeddings
* [ ] PostgreSQL + pgvector integration
* [ ] Retrieval-Augmented Generation (RAG)
* [ ] Historical analogue search
* [ ] Historical factor similarity search
* [ ] Regime detection (risk-on, risk-off, inflation, growth, liquidity)
* [ ] Dynamic tool selection
* [ ] Multi-step planning
* [ ] Long-term episodic memory
* [ ] Adaptive prompt optimization
* [ ] Ensemble prediction using multiple statistical models
* [ ] Confidence calibration using historical performance
* [ ] Continuous retraining from accumulated evaluation data
* [ ] Agent-assisted research workflows for hypothesis generation
