FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install --yes --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . .

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

USER appuser

CMD ["sh", "-c", "streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port ${PORT:-7860}"]
