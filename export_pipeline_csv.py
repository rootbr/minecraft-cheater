#!/usr/bin/env python3
"""
Export full pipeline: GrabCraft → Bedrock → Optimized → Expanded
All stages in one CSV sorted by coordinates.
"""

import csv
import re
import sys
from collections import defaultdict

# Import our modules
from grabcraft_to_commands import extract_blocks_from_web, get_block_id
from grabcraft_to_bedrock import get_converter
from optimize_commands import read_commands, optimize_grid


def expand_fill_command(line: str) -> list[tuple]:
    """Expand /fill command to list of (x, y, z, block) tuples."""
    match = re.match(
        r'/fill\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$',
        line
    )
    if match:
        x1, y1, z1 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        x2, y2, z2 = int(match.group(4)), int(match.group(5)), int(match.group(6))
        block = match.group(7)

        blocks = []
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    blocks.append((x, y, z, block))
        return blocks
    return []


def expand_setblock_command(line: str) -> tuple | None:
    """Parse /setblock command to (x, y, z, block) tuple."""
    match = re.match(r'/setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$', line)
    if match:
        return (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            match.group(4)
        )
    return None


def load_optimized_commands(filename: str) -> dict:
    """Load optimized commands and expand to coordinate dict."""
    blocks = {}

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Try /fill
            expanded = expand_fill_command(line)
            if expanded:
                for x, y, z, block in expanded:
                    blocks[(x, y, z)] = block
                continue

            # Try /setblock
            result = expand_setblock_command(line)
            if result:
                x, y, z, block = result
                blocks[(x, y, z)] = block

    return blocks


def export_pipeline(url: str, output_csv: str, save_intermediate: bool = True):
    """Export full pipeline to CSV."""

    print(f'Fetching from GrabCraft: {url}')

    # Step 1: Extract from GrabCraft
    original_blocks = extract_blocks_from_web(url)
    print(f'Extracted {len(original_blocks)} original blocks')

    # Step 2: Convert to Bedrock and save commands
    bedrock_file = output_csv.replace('.csv', '_bedrock.txt')
    bedrock_commands = []
    bedrock_dict = {}

    converter = get_converter()
    converter.clear_door_cache()
    # Register all door upper blocks first
    for b in original_blocks:
        if 'door' in b['material'].lower() and 'upper' in b['material'].lower():
            converter.register_door_upper_block(b['x'], b['y'], b['z'], b['layer'], b['material'])

    for b in original_blocks:
        block_id = get_block_id(b['material'], b['x'], b['y'], b['z'], b['layer'])
        if block_id:
            cmd = f'/setblock {b["x"]} {b["y"]} {b["z"]} {block_id}'
            bedrock_commands.append(cmd)
            bedrock_dict[(b['x'], b['y'], b['z'])] = {
                'material': b['material'],
                'bedrock': block_id
            }

    if save_intermediate:
        with open(bedrock_file, 'w', encoding='utf-8') as f:
            for cmd in bedrock_commands:
                f.write(cmd + '\n')
        print(f'Saved Bedrock commands: {bedrock_file}')

    # Step 3: Optimize
    optimized_file = output_csv.replace('.csv', '_optimized.txt')
    grid = read_commands(bedrock_file)
    optimized_cmds, (fill_count, setblock_count) = optimize_grid(grid)

    if save_intermediate:
        with open(optimized_file, 'w', encoding='utf-8') as f:
            for cmd in optimized_cmds:
                f.write(cmd + '\n')
        print(f'Saved optimized commands: {optimized_file}')
        print(f'  /fill: {fill_count}, /setblock: {setblock_count}, total: {len(optimized_cmds)}')

    # Step 4: Expand optimized back
    expanded_dict = load_optimized_commands(optimized_file)
    print(f'Expanded optimized to {len(expanded_dict)} blocks')

    # Step 5: Build unified dataset
    all_coords = set()
    for b in original_blocks:
        all_coords.add((b['x'], b['y'], b['z']))
    all_coords.update(expanded_dict.keys())

    # Sort by coordinates (z, y, x for layer-by-layer)
    sorted_coords = sorted(all_coords, key=lambda c: (c[1], c[2], c[0]))

    # Step 6: Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'x', 'y', 'z',
            'original_material',
            'bedrock_block',
            'optimized_block',
            'match'
        ])

        for x, y, z in sorted_coords:
            original_mat = bedrock_dict.get((x, y, z), {}).get('material', '')
            bedrock_block = bedrock_dict.get((x, y, z), {}).get('bedrock', '')
            optimized_block = expanded_dict.get((x, y, z), '')

            # Check if bedrock and optimized match
            match = '✓' if bedrock_block == optimized_block else '✗'

            writer.writerow([
                x, y, z,
                original_mat,
                bedrock_block,
                optimized_block,
                match
            ])

    print(f'\nExported pipeline CSV: {output_csv}')
    print(f'  Total coordinates: {len(sorted_coords)}')

    # Verify integrity
    mismatches = sum(1 for x, y, z in sorted_coords
                     if bedrock_dict.get((x, y, z), {}).get('bedrock', '') != expanded_dict.get((x, y, z), ''))

    if mismatches == 0:
        print(f'  ✓ All blocks match (bedrock == optimized)')
    else:
        print(f'  ✗ {mismatches} mismatches found')


def main():
    if len(sys.argv) < 2:
        print('Usage: export_pipeline_csv.py <GRABCRAFT_URL> [output.csv]')
        print()
        print('Export full pipeline to CSV:')
        print('  1. Original GrabCraft blocks')
        print('  2. Converted to Bedrock Edition')
        print('  3. Optimized with /fill')
        print('  4. Expanded back to /setblock')
        print()
        print('Example:')
        print('  python3 export_pipeline_csv.py https://www.grabcraft.com/.../tower pipeline.csv')
        sys.exit(1)

    url = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else 'pipeline.csv'

    export_pipeline(url, output_csv)


if __name__ == '__main__':
    main()
