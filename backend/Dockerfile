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

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 wsgi:app"]
