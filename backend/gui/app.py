import json
from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime, timedelta, date
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)

# Base URL for the FastAPI backend
API_BASE_URL = "http://api_server:8000" # Assuming your FastAPI is running on this address

logger.info(f"App is runnig on http://localhost:5000/")

@app.route('/')
def index():
    # Render the main dashboard page
    return render_template('dashboard.html')

@app.route('/start_auto_order', methods=['POST'])
def start_auto_order():
    # Handle the auto order start request
    data = request.json
    date_start = data.get('date_start')
    date_finish = data.get('date_finish')
    days_of_order = data.get('days_of_order')

    # Validation
    errors = []

    # Validate date formats
    try:
        date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        date_finish = datetime.strptime(date_finish, "%Y-%m-%d").date()
    except ValueError:
        errors.append("Invalid date format")

    # Validate date range
    if not errors:
        if date_finish <= date_start:
            errors.append("Finish date must be after start date.")
        if (date_finish - date_start) < timedelta(days=7):
            errors.append("Finish date must be at least 7 days after start date.")
        if date_finish == date.today():
            errors.append("The finish date cannot be today. Date must be at least one day ago")
        if date_finish >= date.today():
            errors.append("The finish date cannot be in future")
    # Validate days of order
    try:
        days_of_order = int(days_of_order)
        if days_of_order < 7:
            errors.append("Days of order must be at least 7.")
    except ValueError:
        errors.append("Days of order must be a valid integer.")

    # Return errors if any
    if errors:
        return jsonify({"status": "error", "message": " ".join(errors)}), 422

    # Prepare payload for API request
    payload = {
        "date_start": date_start.isoformat(),
        "date_finish": date_finish.isoformat(),
        "days_of_order": days_of_order
    }

    # Make API request to start auto order
    try:
        response = requests.post(f"{API_BASE_URL}/auto_order", json=payload)
        print(f"GUI -> make request with {API_BASE_URL}/auto_order {payload}")
        response.raise_for_status()
        result = response.json()
        print(f"GUI -> take response from api")
        
    # Записываем данные в файл в формате JSON с отступом
        #print(json.dump(result, indent=4))

        return jsonify({
            "status": "success",
            "message": "Auto order process completed successfully",
            "data": result.get("result", {}),
            "mid_result": result.get("mid_result", {}),
            "analysis_time": result.get("analysis_time", 0),
            "product_count": result.get("product_count", 0),
            "excel_filename_main": result.get("excel_filename_main", ""),
            "filename_mid": result.get("filename_mid", "")
        }), response.status_code
    except requests.RequestException as e:
        if response.status_code == 503:
            return jsonify({"status": "error", "message": "База данных не отвечает. Пожалуйста, попробуйте позже."}), 503
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Configure and run the application using Hypercorn
    config = Config()
    config.bind = ["0.0.0.0:5000"]
    asyncio.run(serve(app, config))
