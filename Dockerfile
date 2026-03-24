FROM python:3.12.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app src/ src/

ENV DATA_DIR=/app/data

USER app

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=300s --timeout=5s --start-period=60s --retries=2 \
  CMD python -c "from pathlib import Path;import time;p=Path('/app/data/sync_state.json');exit(0 if not p.exists() or time.time()-p.stat().st_mtime<900 else 1)"

CMD ["python", "-u", "-m", "src"]
