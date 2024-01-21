from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
from datetime import datetime
from alerts import *
import asyncio
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    today = datetime.now().strftime('%Y-%m-%d')
    result= asyncio.run(process_alerts_for_date(today))
    return render_template('index.html', alerts=result, default_date=today)

@app.route('/process_alerts', methods=['GET', 'POST'])
def process_alerts_endpoint():
    if request.method == 'POST':
        requested_date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    else:
        requested_date = datetime.now().strftime('%Y-%m-%d')

    result, processing_time, count_alerts = asyncio.run(process_alerts_for_date(requested_date))
    return render_template('index.html', alerts=result, default_date=requested_date)

@app.route('/api/process_alerts', methods=['POST'])
def api_process_alerts():
    data = request.get_json()
    if not data or 'date' not in data:
        return jsonify({"error": "Date is required in JSON payload."}), 400

    requested_date = data['date']
    result, processing_time, count_alerts = asyncio.run(process_alerts_for_date(requested_date))
    return jsonify({
        "alerts": result,
        "processing_time_seconds": processing_time,
        "count_alerts": count_alerts
    })

if __name__ == '__main__':
    app.run(debug=True)
