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

1. Load settings from `config.toml` (or custom config file via `--config`)
2. Load commands from file (configured in `execution.file`)
3. Apply coordinate offsets (configured in `coordinates` section)
4. Wait 3 seconds for user to switch to Minecraft window
5. For each command:
   - Apply offset to coordinates
   - Copy modified command to clipboard
   - Press `T` to open chat
   - Paste with Cmd+V
   - Press Enter to execute
   - Automatic detection of chat state for optimal timing

### Configuration

Configuration is managed through TOML file (`config.toml` by default).

**Configuration file structure:**

```toml
[execution]
file = "build_commands_optimized.txt"  # Command file to execute
skip = 0                                # Skip first N commands
# material = "stone_stairs"             # Filter by material (optional)

[coordinates]
offset_x = 0  # X coordinate offset
offset_y = 0  # Y coordinate offset
offset_z = 0  # Z coordinate offset
```

**Files:**
- `config.toml` - Active configuration (not tracked in git)
- `config.example.toml` - Example configuration with detailed comments

**Staircase constants in `staircase.rs`:**
- `START_X`, `START_Y`, `START_Z` - starting coordinates
- `DIRECTION` - build direction (east/west/north/south)
- `MATERIAL` - block material (supports modded blocks like `spark:*`)
- `FLIGHT_HEIGHT`, `WIDTH` - staircase dimensions
- `WALL_MATERIAL`, `LANTERN`, `LANTERN_INTERVAL` - decorative options

## CLI Usage

### Basic Usage

All settings are configured in `config.toml`:

```bash
# Run with default config (config.toml)
./target/release/mc-commander

# Use custom config file
./target/release/mc-commander --config my-build.toml
./target/release/mc-commander -c tower.toml

# Generate staircase (ignores config file)
./target/release/mc-commander staircase
```

### Configuration Examples

**Basic build:**
```toml
[execution]
file = "build_commands_optimized.txt"
```

**Resume interrupted build at command 1500:**
```toml
[execution]
file = "build_commands_optimized.txt"
skip = 1500
```

**Build with coordinate offset:**
```toml
[execution]
file = "house.txt"

[coordinates]
offset_x = 100
offset_y = 64
offset_z = -50
```

**Filter by material (build only stone stairs):**
```toml
[execution]
file = "castle.txt"
material = "stone_stairs"
```

**Full combination:**
```toml
[execution]
file = "tower.txt"
skip = 500
material = "oak"

[coordinates]
offset_x = 100
offset_y = 70
offset_z = 200
```

### CLI Options

- `--config FILE` (or `-c FILE`) - Configuration file to use (default: `config.toml`)

### Execution Order

1. Load configuration from TOML file
2. Read commands from file (specified in config)
3. Calculate bounding box and clear commands (based on all commands)
4. Apply `skip` (skip first N commands)
5. Apply `material` filter (filter remaining commands by material)
6. Execute clear commands (only if skip=0 and no material filter)
7. Execute filtered commands with coordinate offsets

**Note:** When using `skip` to resume an interrupted build, the area clearing step is automatically skipped since the area was already cleared during the initial run.

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

**✨ Automatic Compass Rotation Detection:** Script automatically detects compass orientation on GrabCraft pages and rotates the entire structure so that North always points UP. This ensures consistent building orientation regardless of how the blueprint was originally oriented on the website.

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

**Compass Rotation:**
The script automatically detects the compass orientation from the webpage's HTML and applies rotation to coordinates. Block directions remain unchanged as they are already correct relative to the compass.

- **Coordinates:** X/Z coordinates rotated around structure center
- **Block Directions:** Preserved as-is (already correct relative to compass)

Supported rotations:
- **0°** - North UP (standard, no rotation applied)
- **90°** - North LEFT → coordinates rotated 90° CCW
- **180°** - North DOWN → coordinates rotated 180°
- **270°** - North RIGHT → coordinates rotated 90° CW

Example output:
```
Compass detected: North is LEFT -> 90° rotation
Applying 90° rotation to all blocks...
Rotation applied: 609 blocks
```

### optimize_commands.py

Optimizes existing command files by merging /setblock into /fill and applying offsets.

```bash
# Basic optimization
python3 optimize_commands.py input.txt

# With output file
python3 optimize_commands.py input.txt output.txt
```

### export_pipeline_csv.py

Export full pipeline from GrabCraft to CSV with all transformation stages. Shows original blocks, Bedrock conversion, optimization, and verification.

```bash
# Export pipeline to CSV
python3 export_pipeline_csv.py <GRABCRAFT_URL> [output.csv]

# Example
python3 export_pipeline_csv.py https://www.grabcraft.com/.../house house_pipeline.csv
```

**CSV Columns:**
- `x, y, z` - Coordinates (after rotation)
- `original_material` - GrabCraft block name
- `bedrock_block` - Bedrock Edition ID with states
- `optimized_block` - Block after optimization and expansion
- `match` - ✓ if bedrock and optimized match

**Generated files:**
- `*_bedrock.txt` - Unoptimized Bedrock commands
- `*_optimized.txt` - Optimized commands with /fill
- `*.csv` - Full pipeline data sorted by coordinates

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
- `weirdo_direction`: 1=north, 0=south, 2=west, 3=east

Supported: oak, spruce, birch, jungle, acacia, dark_oak, cobblestone, stone_brick

### Slabs

```
minecraft:stone_slab["minecraft:vertical_half"="bottom"]
```

- `"bottom"` or `"top"`
- Double slabs convert to full blocks (e.g., Double Stone Slab → smooth_stone)

### Ladders / Torches / Chests

```
minecraft:ladder["facing_direction"=0]
minecraft:wall_torch["facing_direction"=1]
minecraft:chest["facing_direction"=2]
```

- `facing_direction`: 0=north, 1=south, 3=west, 2=east

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
- Resume with `--skip <number>` (area clearing will be automatically skipped)

**Stop execution:**
- Press Ctrl+C in terminal

## Notes

- Designed for Parallels Desktop running Windows + Minecraft Bedrock
- Uses clipboard for special characters in block names
- Tested with builds up to 41,000+ blocks
