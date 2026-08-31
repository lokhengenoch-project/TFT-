import argparse
import csv
import json
import os
import sys


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INPUT_DIR = r"C:\Users\enoch\OneDrive\文件\Github\Input"
DEFAULT_OUTPUT_FILE = r"C:\Users\enoch\OneDrive\文件\Github\Output\merged_output.csv"

RARITY_TO_COST = {
    0: 1,
    1: 2,
    2: 3,
    4: 4,
    6: 5,
}

TIER_MULTIPLIER = {
    1: 1,
    2: 3,
    3: 9,
    4: 27,
}

TIER_PREFIX = {
    1: "1★",
    2: "2★",
    3: "3★",
    4: "4★",
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def first_value(*values):
    """Return the first value that is neither None nor an empty string."""
    for value in values:
        if value not in (None, ""):
            return value
    return None


def safe_int(value, default=None):
    """Safely convert a value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------

def load_participants_from_file(path):
    """Load participants, match ID, and game version from a Riot JSON file."""
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


# ---------------------------------------------------------------------------
# Board value
# ---------------------------------------------------------------------------

def calculate_board_value(participant):
    """Calculate the total board value for a participant."""
    total = 0

    for unit in participant.get("units", []) or []:
        if not isinstance(unit, dict):
            continue

        rarity = unit.get("rarity")
        value = RARITY_TO_COST.get(rarity)

        if value is None:
            continue

        tier = safe_int(unit.get("tier", 0), default=0)
        multiplier = TIER_MULTIPLIER.get(tier, 0)

        if multiplier == 0:
            continue

        total += value * multiplier

    return total


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def get_comps(participant):
    """
    Return the notable units in the participant's composition.

    Units are included when:
    - They have exactly 3 items.
    - They are either:
        * 3★ units, regardless of cost, or
        * 4/5-cost units at any tier.
    """
    comps = []

    for unit in participant.get("units", []) or []:
        if not isinstance(unit, dict):
            continue

        items = unit.get("itemNames") or []

        if not isinstance(items, list) or len(items) != 3:
            continue

        rarity = safe_int(unit.get("rarity"))
        tier = safe_int(unit.get("tier"))

        if rarity is None or tier is None:
            continue

        if rarity < 3 and tier < 3:
            continue

        character_name = unit.get("character_id")

        if character_name is None:
            continue

        character_name = str(character_name)

        if character_name.startswith("DA_18_"):
            character_name = character_name[len("DA_18_"):]

        elif character_name.startswith("DA_") and character_name.endswith("18"): 
            character_name = character_name[len("DA_"):-2]

        tier_prefix = TIER_PREFIX.get(tier, "")

        comps.append(f"{tier_prefix}{character_name}")

    return ", ".join(comps) if comps else None


# ---------------------------------------------------------------------------
# Active traits
# ---------------------------------------------------------------------------

def get_active_traits(participant):
    """Return all currently active traits."""
    active_traits = []

    for trait in participant.get("traits", []) or []:
        if not isinstance(trait, dict):
            continue

        tier_current = safe_int(trait.get("tier_current", 0), default=0)

        if tier_current <= 0:
            continue

        name = trait.get("name")

        if name is None:
            continue

        name = str(name)

        if name.startswith("DA_18_"):
            name = name[len("DA_18_"):]

        active_traits.append((name, tier_current))

    if not active_traits:
        return None

    # Preserve original sorting logic:
    # - Normal traits first
    # - Unique traits last
    # - Higher tiers first within each group
    active_traits.sort(
        key=lambda x: (
            x[0].lower().endswith("uniquetrait"),
            -x[1],
        )
    )

    return ", ".join(name for name, _ in active_traits)


# ---------------------------------------------------------------------------
# Playstyle
# ---------------------------------------------------------------------------

def get_playstyle(participant):
    """
    Determine the participant's playstyle using the following priority order:

    1. Flex
       - 3★ 4/5-cost unit
       OR
       - any 3★ unit + Fast 8
       OR
       - any 3★ unit + Fast 9

    2. Fast 9
       - Level 9+
       - 3+ five-cost units
       - 2+ 2★ five-cost units

    3. Fast 8
       - Level 8+
       - 3+ four-cost units
       - 2+ 2★ four-cost units

    4. 3-cost Reroll
       - 3+ 3★ three-cost units

    5. 2-cost Reroll
       - 3+ 3★ units costing 1 or 2

    6. 1-cost Reroll
       - 2+ 3★ one-cost units

    7. Didn't Hit
       - No 3★ units
       - No 2★ 4-cost units
       - No 2★ 5-cost units

    The first matching rule wins.
    """

    level = safe_int(participant.get("level", 0), default=0)
    units = participant.get("units", []) or []

    # -----------------------------------------------------------------------
    # Counters
    # -----------------------------------------------------------------------

    three_star_by_cost = {
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 0,
    }

    four_cost_units = 0
    five_cost_units = 0

    two_star_four_cost_units = 0
    two_star_five_cost_units = 0

    any_three_star = False
    three_star_high_cost = False

    # -----------------------------------------------------------------------
    # Inspect units
    # -----------------------------------------------------------------------

    for unit in units:
        if not isinstance(unit, dict):
            continue

        tier = safe_int(unit.get("tier", 0), default=0)
        rarity = unit.get("rarity")

        if rarity is None:
            continue

        cost = RARITY_TO_COST.get(rarity)

        if cost is None:
            continue

        # 3★ units
        if tier == 3:
            any_three_star = True

            if cost in three_star_by_cost:
                three_star_by_cost[cost] += 1

            # 3★ 4-cost or 5-cost
            if cost >= 4:
                three_star_high_cost = True

        # 4-cost units
        if cost == 4:
            four_cost_units += 1

            if tier == 2:
                two_star_four_cost_units += 1

        # 5-cost units
        if cost == 5:
            five_cost_units += 1

            if tier == 2:
                two_star_five_cost_units += 1

    # -----------------------------------------------------------------------
    # Calculate Fast 9
    # -----------------------------------------------------------------------

    fast_9 = (
        level >= 9
        and five_cost_units >= 3
        and two_star_five_cost_units >= 2
    )

    # -----------------------------------------------------------------------
    # Calculate Fast 8
    # -----------------------------------------------------------------------

    fast_8 = (
        level >= 8
        and four_cost_units >= 3
        and two_star_four_cost_units >= 2
    )

    # -----------------------------------------------------------------------
    # 1. FLEX
    # -----------------------------------------------------------------------

    # Flex if:
    # - There is a 3★ 4/5-cost unit
    # OR
    # - There is any 3★ unit and the board qualifies as Fast 8
    # OR
    # - There is any 3★ unit and the board qualifies as Fast 9
    if (
        three_star_high_cost
        or (any_three_star and fast_8)
        or (any_three_star and fast_9)
    ):
        return "Flex"

    # -----------------------------------------------------------------------
    # 2. FAST 9
    # -----------------------------------------------------------------------

    if fast_9:
        return "Fast 9"

    # -----------------------------------------------------------------------
    # 3. FAST 8
    # -----------------------------------------------------------------------

    if fast_8:
        return "Fast 8"

    # -----------------------------------------------------------------------
    # 4. 3-COST REROLL
    # -----------------------------------------------------------------------

    if three_star_by_cost[3] >= 3:
        return "3-cost Reroll"

    # -----------------------------------------------------------------------
    # 6. 1-COST REROLL
    # -----------------------------------------------------------------------

    if three_star_by_cost[1] >= 2:
        return "1-cost Reroll"

    # -----------------------------------------------------------------------
    # 5. 2-COST REROLL
    # -----------------------------------------------------------------------

    # 3+ total 3★ units costing either 1 or 2.
    if (
        three_star_by_cost[1]
        + three_star_by_cost[2]
        >= 3
    ):
        return "2-cost Reroll"

    
    # -----------------------------------------------------------------------
    # 7. DIDN'T HIT
    # -----------------------------------------------------------------------

    # No 3★ units
    # AND no 2★ 4-cost units
    # AND no 2★ 5-cost units.
    if (
        not any_three_star
        and two_star_four_cost_units == 0
        and two_star_five_cost_units == 0
    ):
        return "Didn't Hit"

    # -----------------------------------------------------------------------
    # Anything not matching the defined categories is Flex?
    # -----------------------------------------------------------------------



# ---------------------------------------------------------------------------
# CSV row creation
# ---------------------------------------------------------------------------

def participant_to_row(participant, match_id, game_version, row_id):
    """Convert a participant object into a CSV-compatible dictionary."""
    row = {
        "ID": row_id,
        "match_id": match_id,
        "game_version": game_version,
    }

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


# ---------------------------------------------------------------------------
# Input resolution
# ---------------------------------------------------------------------------

def resolve_inputs(inputs):
    """
    Expand directory inputs into JSON files.

    Directory scanning is non-recursive and sorted for deterministic output.
    """
    resolved_inputs = []

    for input_path in inputs:
        if os.path.isdir(input_path):
            found = sorted(
                os.path.join(input_path, filename)
                for filename in os.listdir(input_path)
                if filename.lower().endswith(".json")
            )

            if not found:
                print(
                    f"No JSON files found in directory: {input_path}",
                    file=sys.stderr,
                )
            else:
                resolved_inputs.extend(found)

        else:
            resolved_inputs.append(input_path)

    return resolved_inputs


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------

def get_fieldnames(rows):
    """
    Preserve field order based on the first occurrence of each field.
    """
    fieldnames = []
    seen = set()

    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    return fieldnames


def write_csv(output_path, rows):
    """Write participant rows to the output CSV."""
    output_dir = os.path.dirname(output_path)

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    fieldnames = get_fieldnames(rows)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Merge participants from multiple Riot JSON files into one CSV."
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        default=[DEFAULT_INPUT_DIR],
        help="Input JSON files or directories to process "
             "(defaults to the input folder).",
    )

    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Output CSV file path.",
    )

    args = parser.parse_args()

    resolved_inputs = resolve_inputs(args.inputs)

    rows = []
    row_id = 1

    for input_path in resolved_inputs:
        if not os.path.isfile(input_path):
            print(
                f"Skipping missing file: {input_path}",
                file=sys.stderr,
            )
            continue

        try:
            participants, match_id, game_version = (
                load_participants_from_file(input_path)
            )
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"Skipping invalid/unreadable file {input_path}: {exc}",
                file=sys.stderr,
            )
            continue

        if not participants:
            print(
                f"No participants found in {input_path}",
                file=sys.stderr,
            )
            continue

        for participant in participants:
            rows.append(
                participant_to_row(
                    participant,
                    match_id,
                    game_version,
                    row_id,
                )
            )
            row_id += 1

    if not rows:
        raise ValueError(
            "No participants were found in the provided JSON files."
        )

    write_csv(args.output, rows)

    print(f"CSV created successfully: {args.output}")


if __name__ == "__main__":
    main()

