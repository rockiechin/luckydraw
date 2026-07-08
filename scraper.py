import json
import os
import random
import requests

DATA_FILE = "data/results.json"


def fetch_latest_results():
    """Fetches recent draw history from HKJC."""
    # HKJC's web platform often utilizes a direct JSON or GraphQL structure for results
    url = "https://bet.hkjc.com/contentserver/jcbw/cmc/marksix/info/results.json"
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def generate_numbers(history):
    """Your custom logic to generate a set of numbers.

    Replace this placeholder with your own statistical analysis or rules.
    """
    # Simple example: pull all drawn numbers to check basic frequency
    pool = []
    for draw in history.get("draws", []):
        pool.extend([int(n) for n in draw.get("numbers", [])])

    # Fallback to standard 1-49 if history is empty
    if not pool:
        pool = list(range(1, 50))

    # Generate 6 random unique numbers from the pool
    generated_set = sorted(random.sample(set(pool), 6))
    special_number = random.choice([n for n in range(1, 50) if n not in generated_set])

    return {"numbers": generated_set, "special": special_number}


def main():
    # 1. Load existing data if available
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            store = json.load(f)
    else:
        store = {"history": [], "generated": []}

    # 2. Fetch fresh data
    raw_data = fetch_latest_results()

    if raw_data:
        # Format and append/update your history here based on HKJC's payload
        store["history"] = raw_data

        # 3. Generate new sets based on the updated history
        store["prediction"] = generate_numbers(raw_data)

        # 4. Save back to the repository
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(store, f, indent=2)
        print("Data successfully updated.")


if __name__ == "__main__":
    main()
