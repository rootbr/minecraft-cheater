# CLAUDE.md

## Project Overview

**mc-commander** is a Rust CLI tool for generating and auto-executing Minecraft **Bedrock Edition** commands via keyboard emulation. It is designed to run on macOS with Minecraft running in Parallels Desktop.

## Technology Stack

- **Language**: Rust 2021 edition
- **CLI Framework**: clap 4.5 with derive macros
- **Keyboard Emulation**: enigo 0.2
- **Clipboard**: arboard 3.4
- **Target Platform**: macOS (uses Meta key for Cmd+V)
- **Target Game**: Minecraft Bedrock Edition

## Architecture

### Modules

- `main.rs` - CLI parsing, command execution loop, keyboard automation
- `staircase.rs` - Staircase structure generator with configurable parameters

### Command Execution Flow

1. Generate or load commands from `build_commands.mcfunction`
2. Wait 5 seconds for user to switch to Minecraft window
3. For each command:
   - Copy command to clipboard
   - Press `T` to open chat
   - Paste with Cmd+V
   - Press Enter to execute

### Configuration

Hardcoded constants in `main.rs`:
- `START_X`, `START_Y`, `START_Z` - starting coordinates
- `DIRECTION` - build direction (east/west/north/south)
- `MATERIAL` - block material (supports modded blocks like `spark:*`)
- `FLIGHT_HEIGHT`, `WIDTH` - staircase dimensions
- `WALL_MATERIAL`, `LANTERN`, `LANTERN_INTERVAL` - decorative options

## Build & Run

```bash
# Build
cargo build --release

# Run staircase generator
cargo run -- staircase

# Run from file with skip
cargo run -- --skip 10
```

## Command Format

Commands use Bedrock Edition syntax:
- `/fill x1 y1 z1 x2 y2 z2 block`
- `/setblock x y z block`
- Block states: `["minecraft:cardinal_direction"="south"]`

## File Structure

```
src/
├── main.rs        # CLI and execution engine
└── staircase.rs   # Staircase command generator
grabcraft_to_commands.py   # GrabCraft blueprint converter
build_commands.mcfunction  # Command input file (generated or manual)
```

## GrabCraft Blueprint Converter

`grabcraft_to_commands.py` - Python script that converts blueprints from [GrabCraft.com](https://www.grabcraft.com) to Minecraft Bedrock Edition commands.

### What is GrabCraft?

GrabCraft is a website with thousands of Minecraft building blueprints (castles, towers, houses, ships, etc.). Each blueprint shows layer-by-layer block placement with materials.

### How it works

1. Fetches the blueprint page HTML
2. Extracts LayerMap JavaScript containing block data
3. Parses pixel coordinates and converts to grid positions
4. Maps GrabCraft material names to Bedrock Edition block IDs
5. Optimizes output using `/fill` for rectangular regions
6. Generates `.mcfunction` file with commands

### Usage

```bash
python3 grabcraft_to_commands.py <URL> [options]

# Examples
python3 grabcraft_to_commands.py https://www.grabcraft.com/minecraft/tower/...
python3 grabcraft_to_commands.py <URL> -o tower.mcfunction -y 70
python3 grabcraft_to_commands.py <URL> -x 100 -y 64 -z 200
```

### Options

- `-o FILE` - Output file (default: `build_commands.mcfunction`)
- `-x N` - X offset (default: 0)
- `-y N` - Y offset (default: 64)
- `-z N` - Z offset (default: 0)
- `--no-fill` - Use only `/setblock` (no optimization)
- `--save-csv` - Save raw block data to CSV

### Command Optimization

The script optimizes commands in priority order:
1. 3D cuboids (2x2x2+) → single `/fill`
2. 2D rectangles (2x2+) → single `/fill`
3. Horizontal lines (2+ blocks) → single `/fill`
4. Vertical columns (2+ blocks) → single `/fill`
5. Single blocks → `/setblock`

Attachable blocks (ladders, torches) are placed last.

## Notes

- Designed for use with Parallels Desktop running Windows + Minecraft Bedrock
- Uses clipboard-based input to handle special characters in block names
- Skip flag (`-s N`) allows resuming interrupted builds
