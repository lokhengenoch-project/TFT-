import argparse
import json
import csv
import os
import sys


def first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def load_participants_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    participants = data.get("info", {}).get("participants", [])
    if not participants:
        participants = data.get("participants", [])

    match_id = first_value(
        data.get("metadata", {}).get("matchId"),
        data.get("info", {}).get("matchId"),
        data.get("matchId"),
        data.get("gameId"),
        data.get("metadata", {}).get("gameId"),
        os.path.splitext(os.path.basename(path))[0],
    )

    game_version = first_value(
        data.get("info", {}).get("game_version"),
        data.get("metadata", {}).get("game_version"),
        data.get("game_version"),
        data.get("info", {}).get("gameVersion"),
        data.get("metadata", {}).get("gameVersion"),
        data.get("gameVersion"),
    )

    return participants, str(match_id), game_version


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


def get_comps(participant):
    comps = []

    for unit in participant.get("units", []) or []:
        if not isinstance(unit, dict):
            continue

        items = unit.get("itemNames") or []
        if not isinstance(items, list) or len(items) != 3:
            continue

        if "TFT_Item_ThiefsGloves" in items:
            continue

        rarity = unit.get("rarity")
        tier = unit.get("tier")

        try:
            rarity_val = int(rarity)
        except (TypeError, ValueError):
            rarity_val = None

        try:
            tier_val = int(tier)
        except (TypeError, ValueError):
            tier_val = None

        if rarity_val is not None and tier_val is not None:
            if rarity_val < 3 and tier_val < 3:
                continue

        character_name = unit.get("character_id")
        if character_name is None:
            continue

        character_name = str(character_name)

        if character_name.startswith("TFT17_"):
            character_name = character_name[len("TFT17_"):]

        tier_prefix = {
            1: "1★",
            2: "2★",
            3: "3★",
            4: "4★",
        }.get(tier_val, "")

        comps.append(f"{tier_prefix}{character_name}")

    return ", ".join(comps) if comps else None


def get_active_traits(participant):
    active_traits = []

    for trait in participant.get("traits", []) or []:
        if not isinstance(trait, dict):
            continue

        try:
            tier_current = int(trait.get("tier_current", 0) or 0)
        except (TypeError, ValueError):
            continue

        if tier_current <= 0:
            continue

        name = trait.get("name")
        if name is None:
            continue

        name = str(name)
        if name.startswith("TFT17_"):
            name = name[len("TFT17_"):]

        active_traits.append((name, tier_current))

    if not active_traits:
        return None

    active_traits.sort(
        key=lambda x: (
            x[0].lower().endswith("uniquetrait"),
            -x[1]
        )
    )

    return ", ".join(name for name, _ in active_traits)


def get_playstyle(participant):
    level = participant.get("level", 0)
    units = participant.get("units", []) or []
    
    # Rarity to cost mapping (from rarity_value in calculate_board_value)
    rarity_to_cost = {0: 1, 1: 2, 2: 3, 4: 4, 6: 5}
    
    # Count different types of units
    three_star_low_cost = 0  # 3★ units with cost ≤ 3
    four_cost_units = 0
    five_cost_units = 0
    any_three_star = False
    two_star_four_five_cost = 0  # 2★ units with cost 4 or 5
    two_star_five_cost = 0  # 2★ units with cost 5
    
    for unit in units:
        if not isinstance(unit, dict):
            continue
        
        try:
            tier = int(unit.get("tier", 0) or 0)
            rarity = unit.get("rarity")
            if rarity is None:
                continue
            cost = rarity_to_cost.get(rarity)
            if cost is None:
                continue
        except (TypeError, ValueError):
            continue
        
        # Check for 3★ units
        if tier == 3:
            any_three_star = True
            if cost <= 3:
                three_star_low_cost += 1
        
        # Check for 4-cost units
        if cost == 4:
            four_cost_units += 1
        
        # Check for 5-cost units
        if cost == 5:
            five_cost_units += 1
        
        # Check for 2★ 4-cost or 5-cost units
        if tier == 2 and cost >= 4:
            two_star_four_five_cost += 1
        
        # Check for 2★ 5-cost units
        if tier == 2 and cost == 5:
            two_star_five_cost += 1
    
    # Apply the playstyle logic
    playstyles = []
    
    if three_star_low_cost >= 2:
        playstyles.append("Reroll")
    
    if level >= 8 and four_cost_units >= 2:
        playstyles.append("Fast 8")
    
    if level >= 9 and two_star_five_cost >= 2:
        playstyles.append("Fast 9")
    
    if not any_three_star and two_star_four_five_cost == 0:
        playstyles.append("Didn't Hit")
    
    # Flex logic: anything that doesn't fit above OR fits into more than 1 group
    if len(playstyles) == 0:
        return "Flex"
    elif len(playstyles) > 1:
        return "Flex"
    else:
        return playstyles[0]


def participant_to_row(participant, match_id, game_version, row_id):
    row = {"ID": row_id, "match_id": match_id, "game_version": game_version}
    for key, value in participant.items():
        if isinstance(value, (dict, list)):
            row[key] = json.dumps(value, ensure_ascii=False)
        else:
            row[key] = value
    row["board value"] = calculate_board_value(participant)
    row["comp"] = get_comps(participant)
    row["Active Traits"] = get_active_traits(participant)
    row["playstyle"] = get_playstyle(participant)
    return row


def main():
    default_input_dir = r"C:\Users\enoch\OneDrive\文件\GIthub\Input"
    default_output_file = r"C:\Users\enoch\OneDrive\文件\GIthub\Output\merged_output.csv"

    parser = argparse.ArgumentParser(
        description="Merge participants from multiple Riot JSON files into one CSV"
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        default=[default_input_dir],
        help="Input JSON files or directories to process (defaults to the input folder).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=default_output_file,
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

    rows = []
    row_id = 1
    for input_path in resolved_inputs:
        if not os.path.isfile(input_path):
            print(f"Skipping missing file: {input_path}", file=sys.stderr)
            continue

        participants, match_id, game_version = load_participants_from_file(input_path)
        if not participants:
            print(f"No participants found in {input_path}", file=sys.stderr)
            continue
        for participant in participants:
            rows.append(participant_to_row(participant, match_id, game_version, row_id))
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