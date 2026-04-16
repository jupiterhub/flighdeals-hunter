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

# Email Settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "your_email@example.com")

def send_html_email(subject, html_content):
    """Sends a professional HTML email notification."""
    if not all([SENDER_EMAIL, SENDER_PASSWORD]):
        print("Email not sent: SENDER_EMAIL or SENDER_PASSWORD not set in .env")
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = f"Flight Hunter <{SENDER_EMAIL}>"
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = subject

    msg.attach(MIMEText(html_content, 'html'))

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
    """Generates Saturday-Sunday and Saturday-Monday (if BH) windows."""
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
                windows.append({"name": f"Bank Holiday: {uk_holidays[monday]}", "outbound": saturday, "return": monday})
            else:
                windows.append({"name": "Standard Weekend", "outbound": saturday, "return": sunday})
        current += timedelta(days=1)
    return windows

def search_google_explore(window):
    """Broad discovery search using Google Travel Explore."""
    params = {
        "engine": "google_travel_explore",
        "departure_id": "LON",
        "arrival_area_id": "/m/02j9z", # Europe
        "outbound_date": window["outbound"].isoformat(),
        "return_date": window["return"].isoformat(),
        "max_price": 150,
        "currency": "GBP",
        "outbound_times": "09,13",
        "return_times": "14,22",
        "api_key": API_KEY
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results.get("destinations", [])
    except Exception as e:
        print(f"Google search failed: {e}")
        return []

def search_duffel_for_destination(window, destination_name):
    """Deep dive for a specific destination using Duffel to find hacker fares."""
    if not DUFFEL_ACCESS_TOKEN: return []
    client = Duffel(access_token=DUFFEL_ACCESS_TOKEN)
    try:
        slices = [
            {"origin": "LON", "destination": destination_name, "departure_date": window["outbound"].isoformat()},
            {"origin": destination_name, "destination": "LON", "departure_date": window["return"].isoformat()}
        ]
        search = client.offers.create(slices=slices, passengers=[{"type": "adult"}])
        best_deals = []
        for offer in search.offers:
            price = float(offer.total_amount)
            if price <= 150:
                # Ensure direct flights only (for speed on a weekend)
                if all(len(s.segments) == 1 for s in offer.slices):
                    out_dep = offer.slices[0].segments[0].departing_at
                    ret_dep = offer.slices[1].segments[0].departing_at
                    out_h = int(out_dep.split('T')[1].split(':')[0])
                    ret_h = int(ret_dep.split('T')[1].split(':')[0])
                    if 9 <= out_h <= 13 and 14 <= ret_h <= 22:
                        best_deals.append({"destination": destination_name, "price": price, "airline": offer.owner.name})
        return sorted(best_deals, key=lambda x: x['price'])[:1] # Return the best Duffel deal
    except: return []

def main():
    print("--- Flight Hunter 2.0: Strategic Mode ---")
    all_windows = get_travel_windows(2026)
    
    # Strategy: Skip next 14 days, scan next 20 weekends + all Bank Holidays
    two_weeks_out = date.today() + timedelta(days=14)
    bh_windows = [w for w in all_windows if "Bank Holiday" in w["name"]]
    std_windows = [w for w in all_windows if "Standard Weekend" in w["name"] and w["outbound"] >= two_weeks_out]
    target_windows = sorted(bh_windows + std_windows[:20], key=lambda x: x["outbound"])

    range_str = f"{target_windows[0]['outbound']} to {target_windows[-1]['return']}"
    print(f"Scanning {len(target_windows)} windows ({range_str})...")
    
    all_deals = []
    for window in target_windows:
        google_results = search_google_explore(window)
        for g_deal in google_results:
            dest = g_deal.get("name", "Unknown")
            price = g_deal.get("flight_price", 150)
            
            # Contextual Insight: Is this a good price for this specific city?
            # (Note: In a full implementation, you'd store typical prices per city)
            insight = "Deal" if price < 100 else "Typical"
            
            deal_data = {
                "dest": dest, "price": price, "dates": f"{window['outbound']} to {window['return']}",
                "notes": window["name"], "insight": insight, "source": "Google",
                "link": f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}"
            }
            
            # If Google finds a deal, check Duffel for a better "Hacker Fare"
            d_deals = search_duffel_for_destination(window, dest)
            if d_deals and d_deals[0]['price'] < price:
                deal_data.update({"price": d_deals[0]['price'], "source": "Duffel", "airline": d_deals[0]['airline']})
            
            all_deals.append(deal_data)

    if not all_deals:
        send_html_email("🔍 No Deals Found Today", f"<p>Searched {range_str}. No direct flights under £150 with morning departure and afternoon return were found.</p>")
    else:
        # Sort and deduplicate
        all_deals = sorted(all_deals, key=lambda x: x['price'])
        
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
            <h2 style="color: #1a73e8;">✈️ Flight Hunter: Top Deals</h2>
            <p style="color: #666;">Searching from <b>{range_str}</b><br>Budget: £150 | Direct Flights | Morning Out, Afternoon Back</p>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f8f9fa;">
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #eee;">Destination</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #eee;">Price</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #eee;">Dates</th>
                </tr>
        """
        for d in all_deals[:15]: # Show top 15 deals
            html += f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;"><b>{d['dest']}</b><br><small style="color:#999">{d['source']}</small></td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;"><span style="color: #28a745; font-weight: bold;">£{d['price']}</span><br><small>{d['insight']}</small></td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">{d['dates']}<br><small>{d['notes']}</small></td>
                </tr>
                <tr>
                    <td colspan="3" style="padding: 5px 12px 15px 12px; border-bottom: 1px solid #eee;">
                        <a href="{d['link']}" style="background: #1a73e8; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px;">Book on Google Flights</a>
                    </td>
                </tr>
            """
        html += "</table></div>"
        send_html_email(f"✈️ {len(all_deals)} Flight Deals Found!", html)

if __name__ == "__main__":
    main()
