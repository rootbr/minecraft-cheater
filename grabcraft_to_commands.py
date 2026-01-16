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
    'Oak Wood (facing north/south)': 'minecraft:oak_log["pillar_axis"="y"]',
    'Oak Wood (facing east/west)': 'minecraft:oak_log["pillar_axis"="x"]',
    'Oak Wood Plank': 'minecraft:oak_planks',
    'Spruce Wood': 'minecraft:spruce_log',
    'Spruce Wood Plank': 'minecraft:spruce_planks',
    'Birch Wood': 'minecraft:birch_log',
    'Birch Wood Plank': 'minecraft:birch_planks',
    'Jungle Wood': 'minecraft:jungle_log',
    'Jungle Wood Plank': 'minecraft:jungle_planks',
    'Acacia Wood': 'minecraft:acacia_log',
    'Acacia Wood Plank': 'minecraft:acacia_planks',
    'Acacia Leaves': 'minecraft:acacia_leaves["persistent_bit"=true]',
    'Acacia Leaves (No Decay)': 'minecraft:acacia_leaves["persistent_bit"=true]',
    'Acacia Leaves (No Decay and Check Decay)': 'minecraft:acacia_leaves["persistent_bit"=true]',
    'Dark Oak Wood': 'minecraft:dark_oak_log',
    'Dark Oak Wood Plank': 'minecraft:dark_oak_planks',
    'Iron Block': 'minecraft:iron_block',
    'Glowstone': 'minecraft:glowstone',
    'Glass': 'minecraft:glass',
    'Quartz Block': 'minecraft:quartz_block',
    'Bookshelf': 'minecraft:bookshelf',
    'Beacon': 'minecraft:beacon',
    'Iron Bars': 'minecraft:iron_bars',
    'Rail': 'minecraft:rail',
    'Rail (curved; north and east)': 'minecraft:rail',
    'Rail (curved; south and east)': 'minecraft:rail',
    'Rail (curved; north and west)': 'minecraft:rail',
    'Rail (curved; south and west)': 'minecraft:rail',
    'Flower Pot': 'minecraft:flower_pot',
    'Flower (Rose Bush, Lower)': 'minecraft:rose_bush',
    'Flower (Lilac, Upper)': 'minecraft:lilac',
    'Flower (Sunflower, Upper)': 'minecraft:sunflower',
    'Dandelion Flower Pot': 'minecraft:flower_pot',
    'Cobblestone Wall': 'minecraft:cobblestone_wall',

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

    # Terracotta (Stained Clay)
    'White Stained Clay': 'minecraft:white_terracotta',
    'Black Stained Clay': 'minecraft:black_terracotta',
    'Gray Stained Clay': 'minecraft:gray_terracotta',
    'Light Gray Stained Clay': 'minecraft:light_gray_terracotta',
    'Brown Stained Clay': 'minecraft:brown_terracotta',
    'Red Stained Clay': 'minecraft:red_terracotta',
    'Orange Stained Clay': 'minecraft:orange_terracotta',
    'Yellow Stained Clay': 'minecraft:yellow_terracotta',
    'Lime Stained Clay': 'minecraft:lime_terracotta',
    'Green Stained Clay': 'minecraft:green_terracotta',
    'Cyan Stained Clay': 'minecraft:cyan_terracotta',
    'Light Blue Stained Clay': 'minecraft:light_blue_terracotta',
    'Blue Stained Clay': 'minecraft:blue_terracotta',
    'Purple Stained Clay': 'minecraft:purple_terracotta',
    'Magenta Stained Clay': 'minecraft:magenta_terracotta',
    'Pink Stained Clay': 'minecraft:pink_terracotta',

    # Fences
    'Oak Fence': 'minecraft:oak_fence',
    'Spruce Fence': 'minecraft:spruce_fence',
    'Birch Fence': 'minecraft:birch_fence',
    'Jungle Fence': 'minecraft:jungle_fence',
    'Acacia Fence': 'minecraft:acacia_fence',
    'Dark Oak Fence': 'minecraft:dark_oak_fence',

    # Slabs (Bedrock: top_slot_bit determines position)
    'Stone Slab': 'minecraft:stone_slab["minecraft:vertical_half"="bottom"]',
    'Stone Slab (Upper)': 'minecraft:stone_slab["minecraft:vertical_half"="top"]',
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

    # Doors (Bedrock Edition: oak_door -> wooden_door, direction 0-3, upper_block_bit)
    # Note: Doors have 2 blocks - lower (upper_block_bit=false) and upper (upper_block_bit=true)
    'Oak Door (Lower)': 'minecraft:wooden_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Oak Door (Upper)': 'minecraft:wooden_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',
    'Spruce Door (Lower)': 'minecraft:spruce_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Spruce Door (Upper)': 'minecraft:spruce_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',
    'Birch Door (Lower)': 'minecraft:birch_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Birch Door (Upper)': 'minecraft:birch_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',
    'Jungle Door (Lower)': 'minecraft:jungle_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Jungle Door (Upper)': 'minecraft:jungle_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',
    'Acacia Door (Lower)': 'minecraft:acacia_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Acacia Door (Upper)': 'minecraft:acacia_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',
    'Dark Oak Door (Lower)': 'minecraft:dark_oak_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Dark Oak Door (Upper)': 'minecraft:dark_oak_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',
    'Iron Door (Lower)': 'minecraft:iron_door["direction"=2,"open_bit"=false,"upper_block_bit"=false]',
    'Iron Door (Upper)': 'minecraft:iron_door["direction"=2,"open_bit"=false,"upper_block_bit"=true]',

    # Chests (Bedrock Edition uses numeric facing_direction: 0=north, 1=south, 3=west, 2=east)
    'Chest (North)': 'minecraft:chest["facing_direction"=0]',
    'Chest (South)': 'minecraft:chest["facing_direction"=1]',
    'Chest (East)': 'minecraft:chest["facing_direction"=2]',
    'Chest (West)': 'minecraft:chest["facing_direction"=3]',

    # Ladders (Bedrock Edition uses numeric facing_direction: 0=north, 1=south, 3=west, 2=east)
    'Ladder (facing north)': 'minecraft:ladder["facing_direction"=0]',
    'Ladder (facing south)': 'minecraft:ladder["facing_direction"=1]',
    'Ladder (facing east)': 'minecraft:ladder["facing_direction"=2]',
    'Ladder (facing west)': 'minecraft:ladder["facing_direction"=3]',

    # Torches (Bedrock: all torches use minecraft:torch, not wall_torch)
    'Torch (Facing Up)': 'minecraft:torch',
    'Torch (Facing North)': 'minecraft:torch',
    'Torch (Facing South)': 'minecraft:torch',
    'Torch (Facing East)': 'minecraft:torch',
    'Torch (Facing West)': 'minecraft:torch',

    # Oak Wood Stairs - Normal (Bedrock: upside_down_bit=false for normal, weirdo_direction for facing)
    #  weirdo_direction: 1=north, 0=south, 2=west, 3=east)
    'Oak Wood Stairs (North, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Oak Wood Stairs (South, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=0]',
    'Oak Wood Stairs (East, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=3]',
    'Oak Wood Stairs (West, Normal)': 'minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=2]',

    # Oak Wood Stairs - Upside-down (Bedrock: upside_down_bit=true for top)
    'Oak Wood Stairs (North, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Oak Wood Stairs (South, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=0]',
    'Oak Wood Stairs (East, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=3]',
    'Oak Wood Stairs (West, Upside-down)': 'minecraft:oak_stairs["upside_down_bit"=true,"weirdo_direction"=2]',

    # Cobblestone Stairs - Normal (Bedrock: uses stone_stairs, upside_down_bit=false for normal, weirdo_direction for facing)
    'Cobblestone Stairs (North, Normal)': 'minecraft:stone_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Cobblestone Stairs (South, Normal)': 'minecraft:stone_stairs["upside_down_bit"=false,"weirdo_direction"=3]',
    'Cobblestone Stairs (East, Normal)': 'minecraft:stone_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Cobblestone Stairs (West, Normal)': 'minecraft:stone_stairs["upside_down_bit"=false,"weirdo_direction"=0]',

    # Cobblestone Stairs - Upside-down (Bedrock: uses stone_stairs, upside_down_bit=true for top)
    'Cobblestone Stairs (North, Upside-down)': 'minecraft:stone_stairs["upside_down_bit"=true,"weirdo_direction"=2]',
    'Cobblestone Stairs (South, Upside-down)': 'minecraft:stone_stairs["upside_down_bit"=true,"weirdo_direction"=3]',
    'Cobblestone Stairs (East, Upside-down)': 'minecraft:stone_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Cobblestone Stairs (West, Upside-down)': 'minecraft:stone_stairs["upside_down_bit"=true,"weirdo_direction"=0]',

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

    # Acacia Wood Stairs - Normal
    'Acacia Wood Stairs (North, Normal)': 'minecraft:acacia_stairs["upside_down_bit"=false,"weirdo_direction"=0]',
    'Acacia Wood Stairs (South, Normal)': 'minecraft:acacia_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Acacia Wood Stairs (East, Normal)': 'minecraft:acacia_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Acacia Wood Stairs (West, Normal)': 'minecraft:acacia_stairs["upside_down_bit"=false,"weirdo_direction"=3]',

    # Acacia Wood Stairs - Upside-down
    'Acacia Wood Stairs (North, Upside-down)': 'minecraft:acacia_stairs["upside_down_bit"=true,"weirdo_direction"=0]',
    'Acacia Wood Stairs (South, Upside-down)': 'minecraft:acacia_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Acacia Wood Stairs (East, Upside-down)': 'minecraft:acacia_stairs["upside_down_bit"=true,"weirdo_direction"=2]',
    'Acacia Wood Stairs (West, Upside-down)': 'minecraft:acacia_stairs["upside_down_bit"=true,"weirdo_direction"=3]',

    # Quartz Stairs - Normal
    'Quartz Stairs (North, Normal)': 'minecraft:quartz_stairs["upside_down_bit"=false,"weirdo_direction"=0]',
    'Quartz Stairs (South, Normal)': 'minecraft:quartz_stairs["upside_down_bit"=false,"weirdo_direction"=1]',
    'Quartz Stairs (East, Normal)': 'minecraft:quartz_stairs["upside_down_bit"=false,"weirdo_direction"=2]',
    'Quartz Stairs (West, Normal)': 'minecraft:quartz_stairs["upside_down_bit"=false,"weirdo_direction"=3]',

    # Quartz Stairs - Upside-down
    'Quartz Stairs (North, Upside-down)': 'minecraft:quartz_stairs["upside_down_bit"=true,"weirdo_direction"=0]',
    'Quartz Stairs (South, Upside-down)': 'minecraft:quartz_stairs["upside_down_bit"=true,"weirdo_direction"=1]',
    'Quartz Stairs (East, Upside-down)': 'minecraft:quartz_stairs["upside_down_bit"=true,"weirdo_direction"=2]',
    'Quartz Stairs (West, Upside-down)': 'minecraft:quartz_stairs["upside_down_bit"=true,"weirdo_direction"=3]',
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

