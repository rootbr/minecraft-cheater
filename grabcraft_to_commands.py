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
import argparse
from collections import Counter
from urllib.request import urlopen, Request
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from grabcraft_to_bedrock import convert_grabcraft_to_bedrock, get_converter

# ============================================================================
# COMPASS ROTATION DETECTION
# ============================================================================

def _find_compass_container(html: str) -> Optional[str]:
    match = re.search(r'<div[^>]*class=["\']compass-container["\'][^>]*>(.*?)</div>', 
                      html, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None

def _extract_north_span(compass_html: str) -> Optional[Tuple[str, str]]:
    # Try ID then Class
    match = re.search(r'<span[^>]*id=["\']([^"\']+)["\'][^>]*class=["\']([^"\']*)["\'][^>]*>N</span>', 
                      compass_html, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)
    # Try Class then ID
    match = re.search(r'<span[^>]*class=["\']([^"\']*)["\'][^>]*id=["\']([^"\']+)["\'][^>]*>N</span>', 
                      compass_html, re.IGNORECASE)
    if match:
        return match.group(2), match.group(1)
    return None

def detect_compass_rotation_from_html(html: str) -> int:
    """Detect compass orientation from HTML compass container."""
    compass_html = _find_compass_container(html)
    if not compass_html:
        return 0

    north_info = _extract_north_span(compass_html)
    if not north_info:
        return 0

    north_id, _ = north_info
    rotation_map = {'north': 0, 'west': 90, 'east': 270, 'south': 180}
    rotation = rotation_map.get(north_id, 0)

    direction_names = {
        'north': 'UP (standard)',
        'west': 'LEFT',
        'east': 'RIGHT',
        'south': 'DOWN'
    }
    direction_name = direction_names.get(north_id, north_id.upper())

    print(f'✓ Compass: North points {direction_name} → {rotation}° rotation needed')
    return rotation


def rotate_coordinates(x: int, z: int, rotation: int, width: int, depth: int) -> tuple[int, int]:
    """
    Rotate structure coordinates to align North to standard orientation (UP).

    This physically rotates the entire structure so that regardless of the compass
    orientation on GrabCraft, North always points "up" (positive Z direction) in
    the final coordinates. Block orientations (stairs, doors, etc.) remain unchanged
    as they are already correct relative to their local coordinate system.

    Args:
        x, z: Original grid coordinates
        rotation: Rotation angle in degrees (0, 90, 180, 270)
        width, depth: Grid dimensions before rotation

    Returns:
        (new_x, new_z): Rotated coordinates with North aligned to UP
    """
    if rotation == 0:
        return x, z
    elif rotation == 90:
        # 90° CW: North was LEFT, now UP
        return depth - z - 1, x
    elif rotation == 180:
        # 180°: North was DOWN, now UP
        return width - x - 1, depth - z - 1
    elif rotation == 270:
        # 90° CCW: North was RIGHT, now UP
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

    # Extract dimensions (from GrabCraft page, before rotation)
    orig_dim_x, orig_dim_y, orig_dim_z = extract_dimensions(html)
    print(f'Original dimensions: {orig_dim_x}W x {orig_dim_y}H x {orig_dim_z}D (as shown on GrabCraft)')

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
    print(f'Extracted {len(blocks)} blocks (duplicates merged)')

    # Detect compass rotation from HTML
    print('\nDetecting compass orientation...')
    rotation = detect_compass_rotation_from_html(html)

    # Rotate coordinates to align North to standard orientation
    if rotation != 0:
        print(f'Rotating structure coordinates by {rotation}°...')
        print(f'Grid before rotation: {len(xs_unique)}W x {len(ys_unique)}D')

        for b in blocks:
            new_x, new_z = rotate_coordinates(b['x'], b['z'], rotation, len(xs_unique), len(ys_unique))
            b['x'] = new_x
            b['z'] = new_z

        print(f'✓ Structure rotated - North now points UP')
        print(f'Block directions remain unchanged (relative to structure)')
    else:
        print('✓ No rotation needed (North already points UP)')

    # Calculate final dimensions after rotation
    if rotation == 90 or rotation == 270:
        # Width and depth are swapped
        final_x = orig_dim_z  # West-East
        final_z = orig_dim_x  # South-North
    else:
        final_x = orig_dim_x  # West-East
        final_z = orig_dim_z  # South-North
    final_y = orig_dim_y  # Height

    print(f'\n📐 Final structure dimensions:')
    print(f'   {final_x} blocks (West ⬅ to East ➡, X-axis)')
    print(f'   {final_y} blocks (Bottom to Top, Y-axis)')
    print(f'   {final_z} blocks (South ⬇ to North ⬆, Z-axis)')
    print(f'   Total volume: {final_x * final_y * final_z} blocks')

    print('\n📍 Cardinal directions in Minecraft Bedrock Edition:')
    print('   • Z decreases (-Z) → NORTH ⬆')
    print('   • Z increases (+Z) → SOUTH ⬇')
    print('   • X decreases (-X) → WEST ⬅')
    print('   • X increases (+X) → EAST ➡')
    print('   • Sun rises in the EAST, sets in the WEST')

    # Sort blocks after rotation: layer by layer, south to north, west to east
    blocks.sort(key=lambda b: (b['layer'], b['z'], b['x']))

    return blocks


# ============================================================================
# COMMAND GENERATION FUNCTIONS
# ============================================================================

def get_block_id(material: str, x: Optional[int] = None, y: Optional[int] = None,
                 z: Optional[int] = None, layer: Optional[int] = None) -> str | None:
    if not material or not material.strip():
        return None
    bedrock_id = convert_grabcraft_to_bedrock(material, x, y, z, layer)
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
    converter = get_converter()
    converter.clear_door_cache()

    # Pass 1: Register all door upper blocks
    for b in blocks:
        if 'door' in b['material'].lower() and 'upper' in b['material'].lower():
            converter.register_door_upper_block(b['x'], b['y'], b['z'], b['layer'], b['material'])

    commands = []
    attachable_commands = []
    skipped = 0

    for b in blocks:
        block_id = get_block_id(b['material'], b['x'], b['y'], b['z'], b['layer'])
        if block_id is None or block_id.startswith('__SKIP__'):
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
        print(f'✓ Skipped {skipped} blocks (auto-generated parts like bed feet)')

    return commands


# ============================================================================
# MAIN
# ============================================================================

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert GrabCraft blueprint to Minecraft Bedrock Edition commands.'
    )
    parser.add_argument('url', help='GrabCraft page URL')
    parser.add_argument('-o', '--output', default='build_commands.txt', 
                        help='Output file (default: build_commands.txt)')
    parser.add_argument('--save-csv', nargs='?', const='blocks.csv', 
                        help='Save blocks to CSV file (default: blocks.csv)')
    return parser.parse_args()

