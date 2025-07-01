FROM python:3.11.4-slim

WORKDIR /app/forecasting

COPY requirements.txt /app/forecasting/
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/forecasting

ENV PYTHONPATH=/app/forecasting:/app/backend
ENV FC_CONFIG=config/demo.yml

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
