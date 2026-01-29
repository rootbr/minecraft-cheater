#!/usr/bin/env python3
"""
Optimize Minecraft command files by merging setblock commands into fill commands.
Uses layer-by-layer rectangular area detection.
"""

import re
import sys
from collections import Counter


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
    # Attachable blocks should use setblock
    no_fill_blocks = ['ladder', 'torch', 'wall_torch', 'chest', 'door',
                      'lever', 'button', 'vine', 'rail']
    for b in no_fill_blocks:
        if b in block_id.lower():
            return False

    return True


def is_attachable_block(block_id: str) -> bool:
    """Check if block needs to be attached to another block."""
    attachable = ['ladder', 'torch', 'wall_torch', 'vine', 'lever', 'rail', 'water']
    for b in attachable:
        if b in block_id.lower():
            return True
    return False


def find_best_cuboid(grid: dict, processed: set, start_p: tuple, block_id: str) -> tuple:
    """Find a good cuboid starting from a single point by expanding faces greedily."""
    x1, y1, z1 = start_p
    x2, y2, z2 = start_p
    
    current_matches = 1
    current_mismatches = 0
    
    while True:
        best_profit = -1
        best_move = None
        
        # Possible moves: (axis, direction, delta)
        # axis: 0=x, 1=y, 2=z; direction: -1 or 1
        moves = [
            (0, -1), (0, 1),
            (1, -1), (1, 1),
            (2, -1), (2, 1)
        ]
        
        for axis, direction in moves:
            matches = 0
            mismatches = 0
            has_blocker = False  # Empty space or already-processed position

            if axis == 0:  # X
                nx = x1 - 1 if direction == -1 else x2 + 1
                for ny in range(y1, y2 + 1):
                    for nz in range(z1, z2 + 1):
                        p = (nx, ny, nz)
                        if p in processed or p not in grid:
                            has_blocker = True
                        elif grid[p] == block_id:
                            matches += 1
                        else:
                            mismatches += 1
            elif axis == 1:  # Y
                ny = y1 - 1 if direction == -1 else y2 + 1
                for nx in range(x1, x2 + 1):
                    for nz in range(z1, z2 + 1):
                        p = (nx, ny, nz)
                        if p in processed or p not in grid:
                            has_blocker = True
                        elif grid[p] == block_id:
                            matches += 1
                        else:
                            mismatches += 1
            else:  # Z
                nz = z1 - 1 if direction == -1 else z2 + 1
                for nx in range(x1, x2 + 1):
                    for ny in range(y1, y2 + 1):
                        p = (nx, ny, nz)
                        if p in processed or p not in grid:
                            has_blocker = True
                        elif grid[p] == block_id:
                            matches += 1
                        else:
                            mismatches += 1

            if has_blocker:
                continue

            # Profit: matches saved minus mismatches that need correction
            profit = matches - mismatches
            if profit > best_profit and matches > 0:
                best_profit = profit
                best_move = (axis, direction, matches, mismatches)
        
        if best_move and best_profit >= 0:
            axis, direction, m, mm = best_move
            if axis == 0:
                if direction == -1: x1 -= 1
                else: x2 += 1
            elif axis == 1:
                if direction == -1: y1 -= 1
                else: y2 += 1
            else:
                if direction == -1: z1 -= 1
                else: z2 += 1
            current_matches += m
            current_mismatches += mm
        else:
            break
            
    return (x1, y1, z1, x2, y2, z2, current_matches)

def find_cuboids_for_material(grid: dict, processed: set, block_id: str) -> list:
    """Find cuboids for a specific material using greedy expansion."""
    material_coords = [p for p, b in grid.items() if b == block_id and p not in processed]
    if not material_coords:
        return []
    
    material_coords.sort()
    found_regions = []
    
    for p in material_coords:
        if p in processed:
            continue
            
        x1, y1, z1, x2, y2, z2, matches = find_best_cuboid(grid, processed, p, block_id)
        
        # Only use fill if it's profitable (saves at least 1 command)
        # Cost of fill = 1. Cost of individual setblocks = matches. 
        # New cost = 1 + (number of mismatches in this box)
        # But we don't know mismatches directly, let's use matches > 1.
        if matches >= 2:
            found_regions.append((x1, y1, z1, x2, y2, z2, block_id))
            # Mark blocks as processed
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    for z in range(z1, z2 + 1):
                        p_in = (x, y, z)
                        if grid.get(p_in) == block_id:
                            processed.add(p_in)
                            
    return found_regions

