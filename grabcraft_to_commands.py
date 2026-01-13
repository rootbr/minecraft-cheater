#!/usr/bin/env python3
"""
Convert GrabCraft blueprint URL directly to Minecraft Bedrock Edition commands.
Fetches block data from web page and generates optimized /fill and /setblock commands.
"""

import csv
import json
import re
import sys
from collections import defaultdict, Counter
from urllib.request import urlopen, Request


# ============================================================================
# MATERIAL MAPPINGS FOR MINECRAFT BEDROCK EDITION
# ============================================================================

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
    block_name = re.sub(r'\([^)]*\)', '', block_name).strip('_')
    return f'minecraft:{block_name}'


def can_use_fill(material: str) -> bool:
    """Check if material can be used with /fill command."""
    block_id = get_block_id(material)
    if '[' in block_id:
        return False
    no_fill_blocks = ['ladder', 'torch', 'wall_torch', 'chest']
    for b in no_fill_blocks:
        if b in block_id:
            return False
    return True


def find_fill_regions(blocks: list[dict]) -> tuple[list[tuple], set]:
    """
    Find regions of same material that can use /fill command.
    Optimizes in order: 3D cuboids -> 2D rectangles -> 1D lines -> vertical columns
    """
    # Group blocks by material
    by_material = defaultdict(list)
    for b in blocks:
        if can_use_fill(b['material']):
            by_material[b['material']].append((b['x'], b['y'], b['z']))

    fill_regions = []
    used_blocks = set()

    for material, coords in by_material.items():
        remaining = set(coords) - used_blocks

        # Try to find 3D cuboids (at least 2x2x2)
        remaining = find_cuboids(material, remaining, fill_regions, used_blocks)

        # Try to find 2D rectangles on same Y level (at least 2x2)
        remaining = find_rectangles(material, remaining, fill_regions, used_blocks)

        # Try to find 1D horizontal lines (at least 2 blocks)
        remaining = find_horizontal_lines(material, remaining, fill_regions, used_blocks)

        # Try to find vertical columns (at least 2 blocks)
        remaining = find_vertical_columns(material, remaining, fill_regions, used_blocks)

    return fill_regions, used_blocks


def find_cuboids(material: str, coords: set, fill_regions: list, used_blocks: set) -> set:
    """Find 3D cuboid regions."""
    remaining = coords.copy()
    coords_list = sorted(remaining)

    for x, y, z in coords_list:
        if (x, y, z) not in remaining:
            continue

        # Try to expand in all directions
        max_x = x
        max_y = y
        max_z = z

        # Find max X extent at this Y, Z
        while (max_x + 1, y, z) in remaining:
            max_x += 1

        # Find max Z extent for this X range at this Y
        can_expand_z = True
        while can_expand_z and (x, y, max_z + 1) in remaining:
            # Check if entire X range exists at next Z
            for check_x in range(x, max_x + 1):
                if (check_x, y, max_z + 1) not in remaining:
                    can_expand_z = False
                    break
            if can_expand_z:
                max_z += 1

        # Find max Y extent for this XZ rectangle
        can_expand_y = True
        while can_expand_y and (x, max_y + 1, z) in remaining:
            # Check if entire XZ rectangle exists at next Y
            for check_x in range(x, max_x + 1):
                for check_z in range(z, max_z + 1):
                    if (check_x, max_y + 1, check_z) not in remaining:
                        can_expand_y = False
                        break
                if not can_expand_y:
                    break
            if can_expand_y:
                max_y += 1

        # Only create cuboid if it's at least 2x2x2
        volume = (max_x - x + 1) * (max_y - y + 1) * (max_z - z + 1)
        if volume >= 8:  # At least 2x2x2
            fill_regions.append((x, y, z, max_x, max_y, max_z, material))
            for rx in range(x, max_x + 1):
                for ry in range(y, max_y + 1):
                    for rz in range(z, max_z + 1):
                        remaining.discard((rx, ry, rz))
                        used_blocks.add((rx, ry, rz, material))

    return remaining


