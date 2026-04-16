import os
import holidays
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Load API Key and Email settings from .env
load_dotenv()
API_KEY = os.getenv("SERPAPI_KEY")

# Email Settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "your_email@example.com")

def send_email(subject, body):
    """Sends an email notification with the flight deals."""
    if not all([SENDER_EMAIL, SENDER_PASSWORD]):
        print("Email not sent: SENDER_EMAIL or SENDER_PASSWORD not set in .env")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Notification email sent to {RECIPIENT_EMAIL}!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def get_travel_windows(year=2026):
    """Generates all Saturday-Sunday and Saturday-Monday (if BH) windows for the year."""
    uk_holidays = holidays.UnitedKingdom(years=year, subdiv='England')
    windows = []
    
    # Start from the current date or the beginning of the year
    start_date = max(date.today(), date(year, 1, 1))
    end_date = date(year, 12, 31)
    
    current = start_date
    while current <= end_date:
        # Check for Saturday
        if current.weekday() == 5: # 5 is Saturday
            saturday = current
            sunday = saturday + timedelta(days=1)
            monday = saturday + timedelta(days=2)
            
            # If Monday is a holiday, return Monday afternoon
            if monday in uk_holidays:
                windows.append({
                    "name": f"Bank Holiday: {uk_holidays[monday]}",
                    "outbound": saturday,
                    "return": monday
                })
            else:
                # Standard weekend
                windows.append({
                    "name": "Standard Weekend",
                    "outbound": saturday,
                    "return": sunday
                })
        
        current += timedelta(days=1)
    
    return windows

def search_flights(window):
    """Calls SerpApi to find flights for the given travel window."""
    if not API_KEY:
        print("Error: SERPAPI_KEY not found in .env")
        return []

    params = {
        "engine": "google_travel_explore",
        "departure_id": "LON",
        "arrival_area_id": "/m/02j9z", # Europe
        "outbound_date": window["outbound"].isoformat(),
        "return_date": window["return"].isoformat(),
        "max_price": 100,
        "currency": "GBP",
        "outbound_times": "05,12", # Depart between 5 AM and 12 PM
        "return_times": "14,22",   # Return between 2 PM and 10 PM
        "api_key": API_KEY
    }

    print(f"Searching for {window['name']} ({window['outbound']} to {window['return']})...")
    search = GoogleSearch(params)
    results = search.get_dict()
    
    # Extract flight options
    # Note: SerpApi results for travel_explore are in a specific format
    destinations = results.get("flights", [])
    return destinations

def main():
    print("--- Flight Hunter: London to Europe < £100 ---")
    windows = get_travel_windows(2026)
    
    all_deals = []
    
    # Limit to first few for demo/test purposes or process all
    # For a daily script, you might want to process all future windows
    for window in windows:
        # For this script, we'll only search for windows in May to save API credits
        # But you can remove this check to scan the whole year
        if window["outbound"].month == 5:
            deals = search_flights(window)
            for deal in deals:
                all_deals.append({
                    "window": window,
                    "destination": deal.get("destination", "Unknown"),
                    "price": deal.get("price", "N/A"),
                    "airline": deal.get("airline", "Unknown"),
                    "link": f"https://www.google.com/travel/flights?q=Flights%20to%20{deal.get('destination')}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}"
                })

    if not all_deals:
        print("No deals found for under £100 with your criteria.")
    else:
        # Build email content
        email_body = "Flight Hunter Results: London to Europe < £100\n\n"
        email_body += f"{'Destination':<20} {'Price':<10} {'Dates':<25} {'Notes'}\n"
        email_body += "-" * 75 + "\n"
        
        for deal in all_deals:
            date_str = f"{deal['window']['outbound']} - {deal['window']['return']}"
            email_body += f"{deal['destination']:<20} £{deal['price']:<9} {date_str:<25} {deal['window']['name']}\n"
            email_body += f"   Booking Link: {deal['link']}\n\n"

        print(f"\nFound {len(all_deals)} possible deals:\n")
        print(email_body)
        
        # Send email
        subject = f"✈️ {len(all_deals)} Flight Deals Found for under £100!"
        send_email(subject, email_body)

if __name__ == "__main__":
    main()
