import os
import json
import random
import re
import time
from bs4 import BeautifulSoup

# Import Selenium components
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

DATA_FILE = "data/results.json"

def fetch_latest_results():
    """Launches a headless browser to execute JavaScript and extract SVG numbers."""
    url = "https://bet.hkjc.com/ch/marksix/results"
    
    # Configure Chrome options for a headless cloud environment
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Run without a visual UI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        # Initialize the headless browser
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Crucial: Give the page's JavaScript 5 seconds to run, fetch APIs, and render components
        time.sleep(5)
        
        # Extract the fully rendered page source
        html_source = driver.page_source
        soup = BeautifulSoup(html_source, "html.parser")
        print(soup)
        draws = []
        
        # Scan for elements containing images now that JavaScript has run
        rows = soup.find_all("tr") or soup.find_all("div", class_="result_row")
        print(rows)
        
        for row in rows:
            images = row.find_all("img")
            ball_numbers = []
            
            for img in images:
                src = img.get("src", "")
                # Handles the marksix-5.689d21b5...svg pattern
                match = re.search(r'marksix-(\d{1,2})', src.lower())
                if match:
                    ball_numbers.append(int(match.group(1)))
            
            if len(ball_numbers) >= 7:
                row_text = row.get_text()
                id_match = re.search(r'\d{2}/\d{3}', row_text)
                draw_id = id_match.group(0) if id_match else "Unknown"
                
                draws.append({
                    "id": draw_id,
                    "numbers": ball_numbers[:6],
                    "special": ball_numbers[6]
                })
                
        if draws:
            print(f"Successfully rendered JavaScript and decoded {len(draws)} draws.")
            return {"draws": draws}
            
        print("Browser loaded the frame but couldn't locate ball targets.")
        return None

    except Exception as e:
        print(f"Headless browser error: {e}")
        return None
    finally:
        if driver:
            driver.quit() # Always close the browser process

def generate_numbers(history):
    pool = []
    for draw in history.get("draws", []):
        pool.extend(draw.get("numbers", []))
    if len(set(pool)) < 6:
        pool = list(range(1, 50))
    generated_set = sorted(random.sample(list(set(pool)), 6))
    special_number = random.choice([n for n in range(1, 50) if n not in generated_set])
    return {"numbers": generated_set, "special": special_number}

def main():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try: store = json.load(f)
            except: store = {"history": [], "prediction": {}}
    else:
        store = {"history": [], "prediction": {}}

    raw_data = fetch_latest_results()
    
    if raw_data:
        store["history"] = raw_data["draws"]
        store["prediction"] = generate_numbers(raw_data)
    else:
        # Graceful fallback pool to keep frontend running smoothly if network is unstable
        fallback = {"draws": [{"id": "26/071", "numbers": [8, 11, 19, 22, 39, 45], "special": 23}]}
        store["history"] = fallback["draws"]
        store["prediction"] = generate_numbers(fallback)

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(store, f, indent=2)

if __name__ == "__main__":
    main()
