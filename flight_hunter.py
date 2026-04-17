import os
import yaml
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
    "Seville": "SVQ", "Valencia": "VLC", "Bratislava": "BTS", "Ljubljana": "LJU",
    "Bologna": "BLQ", "Innsbruck": "INN"
}

# Load Smart Budgets from YAML
SMART_BUDGETS = {}
if os.path.exists("smart_budgets.yaml"):
    try:
        with open("smart_budgets.yaml", "r") as f:
            SMART_BUDGETS = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading smart_budgets.yaml: {e}")

def get_season(date_obj):
    """Returns the meteorological season for a given date."""
    month = date_obj.month
    if month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    elif month in [9, 10, 11]:
        return "Autumn"
    else:
        return "Winter"

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

def get_travel_windows():
    """Generates Saturday-Sunday, Friday-Sunday, Saturday-Monday, and Friday-Monday windows."""
    this_year = date.today().year
    windows = []
    
    for year in [this_year, this_year + 1]:
        uk_holidays = holidays.UnitedKingdom(years=year, subdiv='England')
        start_date = max(date.today(), date(year, 1, 1))
        end_date = date(year, 12, 31)
        current = start_date
        while current <= end_date:
            if current.weekday() == 5: # Saturday
                saturday = current
                sunday = saturday + timedelta(days=1)
                monday = saturday + timedelta(days=2)
                friday = saturday - timedelta(days=1)
                
                if friday in uk_holidays and monday in uk_holidays:
                    windows.append({"name": f"Bank Holiday: {uk_holidays[friday]} & {uk_holidays[monday]}", "outbound": friday, "return": monday})
                elif friday in uk_holidays:
                    windows.append({"name": f"Bank Holiday: {uk_holidays[friday]}", "outbound": friday, "return": sunday})
                elif monday in uk_holidays:
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
        "outbound_times": "08,14", # 08:00 to 14:00 (Ensures you aren't leaving too early)
        "return_times": "14,20", # 14:00 to 20:00 (Return in the afternoon/evening)
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
                
            # 2. Filter out 'high' prices. Accept 'low', 'typical', or missing insight.
            if price_level == "high":
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
            
            # Extract the actual Google Flights search URL directly from SerpApi metadata
            google_url = results.get("search_metadata", {}).get("google_flights_url", "")
            if not google_url:
                # Fallback to standard URL format if missing
                google_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest_iata}%20from%20LON%20on%20{window['outbound']}%20through%20{window['return']}"
                
            return {"price": price, "airline": airline, "insight": price_level or "Budget Match", "link": google_url}
            
        return None
    except Exception as e:
        print(f"Google Flights verification failed for {dest_iata}: {e}")
        return None