def find_rectangles(material: str, coords: set, fill_regions: list, used_blocks: set) -> set:
    """Find 2D rectangular regions on same Y level."""
    remaining = coords.copy()

    # Group by Y level
    by_y = defaultdict(list)
    for x, y, z in remaining:
        by_y[y].append((x, z))

    for y, xz_coords in by_y.items():
        xz_set = set(xz_coords)
        xz_sorted = sorted(xz_set)

        for x, z in xz_sorted:
            if (x, z) not in xz_set:
                continue

            # Find max X extent at this Z
            max_x = x
            while (max_x + 1, z) in xz_set:
                max_x += 1

            # Find max Z extent for this X range
            max_z = z
            can_expand = True
            while can_expand:
                max_z += 1
                for check_x in range(x, max_x + 1):
                    if (check_x, max_z) not in xz_set:
                        can_expand = False
                        max_z -= 1
                        break

            # Only create rectangle if it's at least 2x2
            area = (max_x - x + 1) * (max_z - z + 1)
            if area >= 4:
                fill_regions.append((x, y, z, max_x, y, max_z, material))
                for rx in range(x, max_x + 1):
                    for rz in range(z, max_z + 1):
                        xz_set.discard((rx, rz))
                        remaining.discard((rx, y, rz))
                        used_blocks.add((rx, y, rz, material))

    return remaining


def find_horizontal_lines(material: str, coords: set, fill_regions: list, used_blocks: set) -> set:
    """Find horizontal lines along X or Z axis."""
    remaining = coords.copy()

    # Group by Y and Z for X-direction lines
    by_yz = defaultdict(list)
    for x, y, z in remaining:
        by_yz[(y, z)].append(x)

    for (y, z), x_list in by_yz.items():
        x_list.sort()
        i = 0
        while i < len(x_list):
            start_x = x_list[i]
            end_x = start_x
            while i + 1 < len(x_list) and x_list[i + 1] == end_x + 1:
                i += 1
                end_x = x_list[i]

            if end_x > start_x:
                fill_regions.append((start_x, y, z, end_x, y, z, material))
                for x in range(start_x, end_x + 1):
                    remaining.discard((x, y, z))
                    used_blocks.add((x, y, z, material))
            i += 1

    # Group by Y and X for Z-direction lines
    by_yx = defaultdict(list)
    for x, y, z in remaining:
        by_yx[(y, x)].append(z)

    for (y, x), z_list in by_yx.items():
        z_list.sort()
        i = 0
        while i < len(z_list):
            start_z = z_list[i]
            end_z = start_z
            while i + 1 < len(z_list) and z_list[i + 1] == end_z + 1:
                i += 1
                end_z = z_list[i]

            if end_z > start_z:
                fill_regions.append((x, y, start_z, x, y, end_z, material))
                for z in range(start_z, end_z + 1):
                    remaining.discard((x, y, z))
                    used_blocks.add((x, y, z, material))
            i += 1

    return remaining


def find_vertical_columns(material: str, coords: set, fill_regions: list, used_blocks: set) -> set:
    """Find vertical columns along Y axis."""
    remaining = coords.copy()

    # Group by X and Z for Y-direction columns
    by_xz = defaultdict(list)
    for x, y, z in remaining:
        by_xz[(x, z)].append(y)

    for (x, z), y_list in by_xz.items():
        y_list.sort()
        i = 0
        while i < len(y_list):
            start_y = y_list[i]
            end_y = start_y
            while i + 1 < len(y_list) and y_list[i + 1] == end_y + 1:
                i += 1
                end_y = y_list[i]

            if end_y > start_y:
                fill_regions.append((x, start_y, z, x, end_y, z, material))
                for y in range(start_y, end_y + 1):
                    remaining.discard((x, y, z))
                    used_blocks.add((x, y, z, material))
            i += 1

    return remaining


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
    attachable_commands = []

    if use_fill:
        fill_regions, used_blocks = find_fill_regions(blocks)

        # Generate /fill commands
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

    # Add attachable blocks at the end
    commands.extend(attachable_commands)

    return commands


# ============================================================================
# MAIN
# ============================================================================

def main():
    page_url = 'https://www.grabcraft.com/minecraft/oakshire-wall-tower/military-buildings'
    output_file = 'build_commands.mcfunction'
    offset_x = 0
    offset_y = 64
    offset_z = 0
    use_fill = True
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
            print()
            print('Arguments:')
            print('  URL                 GrabCraft page URL (required)')
            print()
            print('Options:')
            print('  -o FILE             Output file (default: build_commands.mcfunction)')
            print('  -x N                X offset (default: 0)')
            print('  -y N                Y offset (default: 64)')
            print('  -z N                Z offset (default: 0)')
            print('  --no-fill           Use only /setblock commands')
            print('  --save-csv [FILE]   Save blocks to CSV file (default: blocks.csv)')
            print()
            print('Examples:')
            print('  python3 grabcraft_to_commands.py https://www.grabcraft.com/minecraft/tower/...')
            print('  python3 grabcraft_to_commands.py <URL> -o tower.mcfunction -y 70')
            print('  python3 grabcraft_to_commands.py <URL> --save-csv blocks.csv')
            sys.exit(0)
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
    print(f'\nGenerating commands with offset ({offset_x}, {offset_y}, {offset_z})')
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
