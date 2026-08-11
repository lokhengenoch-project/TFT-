import argparse
import json
import csv
import os
import sys


def load_participants_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    participants = data.get("info", {}).get("participants", [])
    if not participants:
        participants = data.get("participants", [])

    match_id = (
        data.get("metadata", {}).get("matchId")
        or data.get("info", {}).get("matchId")
        or data.get("matchId")
        or data.get("gameId")
        or data.get("metadata", {}).get("gameId")
        or os.path.splitext(os.path.basename(path))[0]
    )

    return participants, str(match_id)


def calculate_board_value(participant):
    rarity_value = {0: 1, 1: 2, 2: 3, 4: 4, 6: 5}
    tier_multiplier = {1: 1, 2: 3, 3: 9}
    total = 0
    for unit in participant.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        rarity = unit.get("rarity")
        tier = unit.get("tier", 0) or 0
        value = rarity_value.get(rarity)
        multiplier = tier_multiplier.get(int(tier), 0)
        if value is None or multiplier == 0:
            continue
        try:
            total += int(value) * multiplier
        except (TypeError, ValueError):
            continue
    return total


def participant_to_row(participant, match_id, row_id):
    row = {"ID": row_id, "match_id": match_id}
    for key, value in participant.items():
        if isinstance(value, (dict, list)):
            row[key] = json.dumps(value, ensure_ascii=False)
        else:
            row[key] = value
    row["board value"] = calculate_board_value(participant)
    return row


def main():
    parser = argparse.ArgumentParser(
        description="Merge participants from multiple Riot JSON files into one CSV"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input JSON files (provide up to 10 files).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=r"C:\Users\enoch\OneDrive\文件\GIthub\Output\merged_output.csv",
        help="Output CSV file path",
    )

    args = parser.parse_args()

    # Ensure the configured output directory exists
    output_path = args.output
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    inputs = args.inputs

    # Expand directory inputs: if any provided input is a directory, collect .json files from it
    resolved_inputs = []
    for input_path in inputs:
        if os.path.isdir(input_path):
            # collect json files in this directory (non-recursive), sorted for determinism
            found = sorted(
                [os.path.join(input_path, fn) for fn in os.listdir(input_path) if fn.lower().endswith(".json")]
            )
            if not found:
                print(f"No JSON files found in directory: {input_path}", file=sys.stderr)
            else:
                resolved_inputs.extend(found)
        else:
            resolved_inputs.append(input_path)

    # Enforce max 10 input files
    if len(resolved_inputs) > 10:
        print("More than 10 input files found; only the first 10 will be used.")
        resolved_inputs = resolved_inputs[:10]

    rows = []
    row_id = 1
    for input_path in resolved_inputs:
        if not os.path.isfile(input_path):
            print(f"Skipping missing file: {input_path}", file=sys.stderr)
            continue

        participants, match_id = load_participants_from_file(input_path)
        if not participants:
            print(f"No participants found in {input_path}", file=sys.stderr)
            continue
        for participant in participants:
            rows.append(participant_to_row(participant, match_id, row_id))
            row_id += 1

    if not rows:
        raise ValueError("No participants were found in the provided JSON files.")

    # Preserve field order discovered across rows
    fieldnames = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV created successfully: {output_path}")


if __name__ == "__main__":
    main()