#!/usr/bin/env python3
"""
Optimize Minecraft command files by merging setblock commands into fill commands.
Uses layer-by-layer rectangular area detection.
"""

import re
import sys
from collections import defaultdict


def parse_command(line: str) -> dict | None:
    """Parse a /setblock or /fill command."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    # Parse /setblock x y z block
    match = re.match(r'/setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$', line)
    if match:
        return {
            'x': int(match.group(1)),
            'y': int(match.group(2)),
            'z': int(match.group(3)),
            'block': match.group(4)
        }

    # Parse /fill x1 y1 z1 x2 y2 z2 block (expand to individual blocks)
    match = re.match(
        r'/fill\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$',
        line
    )
    if match:
        x1, y1, z1 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        x2, y2, z2 = int(match.group(4)), int(match.group(5)), int(match.group(6))
        block = match.group(7)

        # Expand fill to individual blocks
        blocks = []
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    blocks.append({'x': x, 'y': y, 'z': z, 'block': block})
        return blocks

    return None


def read_commands(input_file: str) -> dict:
    """Read commands and build 3D grid of blocks."""
    grid = {}  # (x, y, z) -> block_id

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            result = parse_command(line)
            if result:
                if isinstance(result, list):
                    # Expanded fill command
                    for block in result:
                        grid[(block['x'], block['y'], block['z'])] = block['block']
                else:
                    # Single setblock
                    grid[(result['x'], result['y'], result['z'])] = result['block']

    return grid


def can_use_fill(block_id: str) -> bool:
    """Check if block can be used with /fill command."""
    # Blocks with block states cannot be reliably filled
    if '[' in block_id:
        return False

    # Attachable blocks should use setblock
    no_fill_blocks = ['ladder', 'torch', 'wall_torch', 'chest', 'door',
                      'lever', 'button', 'vine', 'rail']
    for b in no_fill_blocks:
        if b in block_id.lower():
            return False

    return True


def is_attachable_block(block_id: str) -> bool:
    """Check if block needs to be attached to another block."""
    attachable = ['ladder', 'torch', 'wall_torch', 'vine', 'lever', 'rail']
    for b in attachable:
        if b in block_id.lower():
            return True
    return False


def find_rectangles_in_layer(layer_blocks: list, processed: set) -> list:
    """Find rectangular areas with same material in a single Y layer."""
    # Group by material
    by_material = defaultdict(list)
    for x, z, block_id in layer_blocks:
        if (x, z) not in processed and can_use_fill(block_id):
            by_material[block_id].append((x, z))

    fill_regions = []

    # For each material, find rectangles
    for block_id, coords in by_material.items():
        coords_set = set(coords)
        coords_sorted = sorted(coords_set)

        while coords_sorted:
            # Start with first unprocessed coordinate
            x_start, z_start = coords_sorted[0]

            if (x_start, z_start) not in coords_set:
                coords_sorted.pop(0)
                continue

            # Find maximum x extent at this z
            x_end = x_start
            while (x_end + 1, z_start) in coords_set:
                x_end += 1

            # Try to extend in z direction
            z_end = z_start
            can_extend = True
            while can_extend:
                z_next = z_end + 1
                # Check if entire row exists at z_next
                for x in range(x_start, x_end + 1):
                    if (x, z_next) not in coords_set:
                        can_extend = False
                        break
                if can_extend:
                    z_end = z_next

            # Found a rectangle
            area = (x_end - x_start + 1) * (z_end - z_start + 1)

            if area >= 4:  # Only create fill for 2x2 or larger
                fill_regions.append((x_start, z_start, x_end, z_end, block_id))

                # Mark as processed
                for x in range(x_start, x_end + 1):
                    for z in range(z_start, z_end + 1):
                        coords_set.discard((x, z))
                        processed.add((x, z))
            else:
                # Too small, don't create fill
                coords_set.discard((x_start, z_start))

            # Rebuild sorted list
            coords_sorted = sorted(coords_set)

    return fill_regions


def optimize_grid(grid: dict) -> tuple[list, list]:
    """Optimize grid using layer-by-layer rectangular area detection."""
    # Group blocks by Y level
    by_y = defaultdict(list)
    for (x, y, z), block_id in grid.items():
        by_y[y].append((x, z, block_id))

    fill_commands = []
    setblock_commands = []
    attachable_commands = []

    # Process each Y layer
    for y in sorted(by_y.keys()):
        layer_blocks = by_y[y]
        processed = set()  # (x, z) coordinates processed in this layer

        # Find rectangles in this layer
        rectangles = find_rectangles_in_layer(layer_blocks, processed)

        # Generate fill commands for rectangles
        for x1, z1, x2, z2, block_id in rectangles:
            fill_commands.append(f'/fill {x1} {y} {z1} {x2} {y} {z2} {block_id}')

        # Generate setblock for remaining blocks
        for x, z, block_id in layer_blocks:
            if (x, z) not in processed:
                cmd = f'/setblock {x} {y} {z} {block_id}'
                if is_attachable_block(block_id):
                    attachable_commands.append(cmd)
                else:
                    setblock_commands.append(cmd)

    # Combine commands: fills first, then setblocks, then attachables last
    all_commands = fill_commands + setblock_commands + attachable_commands
    return all_commands, (len(fill_commands), len(setblock_commands + attachable_commands))


def apply_offset(commands: list, offset_x: int, offset_y: int, offset_z: int) -> list:
    """Apply coordinate offsets to commands."""
    if offset_x == 0 and offset_y == 0 and offset_z == 0:
        return commands

    result = []
    for cmd in commands:
        if cmd.startswith('/fill '):
            match = re.match(
                r'/fill\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$',
                cmd
            )
            if match:
                x1 = int(match.group(1)) + offset_x
                y1 = int(match.group(2)) + offset_y
                z1 = int(match.group(3)) + offset_z
                x2 = int(match.group(4)) + offset_x
                y2 = int(match.group(5)) + offset_y
                z2 = int(match.group(6)) + offset_z
                block = match.group(7)
                result.append(f'/fill {x1} {y1} {z1} {x2} {y2} {z2} {block}')
            else:
                result.append(cmd)
        elif cmd.startswith('/setblock '):
            match = re.match(r'/setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$', cmd)
            if match:
                x = int(match.group(1)) + offset_x
                y = int(match.group(2)) + offset_y
                z = int(match.group(3)) + offset_z
                block = match.group(4)
                result.append(f'/setblock {x} {y} {z} {block}')
            else:
                result.append(cmd)
        else:
            result.append(cmd)

    return result


def main():
    input_file = None
    output_file = None
    offset_x = 0
    offset_y = 0
    offset_z = 0
    use_optimization = True

    args = sys.argv[1:]
    i = 0
    positional = []

    while i < len(args):
        if args[i] in ('-h', '--help'):
            print('Usage: optimize_commands.py INPUT [OUTPUT] [options]')
            print()
            print('Optimize Minecraft command files by merging /setblock into /fill.')
            print('Uses layer-by-layer rectangular area detection.')
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
            use_optimization = False
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
        if '.' in input_file:
            base, ext = input_file.rsplit('.', 1)
            output_file = f'{base}_optimized.{ext}'
        else:
            output_file = f'{input_file}_optimized'

    # Read input into 3D grid
    print(f'Reading: {input_file}')
    grid = read_commands(input_file)
    print(f'Parsed {len(grid)} blocks')

    # Optimize or just convert to commands
    if use_optimization:
        print('Optimizing with layer-by-layer rectangle detection...')
        commands, (fill_count, setblock_count) = optimize_grid(grid)
    else:
        print('Converting without optimization...')
        commands = []
        for (x, y, z), block_id in sorted(grid.items()):
            commands.append(f'/setblock {x} {y} {z} {block_id}')
        fill_count = 0
        setblock_count = len(commands)

    # Apply offsets
    if offset_x != 0 or offset_y != 0 or offset_z != 0:
        print(f'Applying offset: ({offset_x}, {offset_y}, {offset_z})')
        commands = apply_offset(commands, offset_x, offset_y, offset_z)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    # Summary
    print(f'\nOutput: {output_file}')
    print(f'Total commands: {len(commands)}')
    print(f'  /fill: {fill_count}')
    print(f'  /setblock: {setblock_count}')

    if len(grid) > 0:
        reduction = (1 - len(commands) / len(grid)) * 100
        print(f'Reduction: {reduction:.1f}% ({len(grid)} -> {len(commands)})')


if __name__ == '__main__':
    main()
