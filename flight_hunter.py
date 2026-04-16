import os
import holidays
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from serpapi import GoogleSearch
from duffel_api import Duffel
from dotenv import load_dotenv

# Load API Keys and Email settings from .env
load_dotenv()
API_KEY = os.getenv("SERPAPI_KEY")
DUFFEL_ACCESS_TOKEN = os.getenv("DUFFEL_ACCESS_TOKEN")

# Top European Destinations for Duffel (since it needs specific codes)
DESTINATIONS = ["FCO", "LIS", "CDG", "AMS", "BCN", "MAD", "PRG", "BER", "CPH", "DUB"]

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
    
    start_date = max(date.today(), date(year, 1, 1))
    end_date = date(year, 12, 31)
    
    current = start_date
    while current <= end_date:
        if current.weekday() == 5: # Saturday
            saturday = current
            sunday = saturday + timedelta(days=1)
            monday = saturday + timedelta(days=2)
            
            if monday in uk_holidays:
                windows.append({
                    "name": f"Bank Holiday: {uk_holidays[monday]}",
                    "outbound": saturday,
                    "return": monday
                })
            else:
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
        "outbound_times": "05,12",
        "return_times": "14,22",
        "api_key": API_KEY
    }

    print(f"Searching for {window['name']} ({window['outbound']} to {window['return']}) on Google...")
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results.get("destinations", [])
    except Exception as e:
        print(f"Google search failed: {e}")
        return []

def search_duffel_flights(window):
    """Calls Duffel API to find deals for targeted destinations."""
    if not DUFFEL_ACCESS_TOKEN:
        print("Skipping Duffel: DUFFEL_ACCESS_TOKEN not found in .env")
        return []

    client = Duffel(access_token=DUFFEL_ACCESS_TOKEN)
    results = []

    for dest in DESTINATIONS:
        try:
            slices = [
                {
                    "origin": "LON",
                    "destination": dest,
                    "departure_date": window["outbound"].isoformat(),
                },
                {
                    "origin": dest,
                    "destination": "LON",
                    "departure_date": window["return"].isoformat(),
                }
            ]
            
            search = client.offers.create(
                slices=slices,
                passengers=[{"type": "adult"}]
            )
            
            for offer in search.offers:
                price = float(offer.total_amount)
                if price <= 100:
                    out_dep_at = offer.slices[0].segments[0].departing_at
                    ret_dep_at = offer.slices[1].segments[0].departing_at
                    
                    out_hour = int(out_dep_at.split('T')[1].split(':')[0])
                    ret_hour = int(ret_dep_at.split('T')[1].split(':')[0])
                    
                    if 5 <= out_hour <= 12 and 14 <= ret_hour <= 22:
                        results.append({
                            "destination": dest,
                            "price": price,
                            "airline": offer.owner.name,
                            "link": f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}"
                        })
        except Exception as e:
            print(f"Duffel search for {dest} failed: {e}")
            continue
            
    return results

def main():
    print("--- Flight Hunter: London to Europe < £100 ---")
    all_windows = get_travel_windows(2026)
    
    bh_windows = [w for w in all_windows if "Bank Holiday" in w["name"]]
    std_windows = [w for w in all_windows if "Standard Weekend" in w["name"]]
    target_windows = bh_windows + std_windows[:4]
    
    unique_windows = []
    seen_dates = set()
    for w in sorted(target_windows, key=lambda x: x["outbound"]):
        if w["outbound"] not in seen_dates:
            unique_windows.append(w)
            seen_dates.add(w["outbound"])

    print(f"Plan: Scanning {len(unique_windows)} travel windows across Google and Duffel.")
    all_deals = {}
    
    for window in unique_windows:
        # 1. Google
        google_results = search_flights(window)
        for deal in google_results:
            dest = deal.get("name", "Unknown")
            price = deal.get("flight_price", 0)
            key = f"{dest}-{window['outbound']}-{price}"
            all_deals[key] = {
                "window": window, "destination": dest, "price": price,
                "airline": deal.get("airline", "Unknown"),
                "link": f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}",
                "source": "Google"
            }
            
        # 2. Duffel
        duffel_results = search_duffel_flights(window)
        for deal in duffel_results:
            dest = deal["destination"]
            price = deal["price"]
            key = f"{dest}-{window['outbound']}-{price}"
            if key not in all_deals or price < all_deals[key]["price"]:
                all_deals[key] = {
                    "window": window, "destination": dest, "price": price,
                    "airline": deal["airline"], "link": deal["link"], "source": "Duffel"
                }

    if not all_deals:
        print("No deals found for under £100.")
        send_email("🔍 Flight Hunter: No deals found today", 
                   "The Flight Hunter found no results matching your criteria for the rest of 2026.")
    else:
        final_list = sorted(all_deals.values(), key=lambda x: (x["window"]["outbound"], x["price"]))
        email_body = "Flight Hunter Results: London to Europe < £100\n\n"
        email_body += f"{'Destination':<20} {'Price':<10} {'Dates':<25} {'Source'}\n" + "-" * 75 + "\n"
        for deal in final_list:
            date_str = f"{deal['window']['outbound']} - {deal['window']['return']}"
            email_body += f"{deal['destination']:<20} £{deal['price']:<9} {date_str:<25} {deal['source']}\n"
            email_body += f"   Booking Link: {deal['link']}\n\n"
        
        print(f"\nFound {len(final_list)} possible deals!")
        send_email(f"✈️ {len(final_list)} Flight Deals Found for under £100!", email_body)

if __name__ == "__main__":
    main()
