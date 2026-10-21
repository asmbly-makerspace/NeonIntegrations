"""Print the seed value for the /neon/class_fields SSM parameter.

SEED is the class-to-field table that was hard-coded as EVENT_FIELDS in
attendanceToTestout.py before it moved to SSM, in the same order. It is
only used to create the parameter the first time; after that the parameter
is the source of truth, so change it there, not here.

    python scripts/class_fields_seed.py > class_fields.json
"""

import json
import os
import sys

SEED = [
    ["Festool Domino", "440"],
    ["Shaper Origin", "274"],
    ["Woodshop Safety", "84"],
    ["Metal Shop Safety", "520"],
    ["Big Lasers", "86"],
    ["CNC Router", "435"],
    ["Stationary Sanders", "675"],
    ["Metal Lathe", "676"],
    ["Wood Lathe", "677"],
    ["MIG Welding", "678"],
    ["TIG Welding", "679"],
    ["Small Lasers", "680"],
    ["Laser Engrave Round", "1007"],
    ["Milling", "681"],
    ["Tormach", "682"],
    ["Filament", "683"],
    ["Resin", "684"],
    ["Sublimation", "685"],
    ["Vinyl", "686"],
    ["Orientation", "182"],
    ["CSI", "1248"],  # Ceramics Safety and Information
]


def seedJson(fields=SEED) -> str:
    """The parameter value, one entry per line so SSM history diffs read well."""
    lines = ",\n".join(f"    {json.dumps(entry)}" for entry in fields)
    return f'{{\n  "version": 1,\n  "fields": [\n{lines}\n  ]\n}}\n'


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from helpers.class_fields import parseClassFields

    value = seedJson()
    parseClassFields(value)  # never print a value the sync would reject
    sys.stdout.write(value)
