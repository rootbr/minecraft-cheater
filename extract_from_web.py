#!/usr/bin/env python3
"""
Extract Minecraft block data from GrabCraft web page.
Parses the LayerMap JS file to get exact block positions and materials.
"""

import csv
import json
import re
import sys
from urllib.request import urlopen, Request


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
    # Extract JSON object from: var layerMap = {...};
    match = re.search(r'var\s+layerMap\s*=\s*(\{.*\})\s*;?\s*$', js_content, re.DOTALL)
    if not match:
        raise ValueError("Could not find layerMap in JS content")

    json_str = match.group(1)
    return json.loads(json_str)


def pixel_to_grid(pixel_x: int, pixel_y: int, cell_size: int = 20,
                  grid_offset_x: int = 5, grid_offset_y: int = 291) -> tuple[int, int]:
    """
    Convert pixel coordinates to grid coordinates.
    Based on analysis of the LayerMap data:
    - x starts at 5, increments by 20 (cell_size)
    - y starts at 291 (top of grid), increments by 20 going down (z axis)
    """
    # Normalize to grid coordinates
    # X axis: pixel x -> grid x
    grid_x = (pixel_x - grid_offset_x) // cell_size

    # Z axis: pixel y -> grid z (y in image = z in minecraft)
    grid_z = (pixel_y - grid_offset_y) // cell_size

    return grid_x, grid_z


def extract_blocks(layermap: dict, dim_x: int, dim_z: int) -> list[dict]:
    """Extract all blocks from layermap data."""
    blocks = []

    # Analyze the data to find grid parameters
    # From the data: x values are 5, 25, 45, 65, 85, 105, 125, 145, 165, 185, 205
    # That's 11 columns with spacing of 20, starting at 5
    # y values range from 291 to 491, that's 11 rows with spacing of 20

    cell_size = 20
    grid_offset_x = 5
    grid_offset_y = 291  # top row of the plan grid in image

    for layer_str, layer_blocks in layermap.items():
        layer_num = int(layer_str)

        for block in layer_blocks:
            pixel_x = block['x']
            pixel_y = block['y']
            material = block['h']

            # Convert pixel coords to grid coords
            grid_x, grid_z = pixel_to_grid(pixel_x, pixel_y, cell_size,
                                           grid_offset_x, grid_offset_y)

            # Validate coordinates are within expected grid
            if 0 <= grid_x < dim_x and 0 <= grid_z < dim_z:
                blocks.append({
                    'layer': layer_num,
                    'x': grid_x,
                    'z': grid_z,
                    'y': layer_num,
                    'material': material
                })

    # Sort by layer, then z, then x
    blocks.sort(key=lambda b: (b['layer'], b['z'], b['x']))

    return blocks


def main():
    page_url = 'https://www.grabcraft.com/minecraft/oakshire-wall-tower/military-buildings'
    output_csv = 'blocks_web.csv'

    if len(sys.argv) > 1:
        page_url = sys.argv[1]
    if len(sys.argv) > 2:
        output_csv = sys.argv[2]

    print(f'Fetching page: {page_url}')
    html = fetch_page(page_url)

    # Extract dimensions
    dim_x, dim_y, dim_z = extract_dimensions(html)
    print(f'Dimensions: {dim_x}x{dim_y}x{dim_z} (X x Y x Z)')

    # Find LayerMap JS URL
    layermap_url = extract_layermap_url(html)
    if not layermap_url:
        print('Error: Could not find LayerMap JS URL in page')
        sys.exit(1)

    print(f'Fetching LayerMap: {layermap_url}')
    js_content = fetch_page(layermap_url)

    # Parse LayerMap
    print('Parsing layer data...')
    layermap = parse_layermap_js(js_content)
    print(f'Found {len(layermap)} layers')

    # Extract blocks
    blocks = extract_blocks(layermap, dim_x, dim_z)

    # Write output CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['layer', 'x', 'z', 'y', 'material'])
        writer.writeheader()
        writer.writerows(blocks)

    print(f'\nTotal: {len(blocks)} blocks written to {output_csv}')

    # Print material summary
    from collections import Counter
    materials = Counter(b['material'] for b in blocks)
    print('\nMaterials:')
    for mat, count in materials.most_common():
        print(f'  {mat}: {count}')


if __name__ == '__main__':
    main()
