FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     DEBIAN_FRONTEND=noninteractive     PATH="/opt/venv/bin:$PATH"     PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends     tesseract-ocr     tesseract-ocr-eng     poppler-utils     libgl1     libglib2.0-0     libpq5     curl     && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
