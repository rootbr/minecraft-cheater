#!/usr/bin/env python3
"""
Generate Minecraft commands to build a structure from blocks CSV.
Outputs /setblock and /fill commands optimized for building.
"""

import csv
import re
import sys
from collections import defaultdict


# Mapping from GrabCraft material names to Minecraft block IDs
MATERIAL_TO_BLOCK = {
    # Basic blocks
    'Stone Bricks': 'minecraft:stone_bricks',
    'Cobblestone': 'minecraft:cobblestone',
    'Grass': 'minecraft:grass_block',
    'Oak Wood': 'minecraft:oak_log',
    'Oak Wood Plank': 'minecraft:oak_planks',
    'Iron Block': 'minecraft:iron_block',

    # Chests
    'Chest (North)': 'minecraft:chest[facing=north]',
    'Chest (South)': 'minecraft:chest[facing=south]',
    'Chest (East)': 'minecraft:chest[facing=east]',
    'Chest (West)': 'minecraft:chest[facing=west]',

    # Ladders
    'Ladder (facing north)': 'minecraft:ladder[facing=north]',
    'Ladder (facing south)': 'minecraft:ladder[facing=south]',
    'Ladder (facing east)': 'minecraft:ladder[facing=east]',
    'Ladder (facing west)': 'minecraft:ladder[facing=west]',

    # Torches
    'Torch (Facing Up)': 'minecraft:torch',
    'Torch (Facing North)': 'minecraft:wall_torch[facing=north]',
    'Torch (Facing South)': 'minecraft:wall_torch[facing=south]',
    'Torch (Facing East)': 'minecraft:wall_torch[facing=east]',
    'Torch (Facing West)': 'minecraft:wall_torch[facing=west]',

    # Cobblestone Stairs - Normal
    'Cobblestone Stairs (North, Normal)': 'minecraft:cobblestone_stairs[facing=north,half=bottom]',
    'Cobblestone Stairs (South, Normal)': 'minecraft:cobblestone_stairs[facing=south,half=bottom]',
    'Cobblestone Stairs (East, Normal)': 'minecraft:cobblestone_stairs[facing=east,half=bottom]',
    'Cobblestone Stairs (West, Normal)': 'minecraft:cobblestone_stairs[facing=west,half=bottom]',

    # Cobblestone Stairs - Upside-down
    'Cobblestone Stairs (North, Upside-down)': 'minecraft:cobblestone_stairs[facing=north,half=top]',
    'Cobblestone Stairs (South, Upside-down)': 'minecraft:cobblestone_stairs[facing=south,half=top]',
    'Cobblestone Stairs (East, Upside-down)': 'minecraft:cobblestone_stairs[facing=east,half=top]',
    'Cobblestone Stairs (West, Upside-down)': 'minecraft:cobblestone_stairs[facing=west,half=top]',

    # Stone Brick Stairs - Normal
    'Stone Brick Stairs (North)': 'minecraft:stone_brick_stairs[facing=north,half=bottom]',
    'Stone Brick Stairs (South)': 'minecraft:stone_brick_stairs[facing=south,half=bottom]',
    'Stone Brick Stairs (East)': 'minecraft:stone_brick_stairs[facing=east,half=bottom]',
    'Stone Brick Stairs (West)': 'minecraft:stone_brick_stairs[facing=west,half=bottom]',
    'Stone Brick Stairs (North, Normal)': 'minecraft:stone_brick_stairs[facing=north,half=bottom]',
    'Stone Brick Stairs (South, Normal)': 'minecraft:stone_brick_stairs[facing=south,half=bottom]',
    'Stone Brick Stairs (East, Normal)': 'minecraft:stone_brick_stairs[facing=east,half=bottom]',
    'Stone Brick Stairs (West, Normal)': 'minecraft:stone_brick_stairs[facing=west,half=bottom]',

    # Stone Brick Stairs - Upside-down
    'Stone Brick Stairs (North, Upside-down)': 'minecraft:stone_brick_stairs[facing=north,half=top]',
    'Stone Brick Stairs (South, Upside-down)': 'minecraft:stone_brick_stairs[facing=south,half=top]',
    'Stone Brick Stairs (East, Upside-down)': 'minecraft:stone_brick_stairs[facing=east,half=top]',
    'Stone Brick Stairs (West, Upside-down)': 'minecraft:stone_brick_stairs[facing=west,half=top]',
}


def get_block_id(material: str) -> str:
    """Convert material name to Minecraft block ID."""
    if material in MATERIAL_TO_BLOCK:
        return MATERIAL_TO_BLOCK[material]

    # Try to auto-convert unknown materials
    # Convert to lowercase, replace spaces with underscores
    block_name = material.lower().replace(' ', '_')
    block_name = re.sub(r'\([^)]*\)', '', block_name).strip('_')
    return f'minecraft:{block_name}'


