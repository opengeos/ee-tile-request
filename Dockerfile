FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl git npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
COPY main.py .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