def main():
    print("--- Flight Hunter 3.0: Priority Sunday Scan ---")
    
    # Load Visited Cities and Seasons from YAML
    visited_cities = {}
    if os.path.exists("visited_cities.yaml"):
        try:
            with open("visited_cities.yaml", "r") as f:
                visited_cities = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading visited_cities.yaml: {e}")

    # Load Priority Cities from YAML (with Seasonal Preferences)
    priority_cities = {}
    if os.path.exists("priority_cities.yaml"):
        try:
            with open("priority_cities.yaml", "r") as f:
                priority_cities = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading priority_cities.yaml: {e}")

    all_windows = get_travel_windows()

    # Strategy: Weekly Sunday Scan
    # Focus on the 4-12 week window (1-3 months) to hit the "31-60 day" price drop sweet spot.
    four_weeks_out = date.today() + timedelta(weeks=4)
    twelve_weeks_out = date.today() + timedelta(weeks=12)
    
    bh_windows = [w for w in all_windows if "Bank Holiday" in w["name"] and w["outbound"] >= four_weeks_out]
    std_windows = [w for w in all_windows if "Standard Weekend" in w["name"] and four_weeks_out <= w["outbound"] <= twelve_weeks_out]
    
    target_windows = sorted(bh_windows + std_windows, key=lambda x: x["outbound"])

    if not target_windows:
        print("No target windows found in the 4-12 week range.")
        return

    range_str = f"{target_windows[0]['outbound']} to {target_windows[-1]['return']}"
    print(f"Scanning {len(target_windows)} windows ({range_str})...")
    
    # 1. Gather all explore results into a global pool
    global_explore_deals = []
    
    for window in target_windows:
        print(f"Scanning Explore for: {window['outbound']}...")
        explore_results = search_google_explore(window)
        
        current_season = get_season(window["outbound"])
        
        for g_deal in explore_results:
            dest_name = g_deal.get("name", "Unknown")
            # Substring match
            iata_code = next((code for city, code in CITY_TO_IATA.items() if city.lower() in dest_name.lower()), None)
            
            if iata_code:
                # Exclusion Logic: Skip if city visited in the same season
                if iata_code in visited_cities and current_season in visited_cities[iata_code]:
                    continue
                    
                # Pre-filter: Don't waste Deep Dive credits if Explore price is already above Smart Budget
                explore_price = g_deal.get("flight_price", 9999)
                max_budget = min(150, SMART_BUDGETS.get(iata_code, 150))
                if explore_price > max_budget:
                    continue
                    
                global_explore_deals.append({
                    "window": window,
                    "name": dest_name,
                    "iata": iata_code,
                    "price": explore_price
                })

    print(f"  Found {len(global_explore_deals)} valid options after season filtering.")
    
    # 2. Sort all options globally: Seasonal Priority -> Generic Priority -> Price
    def get_priority_score(deal):
        iata = deal["iata"]
        season = get_season(deal["window"]["outbound"])
        
        if iata in priority_cities:
            preferred_seasons = priority_cities[iata]
            # Priority 0: Matches preferred season
            if not preferred_seasons or season in preferred_seasons:
                return 0
            # Priority 1: In list but wrong season
            return 1
        # Priority 2: Not in priority list
        return 2

    global_explore_deals = sorted(
        global_explore_deals, 
        key=lambda x: (get_priority_score(x), x["price"])
    )
    
    all_deals = []
    destination_counts = {}
    deep_dives_performed = 0
    MAX_DEEP_DIVES = 30 # Weekly Strategy: ~45 credits total per Sunday run
    MAX_PER_DESTINATION = 2 # Only show a specific city twice
    
    # 3. Deep Dive into the absolute cheapest options first
    for e_deal in global_explore_deals:
        if deep_dives_performed >= MAX_DEEP_DIVES:
            print("  [!] Deep dive limit reached.")
            break
            
        dest_name = e_deal["name"]
        
        # Diversity Check
        if destination_counts.get(dest_name, 0) >= MAX_PER_DESTINATION:
            continue
            
        iata_code = e_deal["iata"]
        window = e_deal["window"]
        
        print(f"  -> Verifying {dest_name} ({iata_code}) for {window['outbound']} (£{e_deal['price']})...")
        deep_dives_performed += 1
        
        verified_deal = verify_deal_with_google_flights(window, iata_code)
        if verified_deal:
            print(f"  ✓ Verified Deal Found for {dest_name} (£{verified_deal['price']})")
            
            is_priority = get_priority_score(e_deal) == 0
            dest_display = f"⭐ {dest_name}" if is_priority else dest_name

            all_deals.append({
                "dest": dest_display, 
                "price": verified_deal['price'], 
                "dates": f"{window['outbound']} to {window['return']}",
                "notes": window["name"], 
                "insight": verified_deal['insight'], 
                "source": "Google Flights",
                "airline": verified_deal['airline'],
                "link": verified_deal.get("link", ""),
                "is_priority": is_priority
            })
            
            destination_counts[dest_name] = destination_counts.get(dest_name, 0) + 1
            
            if len(all_deals) >= 12:
                print("  [!] Found 12 verified deals. Stopping.")
                break

    if not all_deals:
        send_html_email("🔍 No Deals Found Today", f"<p>Searched {range_str}. No direct flights matching your Smart Budget, 'low'/'typical' pricing, and strict timing (08:00-14:00 Out, 14:00-20:00 Back) were found.</p>")
    else:
        # Sort and deduplicate
        all_deals = sorted(all_deals, key=lambda x: x['price'])
        priority_deals = [d for d in all_deals if d.get('is_priority')]
        explore_deals = [d for d in all_deals if not d.get('is_priority')]
        
        def build_table(deals, title):
            if not deals: return ""
            t = f"<h3 style='color: #333; margin-top: 20px; font-size: 16px;'>{title}</h3><table style='width: 100%; border-collapse: collapse;'><tr style='background: #f8f9fa;'><th style='padding: 10px; text-align: left; border-bottom: 2px solid #eee;'>Destination</th><th style='padding: 10px; text-align: left; border-bottom: 2px solid #eee;'>Price</th><th style='padding: 10px; text-align: left; border-bottom: 2px solid #eee;'>Dates</th></tr>"
            for d in deals[:15]:
                t += f"<tr><td style='padding: 12px; border-bottom: 1px solid #eee;'><b>{d['dest']}</b><br><small style='color:#999'>{d['airline']}</small></td><td style='padding: 12px; border-bottom: 1px solid #eee;'><span style='color: #28a745; font-weight: bold;'>£{d['price']}</span><br><small>{d['insight']}</small></td><td style='padding: 12px; border-bottom: 1px solid #eee;'>{d['dates']}<br><small>{d['notes']}</small></td></tr><tr><td colspan='3' style='padding: 5px 12px 15px 12px; border-bottom: 1px solid #eee;'><a href='{d['link']}' style='background: #1a73e8; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px;'>Book on Google Flights</a></td></tr>"
            t += "</table>"
            return t
        
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
            <h2 style="color: #1a73e8; margin-bottom: 5px;">✈️ Flight Hunter: Weekly Sunday Scan</h2>
            <p style="color: #666; margin-top: 0;">Searching from <b>{range_str}</b><br>Budget: Smart Budgets (Up to £150) | Hand Luggage Only | Direct Flights<br>Timing: 08:00-14:00 Out, 14:00-20:00 Back</p>
            {build_table(priority_deals, '⭐ Priority Deals')}
            {build_table(explore_deals, '💸 Other Great Deals')}
        </div>"""
        send_html_email(f"✈️ {len(all_deals)} Flight Deals Found!", html)

if __name__ == "__main__":
    main()
