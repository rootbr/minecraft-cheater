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

from grabcraft_to_bedrock import convert_grabcraft_to_bedrock, get_converter

# ============================================================================
# COMPASS ROTATION DETECTION
# ============================================================================

def detect_compass_rotation_from_html(html: str) -> int:
    """
    Detect compass orientation from HTML compass container.

    Returns:
        0: North points up (standard)
        90: North points left (rotated 90° CCW)
        180: North points down
        270: North points right (rotated 90° CW)
    """
    # Find compass container
    compass_match = re.search(
        r'<div[^>]*class=["\']compass-container["\'][^>]*>(.*?)</div>',
        html,
        re.DOTALL | re.IGNORECASE
    )

    if not compass_match:
        print('No compass container found in HTML, assuming standard orientation (0°)')
        return 0

    compass_html = compass_match.group(1)

    # Find span containing text "N" (North)
    # ID indicates screen position, text content indicates actual direction
    north_span_match = re.search(
        r'<span[^>]*>N</span>',
        compass_html,
        re.IGNORECASE
    )

    if not north_span_match:
        print('Could not find North (N) in compass, assuming standard orientation (0°)')
        return 0

    north_span = north_span_match.group(0)

    # Extract the full span with its attributes
    full_north_span = re.search(
        r'<span[^>]*id=["\']([^"\']+)["\'][^>]*class=["\']([^"\']*)["\'][^>]*>N</span>',
        compass_html,
        re.IGNORECASE
    )

    if not full_north_span:
        # Try alternate order (class before id)
        full_north_span = re.search(
            r'<span[^>]*class=["\']([^"\']*)["\'][^>]*id=["\']([^"\']+)["\'][^>]*>N</span>',
            compass_html,
            re.IGNORECASE
        )
        if full_north_span:
            north_class = full_north_span.group(1)
            north_id = full_north_span.group(2)
        else:
            print('Could not parse North span attributes, assuming standard orientation (0°)')
            return 0
    else:
        north_id = full_north_span.group(1)
        north_class = full_north_span.group(2)

    # Determine rotation based on North position
    # Standard: North is in position "north" (top) without pull classes
    # 90° CCW: North is in position "west" (left) with pull-left
    # 180°: North is in position "south" (bottom) with pull-right
    # 270° CW: North is in position "east" (right) with pull-right

    if north_id == 'north':
        # North is at top position
        if 'pull-left' in north_class:
            # North at top but pulled left -> unusual, treat as standard
            rotation = 0
            print('Compass detected: North is UP (standard) -> 0° rotation')
        elif 'pull-right' in north_class:
            rotation = 0
            print('Compass detected: North is UP (standard) -> 0° rotation')
        else:
            rotation = 0
            print('Compass detected: North is UP (standard) -> 0° rotation')
    elif north_id == 'west':
        # North is at left position -> 90° CCW rotation
        rotation = 90
        print('Compass detected: North is LEFT -> 90° rotation')
    elif north_id == 'east':
        # North is at right position -> 90° CW rotation (270°)
        rotation = 270
        print('Compass detected: North is RIGHT -> 270° rotation')
    elif north_id == 'south':
        # North is at bottom position -> 180° rotation
        rotation = 180
        print('Compass detected: North is DOWN -> 180° rotation')
    else:
        rotation = 0
        print(f'Unknown North position ({north_id}), assuming standard orientation (0°)')

    return rotation


