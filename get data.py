import os
import json
import requests

API_KEY = "RGAPI-e4dc02b2-fb2a-4aca-b67d-c7b042087d16"
DEFAULT_REGION = "americas"

# Define players as dictionaries to support individual region or URL overrides
PLAYERS = [
    {
        "puuid": "QuIlIIx00VaUyVkKvIYZEfo-stN4mIR0RbseUOfDLZBnOa4oPiIPHjv3HeP9s6mhL7W0oVF13IVVbA",
        "region": "americas"  # Standard player
    },
    {
        "puuid": "VYoFnMTz8F4nsYzGSp_2sznxjvCA5evHVKHg1GuAlNCeCixDDe-F4Mp2SIu6P1iS9zmZtLOM9o4kqA",
        "region": "europe"    # Example: Different region cluster (americas, europe, asia, esports)
    },
    {
        "puuid": "6ZqIODsRnX_FC6zuP8UFcARYR24ng92OnPqDfqATZJ3-j_udys3frmnj_8SkEdxXFWE2k74TFlppcg",
        "region": "americas"
    },
    {
        "puuid": "x_orLRHgMlINEB_kyHE8rJ-OvBeDQin2Wxr9Dnf78G1KPWMmcv0oaXkM_Kqt9iLYWTZLZWNgmorLjw",
        "region": "americas"
    }
]

OUTPUT_DIR = r"C:\Users\enoch\OneDrive\文件\GIthub\Input"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Store match IDs alongside their corresponding region to ensure details are fetched from the correct endpoint
# Dictionary mapping: match_id -> region
matches_to_fetch = {}

# 1. Gather match IDs for each player configuration
for player in PLAYERS:
    puuid = player["puuid"]
    region = player.get("region", DEFAULT_REGION)
    
    # Construct the appropriate URL
    if "custom_ids_url" in player:
        ids_url = player["custom_ids_url"].format(puuid=puuid)
        if "api_key=" not in ids_url:
            ids_url += f"&api_key={API_KEY}" if "?" in ids_url else f"?api_key={API_KEY}"
    else:
        ids_url = f"https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?count=5&api_key={API_KEY}"

    print(f"Fetching match IDs for PUUID: {puuid[:10]}... (Region: {region})")
    response = requests.get(ids_url)
    
    if response.status_code == 200:
        match_ids = response.json()
        if isinstance(match_ids, list):
            for m_id in match_ids:
                matches_to_fetch[m_id] = region
    else:
        print(f"  ❌ Failed to fetch matches for {puuid[:10]} (Status Code: {response.status_code})")

print(f"\nTotal unique matches queued: {len(matches_to_fetch)}\n")

# 2. Download and save each match JSON file
for index, (match_id, region) in enumerate(matches_to_fetch.items(), start=1):
    file_path = os.path.join(OUTPUT_DIR, f"{match_id}.json")
    
    # Skip downloading if file already exists
    if os.path.exists(file_path):
        print(f"[{index}/{len(matches_to_fetch)}] Already exists, skipping: {match_id}")
        continue

    # Use the player's region cluster (e.g., americas, europe, asia) for fetching match details
    match_detail_url = f"https://{region}.api.riotgames.com/tft/match/v1/matches/{match_id}?api_key={API_KEY}"
    response = requests.get(match_detail_url)
    
    if response.status_code == 200:
        match_data = response.json()
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(match_data, file, indent=4)
        print(f"[{index}/{len(matches_to_fetch)}] Saved: {file_path}")
    else:
        print(f"[{index}/{len(matches_to_fetch)}] Failed to download {match_id} (Status Code: {response.status_code})")