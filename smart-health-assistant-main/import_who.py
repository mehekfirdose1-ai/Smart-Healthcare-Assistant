import os
import time
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("WHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHO_CLIENT_SECRET")

DB_NAME = "healthcare.db"
MAX_RECORDS = 1000

SEARCH_TERMS = [
    "disease", "infection", "fever", "diabetes",
    "heart disease", "cancer", "asthma", "allergy",
    "headache", "migraine", "anemia", "arthritis",
    "kidney disease", "liver disease", "skin disease",
    "eye disease", "ear disease", "lung disease",
    "digestive disorder", "mental disorder",
    "neurological disorder", "blood disorder",
    "pregnancy", "injury", "respiratory disease",
    "viral infection", "bacterial infection",
    "bone disease", "muscle disease", "stomach disorder"
]


def get_token():
    response = requests.post(
        "https://icdaccessmanagement.who.int/connect/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={
            "grant_type": "client_credentials",
            "scope": "icdapi_access"
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()["access_token"]


def create_table():
    connection = sqlite3.connect(DB_NAME)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            who_uri TEXT UNIQUE,
            who_code TEXT,
            name TEXT NOT NULL,
            category TEXT,
            symptoms TEXT,
            precautions TEXT,
            source TEXT,
            verified INTEGER DEFAULT 0
        )
    """)

    connection.commit()
    connection.close()


def import_conditions():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("WHO credentials are missing from .env")
        return

    token = get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "API-Version": "v2",
        "Accept": "application/json",
        "Accept-Language": "en"
    }

    connection = sqlite3.connect(DB_NAME)
    imported = 0

    for term in SEARCH_TERMS:
        if imported >= MAX_RECORDS:
            break

        url = "https://id.who.int/icd/entity/search"

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"q": term},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            print("WHO response:", data)

            print("\nHTTP Status:", response.status_code)
            print("Response keys:", list(data.keys()))
            print("First result:", data.get("destinationEntities", [])[:1])

            results = data.get("destinationEntities", [])
            print("Number of results:", len(results))
            print("First entity:", results[0] if results else "No results")

            if data.get("error"):
               print("WHO API error:", data.get("errorMessage"))

            for item in results:
                if imported >= MAX_RECORDS:
                    break

                name = item.get("title")
                uri = item.get("id")
                code = item.get("theCode")

                if not name or not uri:
                    continue

                code = item.get("theCode")

                connection.execute("""
                    INSERT OR IGNORE INTO conditions
                    (who_uri, who_code, name, category,
                     symptoms, precautions, source, verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    uri,
                    code,
                    name,
                    "WHO ICD-11",
                    None,
                    None,
                    "https://icd.who.int/"
                ))

                if connection.execute(
                    "SELECT changes()"
                ).fetchone()[0]:
                    imported += 1

            connection.commit()
            print(f"Completed search: {term}")

            time.sleep(0.2)

        except requests.RequestException as error:
            print(f"Search failed for {term}: {error}")

    connection.close()
    print(f"Imported {imported} new WHO records.")
    print("Run more search terms if you need additional records.")


if __name__ == "__main__":
    create_table()
    import_conditions()