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
    
    # Extract flight options from 'destinations' key for the explore engine
    destinations = results.get("destinations", [])
    return destinations

def main():
    print("--- Flight Hunter: London to Europe < £100 ---")
    
    # Get all windows for 2026
    all_windows = get_travel_windows(2026)
    
    # FILTER WINDOWS TO SAVE API CREDITS
    # 1. Always include all future Bank Holidays (these are the high-value targets)
    # 2. Include only the next 4 standard weekends (the most relevant ones)
    
    bh_windows = [w for w in all_windows if "Bank Holiday" in w["name"]]
    std_windows = [w for w in all_windows if "Standard Weekend" in w["name"]]
    
    # Only take the next 4 standard weekends
    target_std_windows = std_windows[:4]
    
    # Combine them
    target_windows = bh_windows + target_std_windows
    
    # Remove duplicates and sort by date
    # (Since some BH might be in the next 4 weeks)
    unique_windows = []
    seen_dates = set()
    for w in sorted(target_windows, key=lambda x: x["outbound"]):
        if w["outbound"] not in seen_dates:
            unique_windows.append(w)
            seen_dates.add(w["outbound"])

    print(f"Plan: Scanning {len(unique_windows)} high-priority travel windows to save API credits.")
    
    all_deals = []
    
    for window in unique_windows:
        deals = search_flights(window)
        for deal in deals:
            all_deals.append({
                "window": window,
                "destination": deal.get("name", "Unknown"),
                "price": deal.get("flight_price", "N/A"),
                "airline": deal.get("airline", "Unknown"),
                "link": f"https://www.google.com/travel/flights?q=Flights%20to%20{deal.get('name')}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}"
            })

    if not all_deals:
        print("No deals found for under £100 with your criteria.")
        subject = "🔍 Flight Hunter: No deals found today"
        body = "The Daily Flight Hunter ran but found no results matching your criteria (£100 limit, morning depart, afternoon return) for the rest of 2026."
        send_email(subject, body)
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
