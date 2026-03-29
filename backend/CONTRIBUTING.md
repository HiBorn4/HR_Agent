# Contributing to NexusIQ

## Setup

1. Fork the repo and clone locally
2. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
3. Install deps: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your GCP credentials

## Running tests

```bash
pytest tests/ -v
```

## Code style

- Use Black for formatting: `black .`
- Use isort for imports: `isort .`
- Type hints are encouraged

## Pull Requests

- Branch from `main`
- Keep PRs focused on one feature/fix
- Add tests for new features
- Update README if behavior changes
