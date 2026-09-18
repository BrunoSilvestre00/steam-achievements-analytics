FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY steam_analytics ./steam_analytics

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "steam_analytics.web:app", "--host", "0.0.0.0", "--port", "8000"]
