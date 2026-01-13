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

    # Chests (Bedrock Edition uses numeric facing_direction)
    'Chest (North)': 'minecraft:chest["facing_direction"=2]',
    'Chest (South)': 'minecraft:chest["facing_direction"=3]',
    'Chest (East)': 'minecraft:chest["facing_direction"=5]',
    'Chest (West)': 'minecraft:chest["facing_direction"=4]',

    # Ladders (Bedrock Edition uses numeric facing_direction: 2=north, 3=south, 4=west, 5=east)
    'Ladder (facing north)': 'minecraft:ladder["facing_direction"=2]',
    'Ladder (facing south)': 'minecraft:ladder["facing_direction"=3]',
    'Ladder (facing east)': 'minecraft:ladder["facing_direction"=5]',
    'Ladder (facing west)': 'minecraft:ladder["facing_direction"=4]',

    # Torches
    'Torch (Facing Up)': 'minecraft:torch',
    'Torch (Facing North)': 'minecraft:wall_torch["facing_direction"=2]',
    'Torch (Facing South)': 'minecraft:wall_torch["facing_direction"=3]',
    'Torch (Facing East)': 'minecraft:wall_torch["facing_direction"=5]',
    'Torch (Facing West)': 'minecraft:wall_torch["facing_direction"=4]',

    # Cobblestone Stairs - Normal (Bedrock: upside_down_bit=0 for normal, weirdo_direction for facing)
    'Cobblestone Stairs (North, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=0,"weirdo_direction"=2]',
    'Cobblestone Stairs (South, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=0,"weirdo_direction"=3]',
    'Cobblestone Stairs (East, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=0,"weirdo_direction"=1]',
    'Cobblestone Stairs (West, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=0,"weirdo_direction"=0]',

    # Cobblestone Stairs - Upside-down (Bedrock: upside_down_bit=1 for top)
    'Cobblestone Stairs (North, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=1,"weirdo_direction"=2]',
    'Cobblestone Stairs (South, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=1,"weirdo_direction"=3]',
    'Cobblestone Stairs (East, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=1,"weirdo_direction"=1]',
    'Cobblestone Stairs (West, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=1,"weirdo_direction"=0]',

    # Stone Brick Stairs - Normal (Bedrock: upside_down_bit=0 for normal, weirdo_direction for facing)
    'Stone Brick Stairs (North)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=2]',
    'Stone Brick Stairs (South)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=3]',
    'Stone Brick Stairs (East)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=1]',
    'Stone Brick Stairs (West)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=0]',
    'Stone Brick Stairs (North, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=2]',
    'Stone Brick Stairs (South, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=3]',
    'Stone Brick Stairs (East, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=1]',
    'Stone Brick Stairs (West, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=0,"weirdo_direction"=0]',

    # Stone Brick Stairs - Upside-down (Bedrock: upside_down_bit=1 for top)
    'Stone Brick Stairs (North, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=1,"weirdo_direction"=2]',
    'Stone Brick Stairs (South, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=1,"weirdo_direction"=3]',
    'Stone Brick Stairs (East, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=1,"weirdo_direction"=1]',
    'Stone Brick Stairs (West, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=1,"weirdo_direction"=0]',
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


def can_use_fill(material: str) -> bool:
    """Check if material can be used with /fill command."""
    block_id = get_block_id(material)
    # Blocks with state parameters can't be used with /fill reliably
    if '[' in block_id:
        return False
    # Some blocks need adjacent blocks to place
    no_fill_blocks = ['ladder', 'torch', 'wall_torch', 'chest']
    for b in no_fill_blocks:
        if b in block_id:
            return False
    return True


def find_fill_regions(blocks: list[dict]) -> list[tuple]:
    """
    Find regions of same material that can use /fill command.
    Returns list of (x1, y1, z1, x2, y2, z2, material) tuples.
    """
    # Group blocks by material and y-level (only for fillable materials)
    by_material_y = defaultdict(list)
    for b in blocks:
        if can_use_fill(b['material']):
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


def is_attachable_block(material: str) -> bool:
    """Check if block needs to be attached to another block."""
    block_id = get_block_id(material)
    attachable = ['ladder', 'torch', 'wall_torch']
    for b in attachable:
        if b in block_id:
            return True
    return False


def generate_commands(blocks: list[dict], offset_x: int = 0, offset_y: int = 64,
                      offset_z: int = 0, use_fill: bool = True) -> list[str]:
    """Generate Minecraft commands for all blocks."""
    commands = []
    attachable_commands = []  # Commands for blocks that need walls first

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
                if is_attachable_block(b['material']):
                    attachable_commands.append(cmd)
                else:
                    commands.append(cmd)
    else:
        # Simple mode: only /setblock
        for b in blocks:
            block_id = get_block_id(b['material'])
            cmd = f'/setblock {b["x"] + offset_x} {b["y"] + offset_y} ' \
                  f'{b["z"] + offset_z} {block_id}'
            if is_attachable_block(b['material']):
                attachable_commands.append(cmd)
            else:
                commands.append(cmd)

    # Add attachable blocks at the end (after walls are placed)
    commands.extend(attachable_commands)

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
