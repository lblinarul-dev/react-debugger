# FastAPI Backend for News Aggregation

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/news_db
export OPENAI_API_KEY=your_openai_api_key
export TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

3. Run migrations:
```bash
alembic upgrade head
```

4. Start the server:
```bash
uvicorn main:app --reload
```
