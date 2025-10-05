#!/usr/bin/env python3
"""Merge VSS base spec with extensions"""
import json
import sys
from pathlib import Path

def merge_vss(base_file, extensions_file, output_file):
    """Merge base VSS spec with extensions"""
    # Load base VSS
    with open(base_file) as f:
        base = json.load(f)
    
    # Load extensions
    with open(extensions_file) as f:
        extensions = json.load(f)
    
    # Deep merge function
    def deep_merge(base_dict, overlay_dict):
        result = base_dict.copy()
        for key, value in overlay_dict.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    if 'children' in result[key] and 'children' in value:
                        # Merge children
                        result[key]['children'] = deep_merge(
                            result[key].get('children', {}),
                            value.get('children', {})
                        )
                    else:
                        result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            else:
                # New key from overlay
                result[key] = value
        return result
    
    # Merge
    merged = deep_merge(base, extensions)
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)
    
    print(f"Merged VSS spec written to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: merge-vss-extensions.py <base_vss.json> <extensions.json> <output.json>")
        sys.exit(1)
    
    merge_vss(sys.argv[1], sys.argv[2], sys.argv[3])
