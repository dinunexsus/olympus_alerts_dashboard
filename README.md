# olympus_alerts_dashboard

# Flask OpsGenie Alerts Processor

This Flask application fetches and processes OpsGenie alerts from Gmail emails and provides a web interface to view and analyze the alerts.

## Features

- Fetches OpsGenie alerts from emails based on a specified date.
- Parses email content and retrieves OpsGenie alert details using the OpsGenie API.
- Provides a web interface to view processed alerts.

## Getting Started

### Prerequisites

Make sure you have Python installed on your system.

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
Install dependencies:


pip install -r requirements.txt

Set up your environment variables. Create a .env file in the project root with the following variables:

env

YOUR_EMAIL=your-email@gmail.com
YOUR_PASSWORD=your-email-password
OPS_GENIE_API_KEY=your-opsgenie-api-key
Replace your-email@gmail.com, your-email-password, and your-opsgenie-api-key with your actual credentials.

Run the Flask application:

bash
Copy code
python app.py
Open your web browser and go to http://127.0.0.1:5000/ to access the web interface.

Usage
Access the web interface to view and analyze OpsGenie alerts for a specific date.
API
You can also programmatically fetch alerts using the API endpoint:

Endpoint: /api/process_alerts

Method: POST

Request Payload:

json

{
    "date": "yyyy-mm-dd"
}
Response:

json

{
    "alerts": [...],
    "processing_time_seconds": 1.23,
    "count_alerts": 5
}