def load_blocks(csv_path: str) -> list[dict]:
    """Load blocks from CSV file."""
    blocks = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            blocks.append({
                'x': int(row['x']),
                'y': int(row['y']),
                'z': int(row['z']),
                'material': row['material']
            })
    return blocks


def find_fill_regions(blocks: list[dict]) -> list[tuple]:
    """
    Find regions of same material that can use /fill command.
    Returns list of (x1, y1, z1, x2, y2, z2, material) tuples.
    """
    # Group blocks by material and y-level
    by_material_y = defaultdict(list)
    for b in blocks:
        key = (b['material'], b['y'])
        by_material_y[key].append((b['x'], b['z']))

    fill_regions = []
    used_blocks = set()

    for (material, y), coords in by_material_y.items():
        coords_set = set(coords)

        # Find horizontal lines (same z, consecutive x)
        by_z = defaultdict(list)
        for x, z in coords:
            by_z[z].append(x)

        for z, x_list in by_z.items():
            x_list.sort()
            # Find consecutive runs
            i = 0
            while i < len(x_list):
                start_x = x_list[i]
                end_x = start_x
                while i + 1 < len(x_list) and x_list[i + 1] == end_x + 1:
                    i += 1
                    end_x = x_list[i]

                if end_x > start_x:  # At least 2 blocks in a row
                    fill_regions.append((start_x, y, z, end_x, y, z, material))
                    for x in range(start_x, end_x + 1):
                        used_blocks.add((x, y, z, material))
                i += 1

    return fill_regions, used_blocks


def generate_commands(blocks: list[dict], offset_x: int = 0, offset_y: int = 64,
                      offset_z: int = 0, use_fill: bool = True) -> list[str]:
    """Generate Minecraft commands for all blocks."""
    commands = []

    if use_fill:
        fill_regions, used_blocks = find_fill_regions(blocks)

        # Generate /fill commands for regions
        for x1, y1, z1, x2, y2, z2, material in fill_regions:
            block_id = get_block_id(material)
            cmd = f'/fill {x1 + offset_x} {y1 + offset_y} {z1 + offset_z} ' \
                  f'{x2 + offset_x} {y2 + offset_y} {z2 + offset_z} {block_id}'
            commands.append(cmd)

        # Generate /setblock for remaining blocks
        for b in blocks:
            key = (b['x'], b['y'], b['z'], b['material'])
            if key not in used_blocks:
                block_id = get_block_id(b['material'])
                cmd = f'/setblock {b["x"] + offset_x} {b["y"] + offset_y} ' \
                      f'{b["z"] + offset_z} {block_id}'
                commands.append(cmd)
    else:
        # Simple mode: only /setblock
        for b in blocks:
            block_id = get_block_id(b['material'])
            cmd = f'/setblock {b["x"] + offset_x} {b["y"] + offset_y} ' \
                  f'{b["z"] + offset_z} {block_id}'
            commands.append(cmd)

    return commands


def main():
    input_csv = 'blocks_web.csv'
    output_file = 'build_commands.mcfunction'
    offset_x = 0
    offset_y = 64  # Default Y offset (sea level)
    offset_z = 0
    use_fill = True

    # Parse arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '-i' and i + 1 < len(args):
            input_csv = args[i + 1]
            i += 2
        elif args[i] == '-o' and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == '-x' and i + 1 < len(args):
            offset_x = int(args[i + 1])
            i += 2
        elif args[i] == '-y' and i + 1 < len(args):
            offset_y = int(args[i + 1])
            i += 2
        elif args[i] == '-z' and i + 1 < len(args):
            offset_z = int(args[i + 1])
            i += 2
        elif args[i] == '--no-fill':
            use_fill = False
            i += 1
        elif args[i] in ('-h', '--help'):
            print(f'Usage: {sys.argv[0]} [options]')
            print('Options:')
            print('  -i FILE    Input CSV file (default: blocks_web.csv)')
            print('  -o FILE    Output file (default: build_commands.mcfunction)')
            print('  -x N       X offset (default: 0)')
            print('  -y N       Y offset (default: 64)')
            print('  -z N       Z offset (default: 0)')
            print('  --no-fill  Use only /setblock commands')
            sys.exit(0)
        else:
            i += 1

    print(f'Loading blocks from {input_csv}')
    blocks = load_blocks(input_csv)
    print(f'Loaded {len(blocks)} blocks')

    print(f'Generating commands with offset ({offset_x}, {offset_y}, {offset_z})')
    commands = generate_commands(blocks, offset_x, offset_y, offset_z, use_fill)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    print(f'Generated {len(commands)} commands to {output_file}')

    # Summary
    fill_count = sum(1 for c in commands if c.startswith('/fill'))
    setblock_count = sum(1 for c in commands if c.startswith('/setblock'))
    print(f'  /fill commands: {fill_count}')
    print(f'  /setblock commands: {setblock_count}')


if __name__ == '__main__':
    main()