def main():
    args = parse_arguments()

    # Fetch blocks from web
    try:
        blocks = extract_blocks_from_web(args.url)
    except Exception as e:
        print(f"\n✗ Error fetching blueprint: {e}")
        sys.exit(1)

    # Print summary
    print('\n' + '=' * 60)
    print('MATERIAL SUMMARY')
    print('=' * 60)
    materials = Counter(b['material'] for b in blocks)
    print(f'Unique materials: {len(materials)}')
    print(f'\nTop 10 materials:')
    for mat, count in materials.most_common(10):
        print(f'  • {mat}: {count}')
    if len(materials) > 10:
        print(f'  ... and {len(materials) - 10} more')

    # Save CSV if requested
    if args.save_csv:
        _save_blocks_to_csv(blocks, args.save_csv)

    # Generate commands
    print('\n' + '=' * 60)
    print('GENERATING MINECRAFT COMMANDS')
    print('=' * 60)
    commands = generate_commands(blocks)

    # Write output
    print(f'\nWriting commands to file...')
    with open(args.output, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    print(f'✓ Generated {len(commands)} commands')
    print(f'✓ Saved to: {args.output}')
    print('\n' + '=' * 60)
    print('CONVERSION COMPLETE')
    print('=' * 60)

def _save_blocks_to_csv(blocks: List[Dict], filename: str):
    """Save block data to CSV."""
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['layer', 'x', 'z', 'y', 'material'])
        writer.writeheader()
        writer.writerows(blocks)
    print(f'\nSaved blocks to {filename}')


if __name__ == '__main__':
    main()
