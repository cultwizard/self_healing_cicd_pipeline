FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn
COPY demo_app ./demo_app

EXPOSE 8080
CMD ["uvicorn", "demo_app.app:app", "--host", "0.0.0.0", "--port", "8080"]
