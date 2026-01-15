#!/usr/bin/env python3
"""
Convert GrabCraft blueprint URL directly to Minecraft Bedrock Edition commands.
Fetches block data from web page and generates /setblock commands.
No optimizations - pure 1:1 conversion from web blueprint to commands.
"""

import csv
import json
import re
import sys
from collections import Counter
from urllib.request import urlopen, Request


# ============================================================================
# MATERIAL MAPPINGS FOR MINECRAFT BEDROCK EDITION
# ============================================================================

MATERIAL_TO_BLOCK = {
    # Basic blocks
    'Stone Bricks': 'minecraft:stone_bricks',
    'Stone': 'minecraft:stone',
    'Cobblestone': 'minecraft:cobblestone',
    'Grass': 'minecraft:grass_block',
    'Dirt': 'minecraft:dirt',
    'Oak Wood': 'minecraft:oak_log',
    'Oak Wood Plank': 'minecraft:oak_planks',
    'Spruce Wood': 'minecraft:spruce_log',
    'Iron Block': 'minecraft:iron_block',
    'Glowstone': 'minecraft:glowstone',

    # Wool
    'White Wool': 'minecraft:white_wool',
    'Black Wool': 'minecraft:black_wool',
    'Gray Wool': 'minecraft:gray_wool',
    'Light Gray Wool': 'minecraft:light_gray_wool',
    'Brown Wool': 'minecraft:brown_wool',
    'Red Wool': 'minecraft:red_wool',
    'Orange Wool': 'minecraft:orange_wool',
    'Yellow Wool': 'minecraft:yellow_wool',
    'Lime Wool': 'minecraft:lime_wool',
    'Green Wool': 'minecraft:green_wool',
    'Cyan Wool': 'minecraft:cyan_wool',
    'Light Blue Wool': 'minecraft:light_blue_wool',
    'Blue Wool': 'minecraft:blue_wool',
    'Purple Wool': 'minecraft:purple_wool',
    'Magenta Wool': 'minecraft:magenta_wool',
    'Pink Wool': 'minecraft:pink_wool',

    # Fences
    'Oak Fence': 'minecraft:oak_fence',
    'Spruce Fence': 'minecraft:spruce_fence',
    'Birch Fence': 'minecraft:birch_fence',
    'Jungle Fence': 'minecraft:jungle_fence',
    'Acacia Fence': 'minecraft:acacia_fence',
    'Dark Oak Fence': 'minecraft:dark_oak_fence',

    # Slabs (Bedrock: top_slot_bit determines position)
    'Stone Slab': 'minecraft:stone_slab["minecraft:vertical_half"="bottom"]',
    'Stone Brick Slab': 'minecraft:stone_brick_slab["minecraft:vertical_half"="bottom"]',
    'Cobblestone Slab': 'minecraft:cobblestone_slab["minecraft:vertical_half"="bottom"]',
    'Wooden Slab': 'minecraft:oak_slab["minecraft:vertical_half"="bottom"]',
    'Oak Slab': 'minecraft:oak_slab["minecraft:vertical_half"="bottom"]',
    'Spruce Slab': 'minecraft:spruce_slab["minecraft:vertical_half"="bottom"]',
    'Birch Slab': 'minecraft:birch_slab["minecraft:vertical_half"="bottom"]',

    # Double Slabs (full blocks made from slabs)
    'Double Stone Slab': 'minecraft:smooth_stone',
    'Double Stone Brick Slab': 'minecraft:stone_bricks',
    'Double Cobblestone Slab': 'minecraft:cobblestone',
    'Double Wooden Slab': 'minecraft:oak_planks',

    # Water
    'Still Water': 'minecraft:water',
    'Water': 'minecraft:water',
    'Water (Water level Max)': 'minecraft:water',
    'Water (Water level Max - 1)': 'minecraft:water',
    'Water (Water level Max - 2)': 'minecraft:water',
    'Water (Water level Max - 3)': 'minecraft:water',
    'Water (Water level Max - 1, Falling)': 'minecraft:water',
    'Water (Water level Max - 2, Falling)': 'minecraft:water',

    # Lily Pad (Bedrock uses waterlily)
    'Lily Pad': 'minecraft:waterlily',

    # Vines (Bedrock uses vine_direction_bits: 1=south, 2=west, 4=north, 8=east)
    'Vines ()': 'minecraft:vine',
    'Vines (North)': 'minecraft:vine["vine_direction_bits"=4]',
    'Vines (South)': 'minecraft:vine["vine_direction_bits"=1]',
    'Vines (East)': 'minecraft:vine["vine_direction_bits"=8]',
    'Vines (West)': 'minecraft:vine["vine_direction_bits"=2]',
    'Vines (North&West)': 'minecraft:vine["vine_direction_bits"=6]',
    'Vines (North&East)': 'minecraft:vine["vine_direction_bits"=12]',
    'Vines (South&West)': 'minecraft:vine["vine_direction_bits"=3]',
    'Vines (South&East)': 'minecraft:vine["vine_direction_bits"=9]',

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

    # Oak Wood Stairs - Normal (Bedrock: upside_down_bit=false for normal, weirdo_direction for facing)
    'Oak Wood Stairs (North, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Oak Wood Stairs (South, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=3]',
    'Oak Wood Stairs (East, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Oak Wood Stairs (West, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=0]',

    # Oak Wood Stairs - Upside-down (Bedrock: upside_down_bit=true for top)
    'Oak Wood Stairs (North, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=2]',
    'Oak Wood Stairs (South, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=3]',
    'Oak Wood Stairs (East, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Oak Wood Stairs (West, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=0]',

    # Cobblestone Stairs - Normal (Bedrock: upside_down_bit=false for normal, weirdo_direction for facing)
    'Cobblestone Stairs (North, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Cobblestone Stairs (South, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=false,"weirdo_direction"=3]',
    'Cobblestone Stairs (East, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Cobblestone Stairs (West, Normal)': 'minecraft:cobblestone_stairs["upside_down_bit"=false,"weirdo_direction"=0]',

    # Cobblestone Stairs - Upside-down (Bedrock: upside_down_bit=true for top)
    'Cobblestone Stairs (North, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=true,"weirdo_direction"=2]',
    'Cobblestone Stairs (South, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=true,"weirdo_direction"=3]',
    'Cobblestone Stairs (East, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Cobblestone Stairs (West, Upside-down)': 'minecraft:cobblestone_stairs["upside_down_bit"=true,"weirdo_direction"=0]',

    # Stone Brick Stairs - Normal (Bedrock: upside_down_bit=false for normal, weirdo_direction for facing)
    'Stone Brick Stairs (North)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Stone Brick Stairs (South)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=3]',
    'Stone Brick Stairs (East)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Stone Brick Stairs (West)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=0]',
    'Stone Brick Stairs (North, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Stone Brick Stairs (South, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=3]',
    'Stone Brick Stairs (East, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Stone Brick Stairs (West, Normal)': 'minecraft:stone_brick_stairs["upside_down_bit"=false,"weirdo_direction"=0]',

    # Stone Brick Stairs - Upside-down (Bedrock: upside_down_bit=true for top)
    'Stone Brick Stairs (North, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=true,"weirdo_direction"=2]',
    'Stone Brick Stairs (South, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=true,"weirdo_direction"=3]',
    'Stone Brick Stairs (East, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Stone Brick Stairs (West, Upside-down)': 'minecraft:stone_brick_stairs["upside_down_bit"=true,"weirdo_direction"=0]',
}


