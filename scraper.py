import os
import json
import random
import time
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta, timezone

# Set a limit on how many total historical records to keep in your database pool
MAX_HISTORY_LIMIT = 100

DATA_FILE = "data/results.json"

def parse_rows_from_soup(soup, draws_list):
    """Helper function to parse and append table rows from the current page source."""
    rows = soup.find_all("div", class_="table-row")
    for row in rows:
        id_cell = row.find("div", class_="cell-id")
        if id_cell and id_cell.find("a"):
            draw_id = id_cell.find("a").get_text(strip=True)
        else:
            continue 

        # Skip duplicates if a row appears twice during transitions
        if any(d["id"] == draw_id for d in draws_list):
            continue
            
        ball_list_cell = row.find("div", class_="cell-ball-list")
        if not ball_list_cell:
            continue
            
        images = ball_list_cell.find_all("img")
        ball_numbers = []
        for img in images:
            alt_val = img.get("alt", "")
            if alt_val.isdigit():
                ball_numbers.append(int(alt_val))
        
        if len(ball_numbers) >= 7:
            draws_list.append({
                "id": draw_id,
                "numbers": ball_numbers[:6],
                "special": ball_numbers[6]
            })

def fetch_latest_results():
    """Launches headless browser, updates to 30, and navigates across split pagination."""
    url = "https://bet.hkjc.com/ch/marksix/results"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        wait = WebDriverWait(driver, 10)
        
        # 1. Open dropdown and expand list
        dropdown_button = wait.until(EC.element_to_be_clickable(
            (By.CLASS_NAME, "draw-number-dropdown-button-title-number")
        ))
        dropdown_button.click()
        time.sleep(1)
        
        target_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//*[contains(@class, 'dropdown') or contains(@class, 'option')][text()='30' or contains(text(), '30')]")
        ))
        target_option.click()
        time.sleep(1)

        # 2. Fire Search query
        search_button = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.search-btn.cta_m6")
        ))
        search_button.click()
        print("Fired search query refresh.")
        time.sleep(4) # Let page 1 render completely
        
        draws = []
        
        # --- PAGE 1 SCRAPE ---
        soup_page1 = BeautifulSoup(driver.page_source, "html.parser")
        parse_rows_from_soup(soup_page1, draws)
        print(f"Collected {len(draws)} entries from Page 1.")

        # --- PAGINATION NAVIGATION (PAGE 2) ---
        try:
            # Look for common HKJC pagination selectors (e.g., an arrow icon or a link with text "2")
            # This handles either a literal '2' button or a 'next page' layout element
            next_page_btn = driver.find_elements(By.XPATH, "//*[contains(@class, 'page') or contains(@class, 'pagination')]//*[text()='2' or contains(@class, 'next')]")
            
            if next_page_btn and next_page_btn[0].is_displayed():
                next_page_btn[0].click()
                print("Clicked page navigation to move to Page 2.")
                time.sleep(3) # Give table content time to swap
                
                # --- PAGE 2 SCRAPE ---
                soup_page2 = BeautifulSoup(driver.page_source, "html.parser")
                parse_rows_from_soup(soup_page2, draws)
                print(f"Total entries aggregated across all pages: {len(draws)}")
            else:
                print("No active secondary page navigation found, tracking single-pane setup.")
        except Exception as nav_err:
            print(f"Pagination navigation skipped or not required: {nav_err}")

        if draws:
            return {"draws": draws}
        return None

    except Exception as e:
        print(f"Browser processing error: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# Keep your existing generate_numbers() and main() functions exactly the same below this!

def generate_numbers(history):
    """Generates standard tracking models from real historical weights."""
    pool = []
    for draw in history.get("draws", []):
        pool.extend(draw.get("numbers", []))
    if len(set(pool)) < 6:
        pool = list(range(1, 50))
    generated_set = sorted(random.sample(list(set(pool)), 6))
    special_number = random.choice([n for n in range(1, 50) if n not in generated_set])
    return {"numbers": generated_set, "special": special_number}

def main():
    # 1. Initialize data layout and load existing file if it exists
    existing_history = []
    store = {"updated_at": "", "history": []}

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try: 
                store = json.load(f)
                # Keep a copy of whatever history we already collected in past runs
                existing_history = store.get("history", [])
            except Exception as load_err: 
                print(f"Could not parse existing database file: {load_err}")

    # 2. Try to scrape the latest batch from the web
    raw_data = fetch_latest_results()
    
    hkt_now = datetime.now(timezone.utc) + timedelta(hours=8)
    hkt_str = hkt_now.strftime("%Y-%m-%d %H:%M HKT")

    if raw_data and raw_data.get("draws"):
        new_scraped_draws = raw_data["draws"]
        
        # --- SMART MERGING PROCESS ---
        # Create a dictionary of existing draws mapped by their ID to make merging easy
        merged_dict = {draw["id"]: draw for draw in existing_history}
        
        # Add or overwrite with the newly scraped draws (newest data takes precedence)
        for draw in new_scraped_draws:
            merged_dict[draw["id"]] = draw
            
        # Convert back to a list
        merged_list = list(merged_dict.values())
        
        # Sort the list by Draw ID descending so the newest draws are always at the top
        # (This matches the '26/073' formatting layout cleanly)
        merged_list.sort(key=lambda x: x["id"], reverse=True)
        
        # Optional: Cap the historical database size so it doesn't slow down the page load
        if len(merged_list) > MAX_HISTORY_LIMIT:
            print(f"Capping total stored history pool from {len(merged_list)} to {MAX_HISTORY_LIMIT} entries.")
            merged_list = merged_list[:MAX_HISTORY_LIMIT]
            
        store["history"] = merged_list
        store["updated_at"] = hkt_str
        print(f"Scraper succeeded! Database expanded. Total pool size: {len(store['history'])} draws.")
        
    else:
        # FAIL SAFE: Keep the existing history completely untouched
        print("⚠️ Scraper failed to fetch new data! Retaining the previous history and timestamp.")
        if store.get("updated_at") and "(Stale)" not in store["updated_at"]:
            store["updated_at"] = f"{store['updated_at']} (Stale)"

    # 3. Save everything back out to results.json
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    print("Data package successfully committed to disk storage.")
    


if __name__ == "__main__":
    main()
