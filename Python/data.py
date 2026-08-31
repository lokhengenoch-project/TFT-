import os
import json
import time
import requests

API_KEY = "RGAPI-fd629fa2-a986-4e4a-8f1c-314b3bfb4b46"
DEFAULT_REGION = "americas"

PLAYERS = [
    {
        "puuid": "QuIlIIx00VaUyVkKvIYZEfo-stN4mIR0RbseUOfDLZBnOa4oPiIPHjv3HeP9s6mhL7W0oVF13IVVbA",
        "region": "americas"
    },
    {
        "puuid": "VYoFnMTz8F4nsYzGSp_2sznxjvCA5evHVKHg1GuAlNCeCixDDe-F4Mp2SIu6P1iS9zmZtLOM9o4kqA",
        "region": "europe"
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

# Dictionary mapping match_id -> region
matches_to_fetch = {}

# ---------------------------------------------------------
# 1. Gather match IDs
# ---------------------------------------------------------

for player in PLAYERS:
    puuid = player["puuid"]
    region = player.get("region", DEFAULT_REGION)

    if "custom_ids_url" in player:
        ids_url = player["custom_ids_url"].format(puuid=puuid)

        if "api_key=" not in ids_url:
            separator = "&" if "?" in ids_url else "?"
            ids_url += f"{separator}api_key={API_KEY}"

    else:
        ids_url = (
            f"https://{region}.api.riotgames.com/"
            f"tft/match/v1/matches/by-puuid/{puuid}/ids"
            f"?count=10&api_key={API_KEY}"
        )

    print(
        f"Fetching match IDs for PUUID: "
        f"{puuid[:10]}... (Region: {region})"
    )

    try:
        response = requests.get(ids_url, timeout=30)

        if response.status_code == 200:
            match_ids = response.json()

            if isinstance(match_ids, list):
                for match_id in match_ids:
                    matches_to_fetch.setdefault(match_id, region)

        elif response.status_code == 429:
            print("  ⚠️ Rate limited by Riot API.")

        else:
            print(
                f"  ❌ Failed to fetch matches for "
                f"{puuid[:10]} "
                f"(Status Code: {response.status_code})"
            )

    except requests.RequestException as e:
        print(f"  ❌ Request failed: {e}")

print(f"\nTotal unique matches queued: {len(matches_to_fetch)}\n")


# ---------------------------------------------------------
# 2. Download match JSON
# ---------------------------------------------------------

for index, (match_id, region) in enumerate(
    matches_to_fetch.items(),
    start=1
):
    file_path = os.path.join(
        OUTPUT_DIR,
        f"{match_id}.json"
    )

    if os.path.exists(file_path):
        print(
            f"[{index}/{len(matches_to_fetch)}] "
            f"Already exists, skipping: {match_id}"
        )
        continue

    match_detail_url = (
        f"https://{region}.api.riotgames.com/"
        f"tft/match/v1/matches/{match_id}"
        f"?api_key={API_KEY}"
    )

    try:
        response = requests.get(
            match_detail_url,
            timeout=30
        )

        if response.status_code == 200:
            match_data = response.json()

            with open(
                file_path,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    match_data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            print(
                f"[{index}/{len(matches_to_fetch)}] "
                f"Saved: {file_path}"
            )

        elif response.status_code == 429:
            print(
                f"[{index}/{len(matches_to_fetch)}] "
                f"⚠️ Rate limited while downloading {match_id}"
            )

            time.sleep(10)

        else:
            print(
                f"[{index}/{len(matches_to_fetch)}] "
                f"Failed to download {match_id} "
                f"(Status Code: {response.status_code})"
            )

    except requests.RequestException as e:
        print(
            f"[{index}/{len(matches_to_fetch)}] "
            f"Request failed for {match_id}: {e}"
        )