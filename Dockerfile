FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py login.py ./

# Muhim: MTProto login interaktiv. Session faylni tashqaridan mount qiling:
#   docker run -i --rm \
#     -e TELEGRAM_API_ID=123 -e TELEGRAM_API_HASH=abc \
#     -v $(pwd)/telegram_mcp.session:/app/telegram_mcp.session \
#     telegram-mcp
# Login faylni avval host'da `python login.py` bilan yarating.

ENTRYPOINT ["python", "server.py"]
