#!/usr/bin/env python3
"""
Expand optimized Minecraft commands back to individual /setblock commands.
Used to verify that optimization preserves all blocks correctly.
"""

import re
import sys


def expand_to_setblocks(input_file: str) -> dict:
    """Expand /fill commands to individual /setblock, simulating execution order."""
    blocks = {}

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            m = re.match(r'/setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$', line)
            if m:
                pos = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                blocks[pos] = m.group(4)
                continue

            m = re.match(
                r'/fill\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$',
                line
            )
            if m:
                x1, y1, z1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
                x2, y2, z2 = int(m.group(4)), int(m.group(5)), int(m.group(6))
                block = m.group(7)
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    for y in range(min(y1, y2), max(y1, y2) + 1):
                        for z in range(min(z1, z2), max(z1, z2) + 1):
                            blocks[(x, y, z)] = block

    return blocks


def parse_setblocks(input_file: str) -> dict:
    """Parse file with only /setblock commands."""
    blocks = {}

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            m = re.match(r'/setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(.+)$', line)
            if m:
                pos = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                blocks[pos] = m.group(4)

    return blocks


def compare_files(original_file: str, optimized_file: str) -> bool:
    """Compare original and optimized files, return True if identical."""
    print(f'Original:  {original_file}')
    original = parse_setblocks(original_file)
    print(f'  Blocks: {len(original)}')

    print(f'Optimized: {optimized_file}')
    expanded = expand_to_setblocks(optimized_file)
    print(f'  Blocks: {len(expanded)}')

    orig_pos = set(original.keys())
    exp_pos = set(expanded.keys())

    missing = orig_pos - exp_pos
    extra = exp_pos - orig_pos

    print(f'\nPosition comparison:')
    print(f'  Missing: {len(missing)}')
    print(f'  Extra:   {len(extra)}')

    if missing:
        print(f'  First missing: {list(missing)[:5]}')
    if extra:
        print(f'  First extra: {list(extra)[:5]}')

    mismatches = [
        (p, original[p], expanded[p])
        for p in original
        if p in expanded and original[p] != expanded[p]
    ]

    print(f'\nBlock type comparison:')
    if mismatches:
        print(f'  Mismatches: {len(mismatches)}')
        for pos, orig, exp in mismatches[:5]:
            print(f'    {pos}:')
            print(f'      original:  {orig}')
            print(f'      optimized: {exp}')
        return False
    else:
        print('  All block types match!')

    if len(missing) == 0 and len(extra) == 0:
        print('\n✓ Files are IDENTICAL')
        return True
    else:
        print('\n✗ Files DIFFER')
        return False


def main():
    if len(sys.argv) < 3:
        print('Usage: expand_commands.py ORIGINAL OPTIMIZED')
        print()
        print('Compare original setblock file with optimized file.')
        print('Expands /fill commands and verifies all blocks match.')
        sys.exit(1)

    original_file = sys.argv[1]
    optimized_file = sys.argv[2]

    success = compare_files(original_file, optimized_file)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