def optimize_grid(grid: dict) -> tuple[list, list]:
    """Optimize grid using multi-pass material-frequency-based greedy cuboid detection."""
    processed = set()
    fill_commands = []
    setblock_commands = []
    attachable_commands = []

    # 1. Count material frequency (only for fillable blocks)
    material_counts = Counter()
    for p, block_id in grid.items():
        if can_use_fill(block_id):
            material_counts[block_id] += 1

    # 2. Process materials from most frequent to least frequent
    total_materials = len(material_counts)
    print(f'Processing {total_materials} unique materials...')

    processed_count = 0
    for block_id, count in material_counts.most_common():
        processed_count += 1
        if processed_count % 10 == 0 or processed_count == 1 or processed_count == total_materials:
            print(f'  [{processed_count}/{total_materials}] Processing material with {count} blocks...')

        regions = find_cuboids_for_material(grid, processed, block_id)
        for r in regions:
            fill_commands.append(f'/fill {r[0]} {r[1]} {r[2]} {r[3]} {r[4]} {r[5]} {r[6]}')

    print(f'✓ Processed all materials')

    # 3. Generate setblock for remaining unprocessed blocks
    print(f'Processing remaining individual blocks...')
    for (x, y, z), block_id in grid.items():
        if (x, y, z) not in processed:
            cmd = f'/setblock {x} {y} {z} {block_id}'
            if is_attachable_block(block_id):
                attachable_commands.append(cmd)
            else:
                setblock_commands.append(cmd)

    # Combine commands: fills first, then setblocks, then attachables last
    # Move all water commands to the very end as requested
    water_from_fill = [c for c in fill_commands if 'water' in c.lower()]
    remaining_fill = [c for c in fill_commands if 'water' not in c.lower()]

    water_from_setblock = [c for c in setblock_commands if 'water' in c.lower()]
    remaining_setblock = [c for c in setblock_commands if 'water' not in c.lower()]

    water_from_attachable = [c for c in attachable_commands if 'water' in c.lower()]
    remaining_attachable = [c for c in attachable_commands if 'water' not in c.lower()]

    all_commands = (remaining_fill + remaining_setblock + remaining_attachable +
                    water_from_fill + water_from_setblock + water_from_attachable)
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
    print('=' * 60)
    print('MINECRAFT COMMAND OPTIMIZER')
    print('=' * 60)

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
    print(f'\nReading input file...')
    print(f'  File: {input_file}')
    grid = read_commands(input_file)
    print(f'✓ Parsed {len(grid)} blocks')

    # Optimize or just convert to commands
    if use_optimization:
        print('\n' + '=' * 60)
        print('OPTIMIZING COMMANDS')
        print('=' * 60)
        print('Using 3D cuboid and rectangle detection...')
        commands, (fill_count, setblock_count) = optimize_grid(grid)
        print(f'✓ Optimization complete')
    else:
        print('\nConverting without optimization...')
        commands = []
        for (x, y, z), block_id in sorted(grid.items()):
            commands.append(f'/setblock {x} {y} {z} {block_id}')
        fill_count = 0
        setblock_count = len(commands)

    # Apply offsets
    if offset_x != 0 or offset_y != 0 or offset_z != 0:
        print(f'\nApplying coordinate offset: ({offset_x}, {offset_y}, {offset_z})')
        commands = apply_offset(commands, offset_x, offset_y, offset_z)
        print(f'✓ Offset applied')

    # Write output
    print(f'\nWriting output file...')
    with open(output_file, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    # Summary
    print('\n' + '=' * 60)
    print('OPTIMIZATION SUMMARY')
    print('=' * 60)
    print(f'Output file: {output_file}')
    print(f'\nCommand breakdown:')
    print(f'  • /fill commands:     {fill_count}')
    print(f'  • /setblock commands: {setblock_count}')
    print(f'  • Total:              {len(commands)}')

    if len(grid) > 0:
        reduction = (1 - len(commands) / len(grid)) * 100
        print(f'\nOptimization result:')
        print(f'  • Original: {len(grid)} commands')
        print(f'  • Optimized: {len(commands)} commands')
        print(f'  • Reduction: {reduction:.1f}%')

    print('\n' + '=' * 60)
    print('OPTIMIZATION COMPLETE')
    print('=' * 60)

    print('\n📍 Reminder - Cardinal directions in Minecraft:')
    print('   Z- → NORTH ⬆  |  Z+ → SOUTH ⬇')
    print('   X- → WEST  ⬅  |  X+ → EAST  ➡')


if __name__ == '__main__':
    main()
