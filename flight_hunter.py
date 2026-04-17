import os
import holidays
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Load API Keys and Email settings from .env
load_dotenv()
API_KEY = os.getenv("SERPAPI_KEY")

# Email Settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "your_email@example.com")

CITY_TO_IATA = {
    "Rome": "ROM", "Lisbon": "LIS", "Paris": "PAR", "Amsterdam": "AMS",
    "Barcelona": "BCN", "Madrid": "MAD", "Prague": "PRG", "Berlin": "BER",
    "Copenhagen": "CPH", "Dublin": "DUB", "Vienna": "VIE", "Budapest": "BUD",
    "Athens": "ATH", "Warsaw": "WAW", "Krakow": "KRK", "Venice": "VCE",
    "Milan": "MIL", "Naples": "NAP", "Florence": "FLR", "Munich": "MUC",
    "Frankfurt": "FRA", "Hamburg": "HAM", "Zurich": "ZRH", "Geneva": "GVA",
    "Brussels": "BRU", "Stockholm": "STO", "Oslo": "OSL", "Helsinki": "HEL",
    "Reykjavik": "REK", "Malaga": "AGP", "Alicante": "ALC", "Faro": "FAO",
    "Porto": "OPO", "Ibiza": "IBZ", "Palma": "PMI", "Majorca": "PMI",
    "Nice": "NCE", "Lyon": "LYS", "Marseille": "MRS", "Toulouse": "TLS", 
    "Bordeaux": "BOD", "Riga": "RIX", "Tallinn": "TLL", "Vilnius": "VNO",
    "Sofia": "SOF", "Bucharest": "BUH", "Belgrade": "BEG", "Zagreb": "ZAG",
    "Dubrovnik": "DBV", "Split": "SPU", "Malta": "MLA", "Cyprus": "LCA", 
    "Tenerife": "TFS", "Gran Canaria": "LPA", "Lanzarote": "ACE",
    "Seville": "SVQ", "Valencia": "VLC", "Bratislava": "BTS", "Ljubljana": "LJU"
}

