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

from grabcraft_to_bedrock import convert_grabcraft_to_bedrock

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
    print('\nNote: Use mc-commander with --offset-x/y/z to apply coordinate offsets when executing.')


if __name__ == '__main__':
    main()
