FROM python:3.11.4-slim AS builder

WORKDIR /app/backend
COPY requirements.txt /app/backend/
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.11.4-slim AS runner

WORKDIR /app/backend
# Копіюємо site-packages (бібліотеки) і bin (виконувані файли)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . /app/backend

EXPOSE 8000

CMD ["hypercorn", "api.main:app", "--bind", "0.0.0.0:8000"]