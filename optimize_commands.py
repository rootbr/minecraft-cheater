#!/usr/bin/env python3
"""
Optimize Minecraft command files by merging setblock commands into fill commands.
Also supports applying coordinate offsets.

Takes a file with /setblock commands and outputs optimized /fill + /setblock commands.
"""

import re
import sys
from collections import defaultdict


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_setblock(line: str) -> dict | None:
    """Parse a /setblock command and return block info."""
    line = line.strip()
    if not line.startswith('/setblock '):
        return None

    # /setblock x y z block_id[states]
    match = re.match(r'/setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$', line)
    if not match:
        return None

    return {
        'x': int(match.group(1)),
        'y': int(match.group(2)),
        'z': int(match.group(3)),
        'block': match.group(4)
    }


def parse_fill(line: str) -> dict | None:
    """Parse a /fill command and return fill info."""
    line = line.strip()
    if not line.startswith('/fill '):
        return None

    # /fill x1 y1 z1 x2 y2 z2 block_id[states]
    match = re.match(
        r'/fill\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$',
        line
    )
    if not match:
        return None

    return {
        'x1': int(match.group(1)),
        'y1': int(match.group(2)),
        'z1': int(match.group(3)),
        'x2': int(match.group(4)),
        'y2': int(match.group(5)),
        'z2': int(match.group(6)),
        'block': match.group(7)
    }


def read_commands(input_file: str) -> list[dict]:
    """Read commands from file and parse into blocks list."""
    blocks = []

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Try parsing as setblock
            block = parse_setblock(line)
            if block:
                blocks.append({
                    'x': block['x'],
                    'y': block['y'],
                    'z': block['z'],
                    'material': block['block']
                })
                continue

            # Try parsing as fill (expand to individual blocks)
            fill = parse_fill(line)
            if fill:
                for x in range(min(fill['x1'], fill['x2']), max(fill['x1'], fill['x2']) + 1):
                    for y in range(min(fill['y1'], fill['y2']), max(fill['y1'], fill['y2']) + 1):
                        for z in range(min(fill['z1'], fill['z2']), max(fill['z1'], fill['z2']) + 1):
                            blocks.append({
                                'x': x,
                                'y': y,
                                'z': z,
                                'material': fill['block']
                            })

    return blocks


# ============================================================================
# OPTIMIZATION FUNCTIONS
# ============================================================================

def can_use_fill(block_id: str) -> bool:
    """Check if block can be used with /fill command."""
    if '[' in block_id:
        return False
    no_fill_blocks = ['ladder', 'torch', 'wall_torch', 'chest', 'door', 'lever', 'button']
    for b in no_fill_blocks:
        if b in block_id.lower():
            return False
    return True


def is_attachable_block(block_id: str) -> bool:
    """Check if block needs to be attached to another block."""
    attachable = ['ladder', 'torch', 'wall_torch', 'vine', 'lever']
    for b in attachable:
        if b in block_id.lower():
            return True
    return False


def find_cuboids(material: str, coords: set, fill_regions: list, used_blocks: set) -> set:
    """Find 3D cuboid regions."""
    remaining = coords.copy()
    coords_list = sorted(remaining)

    for x, y, z in coords_list:
        if (x, y, z) not in remaining:
            continue

        max_x, max_y, max_z = x, y, z

        while (max_x + 1, y, z) in remaining:
            max_x += 1

        can_expand_z = True
        while can_expand_z and (x, y, max_z + 1) in remaining:
            for check_x in range(x, max_x + 1):
                if (check_x, y, max_z + 1) not in remaining:
                    can_expand_z = False
                    break
            if can_expand_z:
                max_z += 1

        can_expand_y = True
        while can_expand_y and (x, max_y + 1, z) in remaining:
            for check_x in range(x, max_x + 1):
                for check_z in range(z, max_z + 1):
                    if (check_x, max_y + 1, check_z) not in remaining:
                        can_expand_y = False
                        break
                if not can_expand_y:
                    break
            if can_expand_y:
                max_y += 1

        volume = (max_x - x + 1) * (max_y - y + 1) * (max_z - z + 1)
        if volume >= 8:
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
    by_y = defaultdict(list)
    for x, y, z in remaining:
        by_y[y].append((x, z))

    for y, xz_coords in by_y.items():
        xz_set = set(xz_coords)
        xz_sorted = sorted(xz_set)

        for x, z in xz_sorted:
            if (x, z) not in xz_set:
                continue

            max_x = x
            while (max_x + 1, z) in xz_set:
                max_x += 1

            max_z = z
            can_expand = True
            while can_expand:
                max_z += 1
                for check_x in range(x, max_x + 1):
                    if (check_x, max_z) not in xz_set:
                        can_expand = False
                        max_z -= 1
                        break

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


