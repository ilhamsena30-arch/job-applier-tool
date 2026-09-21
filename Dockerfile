# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# System deps for headed browser under Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run headed browser under a virtual display; dashboard on 8000.
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x720x24 & DISPLAY=:99 uvicorn agent.dashboard:app --host 0.0.0.0 --port 8000"]
