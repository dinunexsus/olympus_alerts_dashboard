import logging
import email
import os
import time
import aiohttp
import asyncio
from datetime import datetime
from imapclient import IMAPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global cache dictionary
cache = {}

async def get_alert_details(alert_id, OPS_GENIE_API_KEY):
    # Check if the data is already in the cache
    if alert_id in cache:
        return cache[alert_id]

    headers = {"Authorization": "GenieKey " + OPS_GENIE_API_KEY}
    url = f"https://api.opsgenie.com/v2/alerts/{alert_id}"

    async with aiohttp.ClientSession() as session:
        retries = 3
        backoff_factor = 2
        for attempt in range(retries):
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 401:
                        logging.error("Unauthorized access. Check your API key.")
                        return None
                    elif response.status == 429:
                        wait_time = backoff_factor ** attempt
                        logging.warning(f"Rate limit exceeded. Retrying in {wait_time} seconds.")
                        await asyncio.sleep(wait_time)
                        continue
                    elif 400 <= response.status < 500:
                        logging.error(f"Client Error: {response.status}")
                        return None

                    data = await response.json()
                    # Save the fetched data in the cache
                    cache[alert_id] = data.get("data")
                    return data.get("data")
            except aiohttp.ClientError as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2)  
                    continue
                else:
                    logging.error(f"Error fetching OpsGenie data: {e}")
                    return None
                
def parse_iso_date(date_string):
    # Split the date string into date and time parts
    date_part, time_part = date_string.split('T')
    
    # Check if the time part contains a timezone
    if '+' in time_part:
        time_main, tz = time_part.split('+')
    elif 'Z' in time_part:
        time_main = time_part.rstrip('Z')
        tz = '00:00'
    else:
        time_main = time_part
        tz = None

    # Split the time part into main and fractional parts
    if '.' in time_main:
        time_main, fractional = time_main.split('.')
        # Ensure the fractional part is always 6 digits (microseconds)
        fractional = fractional.ljust(6, '0')
        time_main = f'{time_main}.{fractional}'
    else:
        time_main = f'{time_main}.000000'  # Add zero microseconds if not present

    # Reconstruct the date string
    if tz:
        date_string = f'{date_part}T{time_main}+{tz}'
    else:
        date_string = f'{date_part}T{time_main}'

    try:
        # Parse the corrected date string
        return datetime.fromisoformat(date_string)
    except ValueError as e:
        logging.error(f"Date parsing error: Invalid isoformat string: '{date_string}' - {e}")
        return None

def extract_field(content, field_name):
    try:
        if field_name == 'description':
            return content.split('description:')[1].split(' message:')[0]
        elif field_name == 'Show Alert':
            return content.split('Show Alert (')[1].split(')')[0]
        else:
            return content.split(field_name + ':')[1].split()[0]
    except IndexError:
      
        return None
def fetch_emails(client, search_query):
    try:
        msgnums = client.search(search_query, charset="UTF-8")
        if not msgnums:
            logging.info("No emails found for the given search query.")
            return []

        response = client.fetch(msgnums, ('RFC822',))
        emails = [email.message_from_bytes(msg_data[b"RFC822"]) for _, msg_data in response.items()]
        logging.info(f"Fetched {len(emails)} emails.")
        return emails
    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        return []
    

def parse_email(msg):
    try:
        if msg.is_multipart():
            content = ''.join(part.get_payload(decode=True).decode("utf-8", errors="ignore")
                              for part in msg.walk() if part.get_content_type() == "text/plain")
        else:
            content = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        return {
            'alertname': extract_field(content, 'alertname'),
            'zone': extract_field(content, 'zone'),
            'description': extract_field(content, 'description'),
            'show_alert_link': extract_field(content, 'Show Alert')
        }
    except Exception as e:
        logging.error(f"Error parsing email: {e}")
        return {}
    
