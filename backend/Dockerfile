FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway assigns $PORT at runtime; config.py's env override picks it up too,
# but gunicorn needs to bind to it directly.
ENV PORT=5050
EXPOSE 5050

# Single worker, threaded: results_store (backtest results, exports) is an
# in-process dict in app.extensions - with 2+ workers, a backtest lands in
# one worker and the subsequent GET /api/metrics/<id> or export randomly
# hits the other and 404s. Threads share the dict; fine for a single-user
# research tool. Don't raise --workers without moving the store out of
# process memory first.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120 wsgi:app"]