# ============================================================================
# WEB SCRAPING FUNCTIONS
# ============================================================================

def fetch_page(url: str) -> str:
    """Fetch content from URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8')


def extract_layermap_url(html: str) -> str | None:
    """Extract LayerMap JS URL from page HTML."""
    match = re.search(r'src="([^"]*LayerMap[^"]*\.js)"', html)
    if match:
        url = match.group(1)
        if not url.startswith('http'):
            url = 'https://www.grabcraft.com' + url
        return url
    return None


def extract_dimensions(html: str) -> tuple[int, int, int]:
    """Extract dimensions from page HTML."""
    dim_x = dim_y = dim_z = 11  # defaults

    match = re.search(r'var dimY\s*=\s*(\d+)', html)
    if match:
        dim_y = int(match.group(1))

    match = re.search(r'var dimX\s*=\s*(\d+)', html)
    if match:
        dim_x = int(match.group(1))

    match = re.search(r'var dimZ\s*=\s*(\d+)', html)
    if match:
        dim_z = int(match.group(1))

    return dim_x, dim_y, dim_z


def parse_layermap_js(js_content: str) -> dict:
    """Parse LayerMap JS and extract layer data."""
    match = re.search(r'var\s+layerMap\s*=\s*(\{.*\})\s*;?\s*$', js_content, re.DOTALL)
    if not match:
        raise ValueError("Could not find layerMap in JS content")

    json_str = match.group(1)
    return json.loads(json_str)


def pixel_to_grid(pixel_x: int, pixel_y: int, cell_size: int = 20,
                  grid_offset_x: int = 5, grid_offset_y: int = 291) -> tuple[int, int]:
    """Convert pixel coordinates to grid coordinates."""
    grid_x = (pixel_x - grid_offset_x) // cell_size
    grid_z = (pixel_y - grid_offset_y) // cell_size
    return grid_x, grid_z


def extract_blocks_from_web(page_url: str) -> list[dict]:
    """Fetch and extract all blocks from GrabCraft page."""
    print(f'Fetching page: {page_url}')
    html = fetch_page(page_url)

    # Extract dimensions
    dim_x, dim_y, dim_z = extract_dimensions(html)
    print(f'Dimensions: {dim_x}x{dim_y}x{dim_z} (X x Y x Z)')

    # Find LayerMap JS URL
    layermap_url = extract_layermap_url(html)
    if not layermap_url:
        raise ValueError('Could not find LayerMap JS URL in page')

    print(f'Fetching LayerMap: {layermap_url}')
    js_content = fetch_page(layermap_url)

    # Parse LayerMap
    print('Parsing layer data...')
    layermap = parse_layermap_js(js_content)
    print(f'Found {len(layermap)} layers')

    # Extract blocks
    blocks = []
    cell_size = 20
    grid_offset_x = 5
    grid_offset_y = 291

    for layer_str, layer_blocks in layermap.items():
        layer_num = int(layer_str)

        for block in layer_blocks:
            pixel_x = block['x']
            pixel_y = block['y']
            material = block['h']

            grid_x, grid_z = pixel_to_grid(pixel_x, pixel_y, cell_size,
                                           grid_offset_x, grid_offset_y)

            if 0 <= grid_x < dim_x and 0 <= grid_z < dim_z:
                blocks.append({
                    'layer': layer_num,
                    'x': grid_x,
                    'z': grid_z,
                    'y': layer_num,
                    'material': material
                })

    blocks.sort(key=lambda b: (b['layer'], b['z'], b['x']))
    print(f'Extracted {len(blocks)} blocks')

    return blocks


# ============================================================================
# COMMAND GENERATION FUNCTIONS
# ============================================================================

def get_block_id(material: str) -> str:
    """Convert material name to Minecraft block ID."""
    if material in MATERIAL_TO_BLOCK:
        return MATERIAL_TO_BLOCK[material]

    # Try to auto-convert unknown materials
    block_name = material.lower().replace(' ', '_')

    # Special handling for stairs with default orientation
    if 'stairs' in block_name.lower():
        # Extract base name and remove direction/orientation info
        base_name = re.sub(r'\([^)]*\)', '', block_name).strip('_')
        # Map common wood types
        base_name = base_name.replace('oak_wood_stairs', 'oak_stairs')
        base_name = base_name.replace('spruce_wood_stairs', 'spruce_stairs')
        base_name = base_name.replace('birch_wood_stairs', 'birch_stairs')
        base_name = base_name.replace('jungle_wood_stairs', 'jungle_stairs')
        base_name = base_name.replace('acacia_wood_stairs', 'acacia_stairs')
        base_name = base_name.replace('dark_oak_wood_stairs', 'dark_oak_stairs')
        # Add default Bedrock state
        return f'minecraft:{base_name}["upside_down_bit"=false,"weirdo_direction"=3]'

    # Remove parentheses and their contents for other blocks
    block_name = re.sub(r'\([^)]*\)', '', block_name).strip('_')
    return f'minecraft:{block_name}'


def is_attachable_block(material: str) -> bool:
    """Check if block needs to be attached to another block (place last)."""
    block_id = get_block_id(material)
    attachable = ['ladder', 'torch', 'wall_torch']
    for b in attachable:
        if b in block_id:
            return True
    return False


def generate_commands(blocks: list[dict]) -> list[str]:
    """Generate Minecraft /setblock commands for all blocks."""
    commands = []
    attachable_commands = []

    for b in blocks:
        block_id = get_block_id(b['material'])
        cmd = f'/setblock {b["x"]} {b["y"]} {b["z"]} {block_id}'
        if is_attachable_block(b['material']):
            attachable_commands.append(cmd)
        else:
            commands.append(cmd)

    # Add attachable blocks at the end (they need support blocks first)
    commands.extend(attachable_commands)

    return commands


# ============================================================================
# MAIN
# ============================================================================

def main():
    page_url = 'https://www.grabcraft.com/minecraft/oakshire-wall-tower/military-buildings'
    output_file = 'build_commands.txt'
    save_csv = False
    csv_file = 'blocks.csv'

    # Parse arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ('-h', '--help'):
            print('Usage: grabcraft_to_commands.py [URL] [options]')
            print()
            print('Convert GrabCraft blueprint to Minecraft Bedrock Edition commands.')
            print('Generates pure /setblock commands - one per block, no optimizations.')
            print()
            print('Arguments:')
            print('  URL                 GrabCraft page URL (required)')
            print()
            print('Options:')
            print('  -o FILE             Output file (default: build_commands.txt)')
            print('  --save-csv [FILE]   Save blocks to CSV file (default: blocks.csv)')
            print()
            print('Examples:')
            print('  python3 grabcraft_to_commands.py https://www.grabcraft.com/minecraft/tower/...')
            print('  python3 grabcraft_to_commands.py <URL> -o tower.txt')
            print('  python3 grabcraft_to_commands.py <URL> --save-csv blocks.csv')
            print()
            print('Note: Use --offset-x/y/z in mc-commander CLI to apply coordinate offsets.')
            print('Use optimize_commands.py to apply /fill optimization after generation.')
            sys.exit(0)
        elif args[i] == '-o' and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == '--save-csv':
            save_csv = True
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                csv_file = args[i + 1]
                i += 2
            else:
                i += 1
        elif not args[i].startswith('-'):
            page_url = args[i]
            i += 1
        else:
            i += 1

    # Fetch blocks from web
    blocks = extract_blocks_from_web(page_url)

    # Print material summary
    materials = Counter(b['material'] for b in blocks)
    print('\nMaterials:')
    for mat, count in materials.most_common():
        print(f'  {mat}: {count}')

    # Save CSV if requested
    if save_csv:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['layer', 'x', 'z', 'y', 'material'])
            writer.writeheader()
            writer.writerows(blocks)
        print(f'\nSaved blocks to {csv_file}')

    # Generate commands
    print('\nGenerating commands...')
    commands = generate_commands(blocks)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    print(f'Generated {len(commands)} commands to {output_file}')
    print(f'  /setblock commands: {len(commands)}')
    print('\nNote: Use mc-commander with --offset-x/y/z to apply coordinate offsets when executing.')


if __name__ == '__main__':
    main()
