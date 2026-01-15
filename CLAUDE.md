# CLAUDE.md

## Project Overview

**mc-commander** is a Rust CLI tool for generating and auto-executing Minecraft **Bedrock Edition** commands via keyboard emulation. Designed for macOS with Minecraft running in Parallels Desktop.

## Technology Stack

- **Language**: Rust 2021 edition
- **CLI Framework**: clap 4.5 with derive macros
- **Keyboard Emulation**: enigo 0.2
- **Clipboard**: arboard 3.4
- **Python Scripts**: grabcraft_to_commands.py, optimize_commands.py
- **Target Platform**: macOS (uses Meta key for Cmd+V)
- **Target Game**: Minecraft Bedrock Edition

## Installation

### Rust CLI

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build
cargo build --release

# Executable: target/release/mc-commander
```

### macOS Permissions

**Required:** System Settings → Privacy & Security → Accessibility
- Add Terminal (or your terminal app)
- Add IDE if running from there

## Architecture

### Rust Modules

- `main.rs` - CLI parsing, command execution loop, keyboard automation
- `staircase.rs` - Staircase structure generator with configurable parameters

### Command Execution Flow

1. Generate or load commands from `build_commands.mcfunction`
2. Apply coordinate offsets (if specified via `--offset-x/y/z`)
3. Wait 5 seconds for user to switch to Minecraft window
4. For each command:
   - Apply offset to coordinates
   - Copy modified command to clipboard
   - Press `T` to open chat
   - Paste with Cmd+V
   - Press Enter to execute
   - Press Escape to close chat

### Configuration

Hardcoded constants in `main.rs`:
- `START_X`, `START_Y`, `START_Z` - starting coordinates
- `DIRECTION` - build direction (east/west/north/south)
- `MATERIAL` - block material (supports modded blocks like `spark:*`)
- `FLIGHT_HEIGHT`, `WIDTH` - staircase dimensions
- `WALL_MATERIAL`, `LANTERN`, `LANTERN_INTERVAL` - decorative options

## CLI Usage

```bash
# Run from file (default: build_commands.mcfunction)
./target/release/mc-commander

# Skip first N commands (resume interrupted build)
./target/release/mc-commander --skip 600
./target/release/mc-commander -s 600

# Apply coordinate offsets
./target/release/mc-commander --offset-x 100 --offset-y 64 --offset-z -50

# Combine skip and offset
./target/release/mc-commander --skip 500 --offset-x 100 --offset-y 70 --offset-z 200

# Generate staircase
./target/release/mc-commander staircase
```

**Options:**
- `--skip N` (or `-s N`) - Skip first N commands
- `--offset-x N` - X coordinate offset (default: 0)
- `--offset-y N` - Y coordinate offset (default: 0)
- `--offset-z N` - Z coordinate offset (default: 0)

## File Structure

```
src/
├── main.rs                  # CLI and execution engine
└── staircase.rs             # Staircase command generator
grabcraft_to_commands.py     # GrabCraft blueprint converter
optimize_commands.py         # Command optimizer (fill merge + offset)
build_commands.mcfunction    # Command input file (generated or manual)
```

## Python Scripts

### grabcraft_to_commands.py

Converts blueprints from [GrabCraft.com](https://www.grabcraft.com) to Minecraft Bedrock Edition commands with base coordinates (no offset applied).

```bash
# Basic usage
python3 grabcraft_to_commands.py <URL>

# Custom output file
python3 grabcraft_to_commands.py <URL> -o my_tower.mcfunction

# Save CSV for analysis
python3 grabcraft_to_commands.py <URL> --save-csv blocks.csv
```

**Options:**
- `-o FILE` - Output file (default: build_commands.txt)
- `--save-csv [FILE]` - Save blocks to CSV

### optimize_commands.py

Optimizes existing command files by merging /setblock into /fill and applying offsets.

```bash
# Basic optimization
python3 optimize_commands.py input.txt

# With output file
python3 optimize_commands.py input.txt output.txt

# Apply offset
python3 optimize_commands.py input.txt -x 100 -y 64 -z 200

# Offset only (no optimization)
python3 optimize_commands.py input.txt --no-fill -y 10
```

### Command Optimization

Both scripts optimize commands in priority order:
1. 3D cuboids (2x2x2+) → single `/fill`
2. 2D rectangles (2x2+) → single `/fill`
3. Horizontal lines (2+ blocks) → single `/fill`
4. Vertical columns (2+ blocks) → single `/fill`
5. Single blocks → `/setblock`

Attachable blocks (ladders, torches, vines) are placed last.

**Typical reduction: 30-70% fewer commands**

## Bedrock Edition Block States

Scripts use correct Bedrock Edition syntax. Key differences from Java:

### Stairs

```
minecraft:oak_stairs["upside_down_bit"=false,"weirdo_direction"=0]
```

- `upside_down_bit`: `false` = normal, `true` = upside-down
- `weirdo_direction`: 0=west, 1=east, 2=north, 3=south

Supported: oak, spruce, birch, jungle, acacia, dark_oak, cobblestone, stone_brick

### Slabs

```
minecraft:stone_slab["minecraft:vertical_half"="bottom"]
```

- `"bottom"` or `"top"`
- Double slabs convert to full blocks (e.g., Double Stone Slab → smooth_stone)

### Ladders / Torches / Chests

```
minecraft:ladder["facing_direction"=2]
minecraft:wall_torch["facing_direction"=3]
minecraft:chest["facing_direction"=5]
```

- `facing_direction`: 2=north, 3=south, 4=west, 5=east

### Logs (with axis)

```
minecraft:oak_log["pillar_axis"="y"]
```

- `"x"`, `"y"`, or `"z"`

### Doors

```
minecraft:oak_door["direction"=0,"open_bit"=false,"upper_block_bit"=false]
```

- `direction`: 0=south, 1=west, 2=north, 3=east
- `upper_block_bit`: `false`=lower, `true`=upper

### Leaves

```
minecraft:oak_leaves["persistent_bit"=true]
```

- `persistent_bit`: `true` = won't decay

### Vines

```
minecraft:vine["vine_direction_bits"=4]
```

- Bitmask: 1=south, 2=west, 4=north, 8=east

## Command File Format

```mcfunction
# Comments start with #
/fill 0 64 0 10 64 10 minecraft:stone
/setblock 5 65 5 minecraft:torch

# Lines starting with = are skipped (separators)
===============================
```

## Troubleshooting

**Commands not typing:**
- Check Accessibility permissions in System Settings
- Ensure Minecraft window is active

**Interrupted build:**
- Note the last command number
- Resume with `--skip <number>`

**Stop execution:**
- Press Ctrl+C in terminal

## Notes

- Designed for Parallels Desktop running Windows + Minecraft Bedrock
- Uses clipboard for special characters in block names
- Tested with builds up to 41,000+ blocks