def find_fill_regions(blocks: list[dict]) -> tuple[list[tuple], set]:
    """Find regions of same material that can use /fill command."""
    by_material = defaultdict(list)
    for b in blocks:
        if can_use_fill(b['material']):
            by_material[b['material']].append((b['x'], b['y'], b['z']))

    fill_regions = []
    used_blocks = set()

    for material, coords in by_material.items():
        remaining = set(coords) - used_blocks
        remaining = find_cuboids(material, remaining, fill_regions, used_blocks)
        remaining = find_rectangles(material, remaining, fill_regions, used_blocks)
        remaining = find_horizontal_lines(material, remaining, fill_regions, used_blocks)
        remaining = find_vertical_columns(material, remaining, fill_regions, used_blocks)

    return fill_regions, used_blocks


# ============================================================================
# COMMAND GENERATION
# ============================================================================

def generate_commands(blocks: list[dict], offset_x: int = 0, offset_y: int = 0,
                      offset_z: int = 0, use_fill: bool = True) -> list[str]:
    """Generate optimized Minecraft commands."""
    commands = []
    attachable_commands = []

    if use_fill:
        fill_regions, used_blocks = find_fill_regions(blocks)

        for x1, y1, z1, x2, y2, z2, material in fill_regions:
            cmd = f'/fill {x1 + offset_x} {y1 + offset_y} {z1 + offset_z} ' \
                  f'{x2 + offset_x} {y2 + offset_y} {z2 + offset_z} {material}'
            commands.append(cmd)

        for b in blocks:
            key = (b['x'], b['y'], b['z'], b['material'])
            if key not in used_blocks:
                cmd = f'/setblock {b["x"] + offset_x} {b["y"] + offset_y} ' \
                      f'{b["z"] + offset_z} {b["material"]}'
                if is_attachable_block(b['material']):
                    attachable_commands.append(cmd)
                else:
                    commands.append(cmd)
    else:
        for b in blocks:
            cmd = f'/setblock {b["x"] + offset_x} {b["y"] + offset_y} ' \
                  f'{b["z"] + offset_z} {b["material"]}'
            if is_attachable_block(b['material']):
                attachable_commands.append(cmd)
            else:
                commands.append(cmd)

    commands.extend(attachable_commands)
    return commands


# ============================================================================
# MAIN
# ============================================================================

def main():
    input_file = None
    output_file = None
    offset_x = 0
    offset_y = 0
    offset_z = 0
    use_fill = True

    args = sys.argv[1:]
    i = 0
    positional = []

    while i < len(args):
        if args[i] in ('-h', '--help'):
            print('Usage: optimize_commands.py INPUT [OUTPUT] [options]')
            print()
            print('Optimize Minecraft command files by merging /setblock into /fill.')
            print()
            print('Arguments:')
            print('  INPUT               Input file with /setblock commands')
            print('  OUTPUT              Output file (default: INPUT with _optimized suffix)')
            print()
            print('Options:')
            print('  -x N                X offset to add (default: 0)')
            print('  -y N                Y offset to add (default: 0)')
            print('  -z N                Z offset to add (default: 0)')
            print('  --no-fill           Skip optimization, only apply offset')
            print()
            print('Examples:')
            print('  python3 optimize_commands.py garden.txt')
            print('  python3 optimize_commands.py garden.txt garden_opt.txt')
            print('  python3 optimize_commands.py garden.txt -x 100 -y 64 -z 200')
            print('  python3 optimize_commands.py garden.txt --no-fill -y 10')
            sys.exit(0)
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
        elif not args[i].startswith('-'):
            positional.append(args[i])
            i += 1
        else:
            print(f'Unknown option: {args[i]}')
            sys.exit(1)

    if len(positional) < 1:
        print('Error: Input file required')
        print('Use -h for help')
        sys.exit(1)

    input_file = positional[0]
    if len(positional) >= 2:
        output_file = positional[1]
    else:
        # Generate output filename
        if '.' in input_file:
            base, ext = input_file.rsplit('.', 1)
            output_file = f'{base}_optimized.{ext}'
        else:
            output_file = f'{input_file}_optimized'

    # Read and parse input
    print(f'Reading: {input_file}')
    blocks = read_commands(input_file)
    print(f'Parsed {len(blocks)} blocks')

    # Generate commands
    offset_str = f'({offset_x}, {offset_y}, {offset_z})'
    if offset_x != 0 or offset_y != 0 or offset_z != 0:
        print(f'Applying offset: {offset_str}')

    if use_fill:
        print('Optimizing with /fill...')

    commands = generate_commands(blocks, offset_x, offset_y, offset_z, use_fill)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    # Summary
    fill_count = sum(1 for c in commands if c.startswith('/fill'))
    setblock_count = sum(1 for c in commands if c.startswith('/setblock'))

    print(f'\nOutput: {output_file}')
    print(f'Total commands: {len(commands)}')
    print(f'  /fill: {fill_count}')
    print(f'  /setblock: {setblock_count}')

    if len(blocks) > 0:
        reduction = (1 - len(commands) / len(blocks)) * 100
        print(f'Reduction: {reduction:.1f}% ({len(blocks)} -> {len(commands)})')


if __name__ == '__main__':
    main()
