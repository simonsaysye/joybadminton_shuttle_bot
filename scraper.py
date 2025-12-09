import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# --- CONFIGURATION ---
URL = "https://joybadminton.com/collections/all-shuttlecock?sort_by=price-descending"
DATA_FILE = "shuttlecocks.json"

# Email credentials from GitHub Secrets
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD") # This must be an App Password, not login password
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

def fetch_current_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Fetching {URL}...")
    try:
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching page: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    products_container = soup.select_one('div.ecom-collection__product-container.ecom-collection__product-container_collection')

    if not products_container:
        print("❌ Product container not found.")
        return {}

    product_items = products_container.select('div > div > div')
    current_products = {}

    for item in product_items:
        name_element = item.select_one('h3 > a')
        if not name_element:
            continue
            
        name = name_element.get_text(strip=True)
        
        # Extract prices
        sale_price = None
        regular_price = None

        sale_element = item.select_one('span.ecom-collection__product-price--sale')
        if sale_element:
            try:
                sale_price = float(sale_element.get_text(strip=True).replace('$', '').replace(',', '').replace(' USD', ''))
            except ValueError: 
                pass
            
            reg_element = item.select_one('span.ecom-collection__product-price--regular')
            if reg_element:
                try:
                    regular_price = float(reg_element.get_text(strip=True).replace('$', '').replace(',', '').replace(' USD', ''))
                except ValueError: 
                    pass
        else:
            reg_element_gen = item.select_one('span.ecom-collection__product-price')
            if reg_element_gen:
                try:
                    regular_price = float(reg_element_gen.get_text(strip=True).replace('$', '').replace(',', '').replace(' USD', ''))
                except ValueError: 
                    pass

        # Store in dictionary keyed by Name for easy comparison
        # Logic: If sale price exists, that's the "effective" price.
        effective_price = sale_price if sale_price is not None else regular_price
        
        current_products[name] = {
            "name": name,
            "regular_price": regular_price,
            "sale_price": sale_price,
            "effective_price": effective_price
        }

    return current_products

def load_previous_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def compare_data(old_data, new_data):
    changes = []
    
    # 1. Check for New Products
    for name, data in new_data.items():
        if name not in old_data:
            changes.append(f"🆕 NEW: {name} - ${data['effective_price']}")

    # 2. Check for Removed Products
    for name in old_data:
        if name not in new_data:
            changes.append(f"❌ REMOVED: {name}")

    # 3. Check for Price Changes
    for name, data in new_data.items():
        if name in old_data:
            old_price = old_data[name].get('effective_price')
            new_price = data.get('effective_price')
            
            # Use a small epsilon for float comparison or just strict inequality
            if old_price is not None and new_price is not None:
                if old_price != new_price:
                    diff = new_price - old_price
                    direction = "📈 UP" if diff > 0 else "📉 DOWN"
                    changes.append(f"{direction}: {name} changed from ${old_price} to ${new_price}")

    return changes

def send_email(changes):
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("⚠️ Email credentials missing. Skipping email.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = f"Badminton Price Alert - {datetime.now().strftime('%Y-%m-%d')}"

    body = "The following changes were detected in shuttlecock prices:\n\n" + "\n".join(changes)
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, text)
        server.quit()
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def main():
    print("--- Starting Scraper ---")
    current_data = fetch_current_data()
    previous_data = load_previous_data()
    
    if not current_data:
        print("No data fetched. Aborting.")
        return

    changes = compare_data(previous_data, current_data)

    if changes:
        print(f"Found {len(changes)} changes.")
        for change in changes:
            print(change)
        
        # Send Email
        send_email(changes)
        
        # Save new data ONLY if there were changes (to update the baseline)
        with open(DATA_FILE, 'w') as f:
            json.dump(current_data, f, indent=4)
        print("Updated database file.")
    else:
        print("No changes detected.")

if __name__ == "__main__":
    main()
