# Gmail Lead Sync - API Layer

FastAPI backend for the Gmail Lead Sync Web UI.

## Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r ../requirements-api.txt
```

3. Copy environment variables:
```bash
cp .env.example .env
```

4. Edit `.env` and set your configuration values, especially:
   - `ENCRYPTION_KEY` - Use the same key from your existing CLI setup
   - `SECRET_KEY` - Generate a secure random key for sessions

5. Run database migrations:
```bash
cd ..
alembic upgrade head
```

6. Start the development server:
```bash
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000

API documentation will be at http://localhost:8000/docs

## Project Structure

```
api/
├── main.py              # FastAPI application entry point
├── models/              # SQLAlchemy database models
├── routes/              # API route handlers
├── services/            # Business logic services
└── .env.example         # Environment variables template
```

## Tech Stack

- FastAPI 0.104+
- SQLAlchemy 2.0+
- Pydantic 2.0+
- Uvicorn (ASGI server)
- Prometheus Client (metrics)
- bcrypt (password hashing)