async def process_email_async(msg, OPS_GENIE_API_KEY, formatted_date):
    time_difference = None  
    time_to_ack = None  
    time_to_close = None
    try:
       email_data = parse_email(msg)
       if email_data['show_alert_link']:
            alert_id = email_data['show_alert_link'].split('/')[-1]
            alert_details = await get_alert_details(alert_id, OPS_GENIE_API_KEY)

            if alert_details:
                # Extracting individual fields from the OpsGenie alert details
            
                alert_id = alert_details.get('id', '')
                tiny_id = alert_details.get('tinyId', '')
                alias = alert_details.get('alias', '')
                status = alert_details.get('status', '')
                acknowledged = alert_details.get('acknowledged', False)
                is_seen = alert_details.get('isSeen', False)
                count = alert_details.get('count', 0)
                last_occurred_at = alert_details.get('lastOccurredAt', '')
                created_at = alert_details.get('createdAt', '')
                updated_at = alert_details.get('updatedAt', '')
                source = alert_details.get('source', '')
                owner = alert_details.get('owner', '')
                ack_time = alert_details.get('report', {}).get('ackTime', None)
                close_time = alert_details.get('report', {}).get('closeTime', None)
                acknowledged_by = alert_details.get('report', {}).get('acknowledgedBy', '')
                closed_by = alert_details.get('report', {}).get('closedBy', '')
                priority = alert_details.get('priority', '').upper()  
                severity = alert_details.get('details', {}).get('severity', '')
                prometheus_url = alert_details.get('details', {}).get('prometheus_url', '')
                grafana_url = alert_details.get('details', {}).get('grafana_url', '')
                runbook_url = alert_details.get('details', {}).get('runbook_url', '')
                cluster = alert_details.get('details', {}).get('cluster', '')
                namespace = alert_details.get('details', {}).get('namespace', '')
                service = alert_details.get('details', {}).get('service', '')
                job = alert_details.get('details', {}).get('job', '')
                contact_method = "Call" if priority in ["P1", "P2"] else "Email"
                tags = alert_details.get('tags', [])
                
                try:
                    # Use the parse_iso_date function for parsing
                    created_at_datetime = parse_iso_date(created_at)
                    updated_at_datetime = parse_iso_date(updated_at)

                    if created_at_datetime and updated_at_datetime:
                        ack_time_minutes = int(ack_time) / 60000 if ack_time is not None else None
                        close_time = int(close_time) / 60000 if close_time is not None else None
                        alert_duration_minutes = (updated_at_datetime - created_at_datetime).total_seconds() / 60

                        time_to_ack = round(ack_time_minutes, 3) if ack_time_minutes is not None else None
                        time_to_close = round(alert_duration_minutes, 3)

                        if time_to_ack is not None and time_to_close is not None:
                            time_difference = abs(time_to_close - time_to_ack)
                            time_difference = round(time_difference, 3)

                except ValueError as e:
                    logging.error(f"Date parsing error: {e}")
                    # Set to None in case of error
                    time_to_ack = None
                    time_to_close = None


                return {
                
                "Date": formatted_date,
                "Tiny ID":tiny_id,
                "Alert ID":alert_id,
                "Alias":alias,
                "Alert Name": email_data['alertname'],
                "Description":email_data['description'], 
                "Priority":priority,
                "Tags":tags,
                "Zone":email_data['zone'], 
                "Cluster":cluster,
                "Namespace":namespace,
                "Alert Creation Time":created_at,
                "Alert Last Updated At":updated_at, 
                "Count":count, 
                "Is Seen":is_seen,
                "Acknowledged":acknowledged,
                "Last Occured At":last_occurred_at, 
                "Source":source,
                "Owner":owner,
                "Severity":severity,
                "Status":status, 
                "Service":service, 
                "Job":job,
                "Ack Time":ack_time,
                "Alert Ack By":acknowledged_by,
                "Time To ACK":time_to_ack,
                "Time To Close": time_to_close,
                "Close Time":close_time,
                "Closed By": closed_by, 
                "Alert Link":email_data['show_alert_link'], 
                "Runbook ":runbook_url,
                "Prometheus": prometheus_url,
                "Grafana":grafana_url, 
                "Contact Method":contact_method, 
                "Time Diff":time_difference
                
                
                    
                
                    
                    
                }

            
    except Exception as e:
        logging.error(f"Error processing email: {e}")
        return None

async def process_alerts_for_date(date):
    start_time = time.time()
    YOUR_EMAIL = os.environ.get('YOUR_EMAIL')
    YOUR_PASSWORD = os.environ.get('YOUR_PASSWORD')
    OPS_GENIE_API_KEY = os.environ.get('OPS_GENIE_API_KEY')
    TARGET_SUBJECT = "Opsgenie Alert"

    try:
        with IMAPClient("imap.gmail.com", use_uid=True, ssl=True) as client:
            client.login(YOUR_EMAIL, YOUR_PASSWORD)
            client.select_folder("[Gmail]/All Mail")

            formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime("%d-%b-%Y")
            search_query = f'SUBJECT "{TARGET_SUBJECT}" SINCE {formatted_date}'

            emails = fetch_emails(client, search_query)
            if not emails:
                logging.info("No emails found for the given date.")
                return [], 0, 0

            processed_results = await asyncio.gather(
                *[process_email_async(msg, OPS_GENIE_API_KEY, formatted_date) for msg in emails]
            )

            end_time = time.time()
            processing_time = end_time - start_time
            processed_results = [result for result in processed_results if result is not None]
            count_alerts = len(processed_results)
            logging.info(f"Processed {count_alerts} alerts in {processing_time:.2f} seconds.")
            return processed_results, processing_time, count_alerts

    except Exception as e:
        logging.error(f"Error processing alerts: {e}")
        return [], 0, 0