def rotate_coordinates(x: int, z: int, rotation: int, width: int, depth: int) -> tuple[int, int]:
    """
    Rotate grid coordinates around center.

    Args:
        x, z: Original coordinates
        rotation: Rotation in degrees (0, 90, 180, 270)
        width, depth: Grid dimensions for calculating rotation center

    Returns:
        (new_x, new_z): Rotated coordinates
    """
    if rotation == 0:
        return x, z
    elif rotation == 90:
        # 90° CW: (x, z) -> (depth - z - 1, x)
        return depth - z - 1, x
    elif rotation == 180:
        # 180°: (x, z) -> (width - x - 1, depth - z - 1)
        return width - x - 1, depth - z - 1
    elif rotation == 270:
        # 90° CCW: (x, z) -> (z, width - x - 1)
        return z, width - x - 1
    else:
        return x, z




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

    # First pass: collect all pixel coordinates and auto-detect cell size
    all_xs = []
    all_ys = []

    for layer_blocks in layermap.values():
        for block in layer_blocks:
            all_xs.append(block['x'])
            all_ys.append(block['y'])

    # Auto-detect cell size from coordinate spacing
    xs_unique = sorted(set(all_xs))
    ys_unique = sorted(set(all_ys))

    cell_size = 15  # default
    if len(xs_unique) > 1:
        x_step = xs_unique[1] - xs_unique[0]
        cell_size = x_step

    # Use minimum coordinates as offsets
    grid_offset_x = min(all_xs)
    grid_offset_y = min(all_ys)

    print(f'Auto-detected cell size: {cell_size} pixels')
    print(f'Grid has {len(xs_unique)}x{len(ys_unique)} cells')
    print(f'Pixel offsets: x={grid_offset_x}, y={grid_offset_y}')

    # Second pass: extract blocks, keeping only last block for each coordinate
    blocks_dict = {}  # (layer, x, z) -> block data

    for layer_str, layer_blocks in layermap.items():
        layer_num = int(layer_str)

        for block in layer_blocks:
            pixel_x = block['x']
            pixel_y = block['y']
            material = block['h']

            grid_x, grid_z = pixel_to_grid(pixel_x, pixel_y, cell_size,
                                           grid_offset_x, grid_offset_y)

            # Store or overwrite (last block wins for duplicates)
            if grid_x >= 0 and grid_z >= 0:
                key = (layer_num, grid_x, grid_z)
                blocks_dict[key] = {
                    'layer': layer_num,
                    'x': grid_x,
                    'z': grid_z,
                    'y': layer_num,
                    'material': material
                }

    # Convert to list
    blocks = list(blocks_dict.values())
    blocks.sort(key=lambda b: (b['layer'], b['z'], b['x']))
    print(f'Extracted {len(blocks)} blocks (duplicates merged)')

    # Detect compass rotation from HTML
    rotation = detect_compass_rotation_from_html(html)

    if rotation != 0:
        print(f'Applying {rotation}° rotation to all blocks...')

        # Calculate grid dimensions (before rotation)
        max_x = max(b['x'] for b in blocks)
        max_z = max(b['z'] for b in blocks)
        width = max_x + 1
        depth = max_z + 1

        # Apply rotation to all blocks
        rotated_blocks = []
        for b in blocks:
            # Rotate coordinates only - block directions are already correct relative to compass
            new_x, new_z = rotate_coordinates(b['x'], b['z'], rotation, width, depth)

            rotated_blocks.append({
                'layer': b['layer'],
                'x': new_x,
                'z': new_z,
                'y': b['y'],
                'material': b['material']
            })

        blocks = rotated_blocks
        blocks.sort(key=lambda b: (b['layer'], b['z'], b['x']))
        print(f'Rotation applied: {len(blocks)} blocks')

    return blocks


# ============================================================================
# COMMAND GENERATION FUNCTIONS
# ============================================================================

def get_block_id(material: str) -> str | None:
    if not material or not material.strip():
        return None
    bedrock_id = convert_grabcraft_to_bedrock(material)
    if bedrock_id:
        return bedrock_id
    else:
        return None


def is_attachable_block(material: str) -> bool:
    """Check if block needs to be attached to another block (place last)."""
    block_id = get_block_id(material)
    if block_id is None:
        return False
    attachable = ['ladder', 'torch', 'wall_torch']
    for b in attachable:
        if b in block_id:
            return True
    return False


def generate_commands(blocks: list[dict]) -> list[str]:
    """Generate Minecraft /setblock commands for all blocks."""
    commands = []
    attachable_commands = []
    skipped = 0

    for b in blocks:
        block_id = get_block_id(b['material'])
        if block_id is None:
            skipped += 1
            continue

        cmd = f'/setblock {b["x"]} {b["y"]} {b["z"]} {block_id}'
        if is_attachable_block(b['material']):
            attachable_commands.append(cmd)
        else:
            commands.append(cmd)

    # Add attachable blocks at the end (they need support blocks first)
    commands.extend(attachable_commands)

    if skipped > 0:
        print(f'Skipped {skipped} blocks with invalid/empty materials')

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


if __name__ == '__main__':
    main()