def get_block_id(material: str) -> str:
    """Convert material name to Minecraft block ID."""
    if material in MATERIAL_TO_BLOCK:
        return MATERIAL_TO_BLOCK[material]

    # Try to auto-convert unknown materials
    block_name = material.lower().replace(' ', '_')

    # Fix common naming issues
    # GrabCraft uses "wood_plank" but Bedrock uses "planks"
    block_name = block_name.replace('_wood_plank', '_planks')
    block_name = block_name.replace('wood_plank', 'planks')

    # Special handling for doors
    if 'door' in block_name.lower():
        # Remove everything after first opening parenthesis (handles malformed data)
        if '(' in block_name:
            base_name = block_name.split('(')[0].strip('_')
        else:
            base_name = block_name.strip('_')
        # Bedrock uses wooden_door for oak doors
        base_name = base_name.replace('oak_door', 'wooden_door')
        # Add default door state if not present
        if '[' not in base_name:
            # Check if upper or lower part
            if 'upper' in material.lower():
                base_name += '["direction"=2,"open_bit"=false,"upper_block_bit"=true]'
            else:
                base_name += '["direction"=2,"open_bit"=false,"upper_block_bit"=false]'
        return f'minecraft:{base_name}'

    # Special handling for stairs with default orientation
    if 'stairs' in block_name.lower():
        # Remove everything after first opening parenthesis
        if '(' in block_name:
            base_name = block_name.split('(')[0].strip('_')
        else:
            base_name = block_name.strip('_')
        # Map common wood types and stone variants
        base_name = base_name.replace('oak_wood_stairs', 'oak_stairs')
        base_name = base_name.replace('spruce_wood_stairs', 'spruce_stairs')
        base_name = base_name.replace('birch_wood_stairs', 'birch_stairs')
        base_name = base_name.replace('jungle_wood_stairs', 'jungle_stairs')
        base_name = base_name.replace('acacia_wood_stairs', 'acacia_stairs')
        base_name = base_name.replace('dark_oak_wood_stairs', 'dark_oak_stairs')
        # Bedrock uses stone_stairs, not cobblestone_stairs
        base_name = base_name.replace('cobblestone_stairs', 'stone_stairs')
        # Add default Bedrock state
        return f'minecraft:{base_name}["upside_down_bit"=false,"weirdo_direction"=3]'

    # Remove everything after first opening parenthesis for other blocks
    if '(' in block_name:
        block_name = block_name.split('(')[0].strip('_')
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
