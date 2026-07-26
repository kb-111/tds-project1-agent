FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bot uses long polling, not a webhook - no port needs to be exposed.
CMD ["python3", "bot.py"]