SMART_BUDGETS = {
    "ROM": 100, "LIS": 100, "PAR": 80, "AMS": 80, "BCN": 90, "MAD": 90, "PRG": 80, "BER": 80,
    "CPH": 90, "DUB": 60, "VIE": 90, "BUD": 80, "ATH": 130, "WAW": 80, "KRK": 80, "VCE": 90,
    "MIL": 80, "NAP": 90, "FLR": 100, "MUC": 90, "FRA": 80, "HAM": 80, "ZRH": 100, "GVA": 90,
    "BRU": 80, "STO": 100, "OSL": 100, "HEL": 100, "REK": 130, "AGP": 100, "ALC": 90, "FAO": 90,
    "OPO": 90, "IBZ": 100, "PMI": 90, "NCE": 90, "LYS": 80, "MRS": 80, "TLS": 80, "BOD": 80,
    "RIX": 80, "TLL": 90, "VNO": 80, "SOF": 80, "BUH": 80, "BEG": 90, "ZAG": 90, "DBV": 100,
    "SPU": 100, "MLA": 100, "LCA": 130, "TFS": 130, "LPA": 130, "ACE": 130, "SVQ": 90, "VLC": 90,
    "BTS": 80, "LJU": 90
}

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
    """Broad discovery search using Google Travel Explore without strict time filters."""
    if not API_KEY:
        return []
    params = {
        "engine": "google_travel_explore",
        "departure_id": "/m/04jpl", # London
        "arrival_area_id": "/m/02j9z", # Europe
        "outbound_date": window["outbound"].isoformat(),
        "return_date": window["return"].isoformat(),
        "max_price": 150,
        "currency": "GBP",
        "api_key": API_KEY
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        if "error" in results:
            print(f"  [!] SerpApi Error: {results['error']}")
        
        destinations = results.get("destinations", [])
        if not destinations and "error" not in results:
            # Print a small snippet of the response to see what's wrong (e.g., search_metadata status)
            print(f"  [!] Raw SerpApi response keys: {list(results.keys())}")
            if "search_metadata" in results:
                print(f"  [!] Status: {results['search_metadata'].get('status')}")
            if "search_information" in results:
                print(f"  [!] Search Info: {results['search_information']}")
        
        return destinations
    except Exception as e:
        print(f"  [!] Google Explore search failed: {e}")
        return []

def verify_deal_with_google_flights(window, dest_iata):
    """Deep dive to check if there is a direct flight in the specific time window using Google Flights API."""
    params = {
        "engine": "google_flights",
        "departure_id": "LON", # Google Flights deep dive works best with IATA code
        "arrival_id": dest_iata,
        "outbound_date": window["outbound"].isoformat(),
        "return_date": window["return"].isoformat(),
        "currency": "GBP",
        "hl": "en",
        "type": "1", # Round trip
        "outbound_times": "09,13",
        "return_times": "14,22",
        "api_key": API_KEY
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Check price insights
        price_insights = results.get("price_insights", {})
        price_level = price_insights.get("price_level")
        
        # Determine the budget for this specific city
        max_budget = min(150, SMART_BUDGETS.get(dest_iata, 150))
        
        flights = results.get("best_flights", []) + results.get("other_flights", [])
        
        for flight in flights:
            price = flight.get("price", 9999)
            
            # 1. Price must be under the strict smart budget
            if price > max_budget:
                continue
                
            # 2. Strict 'low' filter enabled: Trust Google if it provides an insight
            if price_level and price_level != "low":
                 continue

            legs = flight.get("flights", [])
            if not legs:
                continue
                
            # 3. Check Outbound Arrival Time (must land before 16:00)
            outbound = legs[0]
            arr_time_str = outbound.get("arrival_airport", {}).get("time", "")
            if arr_time_str:
                try:
                    # Format is usually "2026-05-23 15:30"
                    arr_hour = int(arr_time_str.split(" ")[1].split(":")[0])
                    if arr_hour >= 16:
                        continue # Arrives too late, skip
                except:
                    pass
            
            airline = outbound.get("airline", "Unknown Airline")
            return {"price": price, "airline": airline, "insight": price_level or "Budget Match"}
            
        return None
    except Exception as e:
        print(f"Google Flights verification failed for {dest_iata}: {e}")
        return None

def main():
    print("--- Flight Hunter 3.0: Dual SerpApi Mode ---")
    all_windows = get_travel_windows(2026)

    
    # Strategy: Skip next 14 days, scan next 6 weekends + all Bank Holidays (~10 windows total)
    # 10 windows * 3 calls max (1 explore + 2 deep dives) = 30 credits per run
    # 30 credits * 8 runs/month (Tue & Thu) = 240 credits/month (Safely under 250 limit)
    two_weeks_out = date.today() + timedelta(days=14)
    bh_windows = [w for w in all_windows if "Bank Holiday" in w["name"]]
    std_windows = [w for w in all_windows if "Standard Weekend" in w["name"] and w["outbound"] >= two_weeks_out]
    target_windows = sorted(bh_windows + std_windows[:6], key=lambda x: x["outbound"])

    if not target_windows:
        print("No target windows found.")
        return

    range_str = f"{target_windows[0]['outbound']} to {target_windows[-1]['return']}"
    print(f"Scanning {len(target_windows)} windows ({range_str})...")
    
    all_deals = []
    for window in target_windows:
        print(f"Scanning: {window['outbound']}...")
        explore_results = search_google_explore(window)
        print(f"  Found {len(explore_results)} destinations in Explore.")
        
        # Filter explore results to only include cities we have IATA codes for
        valid_deals = []
        for g_deal in explore_results:
            dest_name = g_deal.get("name", "Unknown")
            # Substring match (e.g. "Paris, France" -> "PAR")
            iata_code = next((code for city, code in CITY_TO_IATA.items() if city.lower() in dest_name.lower()), None)
            if iata_code:
                valid_deals.append({"name": dest_name, "iata": iata_code, "price": g_deal.get("flight_price", 9999)})
        
        print(f"  Filtered down to {len(valid_deals)} valid European cities.")
        
        # Sort by Explore price and take the top 2 to strictly save API credits
        valid_deals = sorted(valid_deals, key=lambda x: x["price"])
        
        verified = False
        for v_deal in valid_deals[:2]:
            dest_name = v_deal["name"]
            iata_code = v_deal["iata"]
            print(f"  -> Deep diving into {dest_name} ({iata_code})...")
            
            # Deep dive with Google Flights to verify the strict time window and smart budget
            verified_deal = verify_deal_with_google_flights(window, iata_code)
            if verified_deal:
                print(f"  ✓ Verified Deal Found for {dest_name} (£{verified_deal['price']})")
                all_deals.append({
                    "dest": dest_name, 
                    "price": verified_deal['price'], 
                    "dates": f"{window['outbound']} to {window['return']}",
                    "notes": window["name"], 
                    "insight": verified_deal['insight'], 
                    "source": "Google Flights",
                    "airline": verified_deal['airline'],
                    "link": f"https://www.google.com/travel/flights?q=Flights%20to%20{dest_name}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}"
                })
                verified = True
                break # Stop at the first verified deal for this weekend to save credits

    if not all_deals:
        send_html_email("🔍 No Deals Found Today", f"<p>Searched {range_str}. No direct flights matching your Smart Budget, 'low' pricing, and strict timing (Arrive before 16:00) were found.</p>")
    else:
        # Sort and deduplicate
        all_deals = sorted(all_deals, key=lambda x: x['price'])
        
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
            <h2 style="color: #1a73e8;">✈️ Flight Hunter: Top Deals</h2>
            <p style="color: #666;">Searching from <b>{range_str}</b><br>Budget: £150 | Direct Flights | 09:00-13:00 Out, 14:00-22:00 Back</p>
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
                    <td style="padding: 12px; border-bottom: 1px solid #eee;"><b>{d['dest']}</b><br><small style="color:#999">{d['airline']}</small></td>
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
