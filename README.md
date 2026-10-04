# CrisisConnect API

Backend service for CrisisConnect, built with FastAPI. The project currently provides application startup, database initialization, request-rate-limiting configuration, and a reusable database-session dependency.

## Features

- FastAPI application titled **CrisisConnect API**
- SQLModel database engine managed through Alembic migrations
- Database session dependency for route handlers
- IP-based request rate limiting via SlowAPI
- Environment-based database configuration

## Requirements

- Python 3.10 or later
- A database supported by SQLAlchemy/SQLModel (SQLite is suitable for local development)

## Setup

1. Clone the repository and enter the project directory.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

3. Install the project dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root and define the database URL:

   ```env
   DATABASE_URL=sqlite:///./crisisconnect.db
   ```

5. Start the development server:

   ```bash
   uvicorn main:app --reload
   ```

The API will be available at `http://127.0.0.1:8000`.

## API documentation

Once the server is running, FastAPI provides interactive documentation at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Project structure

```text
.
├── main.py                         # FastAPI app and startup configuration
├── db/
│   └── database.py                 # Database engine, initialization, sessions
├── core/
│   └── session_dependency.py       # Injected SQLModel session type
├── rate_limiter/
│   └── rate_limiter.py             # SlowAPI limiter configuration
├── .env.example                    # Environment-variable template
├── migrations/                     # Alembic migration environment and revisions
├── alembic.ini                     # Alembic configuration
└── requirements.txt                # Python dependencies
```

## Database sessions

Use `sessionDep` when defining route handlers that need a SQLModel session:

```python
from fastapi import APIRouter
from core.session_dependency import sessionDep

router = APIRouter()

@router.get("/example")
def example(session: sessionDep):
    return {"status": "ok"}
```

## Database migrations

Alembic reads `DATABASE_URL` from `.env`, so the API and migration commands
always target the same database. Run these commands from the project root:

```bash
# Generate a migration after adding or changing SQLModel models.
alembic revision --autogenerate -m "describe the schema change"

# Apply all pending migrations.
alembic upgrade head

# View the database's current migration revision.
alembic current
```

Add each new model module to the import section in `migrations/env.py`; this
registers its tables in `SQLModel.metadata`, allowing `--autogenerate` to
detect schema changes. Do not use `SQLModel.metadata.create_all()` in the API
once Alembic manages the schema.

## Rate limiting

The application uses SlowAPI with the client's remote IP address as the rate-limit key. Add limits to individual endpoints as they are implemented, for example:

```python
from fastapi import Request
from rate_limiter.rate_limiter import limiter

@router.get("/example")
@limiter.limit("10/minute")
def example(request: Request):
    return {"status": "ok"}
```

## Configuration

| Variable       | Description                                   | Example                                                      |
| -------------- | --------------------------------------------- | ------------------------------------------------------------ |
| `DATABASE_URL` | SQLAlchemy-compatible database connection URL | `postgresql+psycopg2://name:password@localhost:5432/db-name` |

## Notes

The application imports `fastapi`, `sqlmodel`, `slowapi`, and `uvicorn` for local development. Ensure these packages are present in `requirements.txt` if they are not already installed in your environment.
