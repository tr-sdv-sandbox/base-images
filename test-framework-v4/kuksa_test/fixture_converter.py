"""
Convert YAML test fixtures to JSON format for C++ fixture runner.
"""

import json
from typing import List, Dict, Any
from .models import Fixture


def fixtures_to_json(fixtures: List[Fixture]) -> str:
    """Convert fixtures to JSON format for C++ runner"""
    fixture_list = []

    for fixture in fixtures:
        fixture_dict = {
            "name": fixture.name,
            "type": fixture.type.value,
        }
        # Merge config into the dict
        fixture_dict.update(fixture.config)
        fixture_list.append(fixture_dict)

    return json.dumps({"fixtures": fixture_list}, indent=2)


def save_fixtures_json(fixtures: List[Fixture], filepath: str):
    """Save fixtures to JSON file"""
    with open(filepath, 'w') as f:
        f.write(fixtures_to_json(fixtures))
