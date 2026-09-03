# ── Deep Research — cloud-deployable research service ───────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Use Tsinghua PyPI mirror (essential for servers inside China)
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# ── install dependencies in one cached layer ─────────────────────────
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    litellm \
    openai \
    orjson \
    pydantic \
    python-dotenv \
    httpx \
    firecrawl \
    tavily-python \
    duckduckgo-search \
    fastapi \
    "uvicorn[standard]" \
    asyncpg

# ── application code ────────────────────────────────────────────────
COPY src/ src/
COPY web/ web/

# Make the package importable without editable install
ENV PYTHONPATH=/app/src

RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/data /app/runs /app/logs && \
    chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "web.api:app", "--host", "0.0.0.0", "--port", "8000"]
