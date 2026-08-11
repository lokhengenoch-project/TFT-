import argparse
import json
import csv
import os
import sys


def load_participants_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("info", {}).get("participants", [])


def participant_to_row(participant):
    row = {}
    for key, value in participant.items():
        if isinstance(value, (dict, list)):
            row[key] = json.dumps(value, ensure_ascii=False)
        else:
            row[key] = value
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
    for input_path in resolved_inputs:
        if not os.path.isfile(input_path):
            print(f"Skipping missing file: {input_path}", file=sys.stderr)
            continue
        participants = load_participants_from_file(input_path)
        if not participants:
            print(f"No participants found in {input_path}", file=sys.stderr)
            continue
        for participant in participants:
            rows.append(participant_to_row(participant))

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