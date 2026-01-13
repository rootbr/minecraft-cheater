#!/usr/bin/env python3
"""
Extract layer plans from GrabCraft blueprint images.
Parses the bottom-left plan grid, matches colors to materials, outputs CSV.
"""

import csv
import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library required. Install with: pip install Pillow")
    sys.exit(1)


def load_materials(csv_path: str) -> dict[str, str]:
    """Load materials CSV and return color -> material mapping."""
    color_to_material = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            color = row['color'].lower()
            material = row['material']
            # Store color without # for easier matching
            color_key = color.lstrip('#')
            color_to_material[color_key] = material
    return color_to_material


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex string (without #)."""
    return f'{r:02x}{g:02x}{b:02x}'


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> int:
    """Calculate simple color distance."""
    return sum(abs(a - b) for a, b in zip(c1, c2))


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex string to RGB tuple."""
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def find_closest_material(pixel_rgb: tuple[int, int, int],
                          color_to_material: dict[str, str],
                          threshold: int = 50) -> str | None:
    """Find closest matching material by color distance."""
    # Check for air/empty (white, light gray, or blue background)
    r, g, b = pixel_rgb

    # Blue background color (approximately #1e6eb8 or similar)
    if b > 150 and b > r and b > g:
        return None  # Air/empty

    # White or very light = air
    if r > 240 and g > 240 and b > 240:
        return None

    # Light gray background
    if r > 200 and g > 200 and b > 200 and abs(r - g) < 20 and abs(g - b) < 20:
        return None

    best_match = None
    best_distance = threshold

    for hex_color, material in color_to_material.items():
        mat_rgb = hex_to_rgb(hex_color)
        dist = color_distance(pixel_rgb, mat_rgb)
        if dist < best_distance:
            best_distance = dist
            best_match = material

    return best_match


def find_grid_bounds(img: Image.Image) -> tuple[int, int, int, int]:
    """
    Find the bottom-left plan grid bounds.
    Returns (left, top, right, bottom) of the grid area.
    """
    width, height = img.size

    # The plan is in bottom-left quadrant
    # Based on images: grid starts around x=0-10, ends around x=220
    # y starts around height/2, ends near bottom

    # Scan to find the colored grid area (non-blue region in bottom-left)
    pixels = img.load()

    # Find left edge of grid (first non-blue column in bottom half)
    left = 0
    for x in range(width // 2):
        for y in range(height // 2, height):
            r, g, b = pixels[x, y][:3]
            # Not blue background
            if not (b > 150 and b > r + 30 and b > g + 30):
                left = x
                break
        else:
            continue
        break

    # Find top edge of grid
    top = height // 2
    for y in range(height // 2, height):
        for x in range(left, width // 2):
            r, g, b = pixels[x, y][:3]
            if not (b > 150 and b > r + 30 and b > g + 30):
                top = y
                break
        else:
            continue
        break

    # Find right edge
    right = width // 2
    for x in range(width // 2, left, -1):
        found = False
        for y in range(top, height):
            r, g, b = pixels[x, y][:3]
            if not (b > 150 and b > r + 30 and b > g + 30):
                found = True
                break
        if found:
            right = x + 1
            break

    # Find bottom edge
    bottom = height
    for y in range(height - 1, top, -1):
        found = False
        for x in range(left, right):
            r, g, b = pixels[x, y][:3]
            if not (b > 150 and b > r + 30 and b > g + 30):
                found = True
                break
        if found:
            bottom = y + 1
            break

    return left, top, right, bottom


def extract_grid(img: Image.Image, grid_size: tuple[int, int] = (11, 11)) -> list[list[tuple[int, int, int]]]:
    """
    Extract the color grid from bottom-left plan area.
    Returns 2D array of RGB colors for each cell.
    """
    left, top, right, bottom = find_grid_bounds(img)

    grid_width = right - left
    grid_height = bottom - top

    cell_width = grid_width / grid_size[0]
    cell_height = grid_height / grid_size[1]

    pixels = img.load()
    grid = []

    for row in range(grid_size[1]):
        grid_row = []
        for col in range(grid_size[0]):
            # Sample center of each cell
            center_x = int(left + (col + 0.5) * cell_width)
            center_y = int(top + (row + 0.5) * cell_height)

            # Get average color from small area around center
            colors = []
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    x = min(max(center_x + dx, 0), img.width - 1)
                    y = min(max(center_y + dy, 0), img.height - 1)
                    pixel = pixels[x, y]
                    colors.append(pixel[:3])

            # Average color
            avg_r = sum(c[0] for c in colors) // len(colors)
            avg_g = sum(c[1] for c in colors) // len(colors)
            avg_b = sum(c[2] for c in colors) // len(colors)

            grid_row.append((avg_r, avg_g, avg_b))
        grid.append(grid_row)

    return grid


def process_layer(img_path: str, layer_num: int,
                  color_to_material: dict[str, str],
                  grid_size: tuple[int, int] = (11, 11)) -> list[dict]:
    """Process a single layer image and return block data."""
    img = Image.open(img_path).convert('RGB')
    grid = extract_grid(img, grid_size)

    blocks = []
    for z, row in enumerate(grid):
        for x, pixel_rgb in enumerate(row):
            material = find_closest_material(pixel_rgb, color_to_material)
            if material:
                blocks.append({
                    'layer': layer_num,
                    'x': x,
                    'z': z,
                    'y': layer_num,
                    'material': material,
                    'color': '#' + rgb_to_hex(*pixel_rgb)
                })

    return blocks


def main():
    blueprints_dir = 'blueprints/4349_Oakshire_Wall_Tower/Y'
    materials_csv = 'materials.csv'
    output_csv = 'blocks.csv'
    grid_size = (11, 11)  # Width x Depth from object properties

    if len(sys.argv) > 1:
        blueprints_dir = sys.argv[1]
    if len(sys.argv) > 2:
        materials_csv = sys.argv[2]
    if len(sys.argv) > 3:
        output_csv = sys.argv[3]

    print(f'Loading materials from {materials_csv}')
    color_to_material = load_materials(materials_csv)
    print(f'Loaded {len(color_to_material)} material colors')

    # Find all layer images
    layer_files = sorted(
        Path(blueprints_dir).glob('*.png'),
        key=lambda p: int(p.stem)
    )

    if not layer_files:
        print(f'No PNG files found in {blueprints_dir}')
        sys.exit(1)

    print(f'Found {len(layer_files)} layer images')

    all_blocks = []
    for img_path in layer_files:
        layer_num = int(img_path.stem)
        print(f'Processing layer {layer_num}...', end=' ')

        blocks = process_layer(str(img_path), layer_num, color_to_material, grid_size)
        all_blocks.extend(blocks)
        print(f'{len(blocks)} blocks')

    # Write output CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['layer', 'x', 'z', 'y', 'material', 'color'])
        writer.writeheader()
        writer.writerows(all_blocks)

    print(f'\nTotal: {len(all_blocks)} blocks written to {output_csv}')


if __name__ == '__main__':
    main()
