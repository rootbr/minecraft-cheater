# CLAUDE.md

## Project Overview

**mc-commander** is a Rust application with GUI and CLI modes for generating and auto-executing Minecraft **Bedrock Edition** commands via keyboard emulation. Designed for macOS with Minecraft running in Parallels Desktop.

## Technology Stack

### Rust Dependencies (Cargo.toml)

| Crate | Version | Purpose | Latest |
|-------|---------|---------|--------|
| clap | 4.5 | CLI argument parsing with derive macros | 4.5.x |
| enigo | 0.2 | Cross-platform keyboard/mouse emulation | 0.5.0 |
| arboard | 3.4 | Cross-platform clipboard access | 3.6.1 |
| scrap | 0.5 | Screen capture for chat state detection | 0.5 |
| image | 0.24 | Image processing for pixel detection | 0.24.x |
| eframe | 0.31 | Native GUI framework wrapper | 0.33.3 |
| egui | 0.31 | Immediate mode GUI library | 0.31.x |
| serde | 1.0 | Serialization/deserialization | 1.0.x |
| toml | 0.8 | TOML config file parsing | 0.8.x |

### Python Dependencies

- Python 3.13 (via .venv)
- Standard library only (urllib, json, re, csv, argparse)
- tomllib/tomli for TOML parsing in `grabcraft_to_bedrock.py`

### Target Platform
- **OS**: macOS (uses Meta key for Cmd+V)
- **Game**: Minecraft Bedrock Edition (Windows via Parallels Desktop)

## Architecture

### Module Dependency Graph

```
main.rs
├── config.rs        # Configuration loading and constants
├── executor.rs      # Command execution via keyboard emulation
│   ├── feedback.rs  # Screen capture and chat state detection
│   └── config.rs    # Timing constants
├── commands.rs      # Command parsing, offset application, bounding box
├── clear.rs         # Area clearing before builds
├── staircase.rs     # Staircase structure generator
├── url_handler.rs   # GrabCraft URL → commands pipeline
├── generator.rs     # Alternative URL-to-commands generator (unused)
└── gui.rs           # eframe/egui GUI application
```

### Rust Modules Detail

| Module | Lines | Purpose |
|--------|-------|---------|
| `main.rs` | ~150 | CLI parsing, execution orchestration |
| `gui.rs` | ~350 | Full GUI with URL loading, execution, logs |
| `executor.rs` | ~165 | Keyboard emulation, clipboard, retry logic |
| `feedback.rs` | ~240 | Screen capture, pixel analysis, chat state detection |
| `commands.rs` | ~170 | Command parsing, coordinate offset, bounding box |
| `config.rs` | ~105 | TOML config, timing constants, offset struct |
| `clear.rs` | ~55 | Area clearing with chunked fill commands |
| `staircase.rs` | ~310 | Parametric staircase generator |
| `url_handler.rs` | ~160 | GrabCraft URL processing, Python script invocation |
| `generator.rs` | ~90 | Alternative generator (partially redundant) |

### Python Scripts

| Script | Purpose |
|--------|---------|
| `grabcraft_to_commands.py` | Fetch GrabCraft blueprint → Bedrock commands |
| `grabcraft_to_bedrock.py` | Block name conversion (GrabCraft → Bedrock) |
| `optimize_commands.py` | Merge setblock → fill, apply offsets |
| `expand_commands.py` | Verify optimization (expand fill → setblock) |
| `export_pipeline_csv.py` | Full pipeline export with verification |

### Data Flow

```
GrabCraft URL
    ↓
grabcraft_to_commands.py (fetch, parse, rotate)
    ↓
grabcraft_to_bedrock.py (block conversion via bedrock_states.toml)
    ↓
build_commands.txt (raw /setblock commands)
    ↓
optimize_commands.py (merge to /fill)
    ↓
build_commands_optimized.txt
    ↓
mc-commander (Rust)
    ↓
executor.rs (keyboard emulation)
    ↓
Minecraft chat → command execution
```

### Chat State Detection (feedback.rs)

Screen regions monitored (configurable via `config.toml`):
- `panel_region`: Default (75, 645, 75, 30) - Chat panel area
- `health_region`: Default (450, 1360, 200, 20) - Health bar (closed state)
- `command_region`: Default (1250, 1392, 15, 40) - Command input area

**Note:** These regions are now configurable and will vary based on your screen resolution. Use the "Detection Areas" tab in the GUI to adjust them.

Chat states detected via pixel color analysis:
- `Open`: Command input empty (gray 117,117,117)
- `CommandEntered`: Text present (gray 198,198,198)
- `Closed`: Health bar visible (red 217,61,41 + green 148,235,58)

## Installation

### Rust CLI/GUI

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build
cargo build --release

# Executable: target/release/mc-commander
```

### Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
# No additional packages needed - uses stdlib only
```

### macOS Permissions

**Required:** System Settings → Privacy & Security → Accessibility
- Add Terminal (or your terminal app)
- Add IDE if running from there

**Required:** System Settings → Privacy & Security → Screen Recording
- Required for chat state detection (scrap crate)

## Usage

### GUI Mode (Default)

```bash
./target/release/mc-commander
```

GUI features:
- URL input with Load/Open buttons
- Execution mode: From File, Staircase, or Detection Areas
- Skip commands, material filter, coordinate offsets
- Real-time logs with scroll-to-bottom
- Detection areas preview with "Show Detection Areas" button
- Detection Areas tab for adjusting screen regions
- Auto-save to config.toml

### CLI Mode

```bash
# Run from config file
./target/release/mc-commander cli

# Generate staircase
./target/release/mc-commander staircase
```

### Configuration (config.toml)

```toml
[execution]
url = "https://www.grabcraft.com/minecraft/small-modern-villa/modern-houses"
skip = 0                    # Resume from command N
# material = "stone_stairs" # Filter by material

[coordinates]
offset_x = 0
offset_y = 0
offset_z = 0

[screen_regions]
# Adjust these values for your screen resolution
# Use the "Detection Areas" tab in GUI to edit

[screen_regions.panel_region]
x = 75
y = 645
width = 75
height = 30

[screen_regions.health_region]
x = 450
y = 1360
width = 200
height = 20

[screen_regions.command_region]
x = 1250
y = 1392
width = 15
height = 40
```

## Python Scripts

### grabcraft_to_commands.py

Converts GrabCraft blueprints to Minecraft Bedrock commands.

```bash
python3 grabcraft_to_commands.py <URL> [-o output.txt] [--save-csv blocks.csv]
```

Features:
- Automatic compass rotation detection
- LayerMap.js parsing
- Auto-detected cell size and grid offsets
- Block conversion via grabcraft_to_bedrock.py

### grabcraft_to_bedrock.py

Block conversion engine using:
- `bedrock_states.toml` - Direction mappings, block name translations
- Pattern-based converters for stairs, slabs, doors, etc.
- Singleton converter instance for performance

Converter classes:
- StairConverter, SlabConverter, DoorConverter, TrapdoorConverter
- ChestConverter, FurnaceConverter, LadderConverter, TorchConverter
- VineConverter, LogConverter, ButtonConverter, LeverConverter
- PistonConverter, ObserverConverter, DispenserConverter, HopperConverter
- WallConverter, FenceGateConverter, LeavesConverter, SignConverter, WallSignFixConverter
- FireConverter, PressurePlateConverter
- ColoredBlockConverter (wool, concrete, terracotta, etc.)
- BedConverter (skips foot pieces)
- SimpleBlockConverter (fallback)

#### Adding New Converters

> **Quick Reference:** See `ADDING_CONVERTERS.md` for step-by-step examples and common patterns.

**Step 1: Add material mappings to `bedrock_states.toml`**

For blocks with multiple materials (stairs, slabs, doors, etc.), add mappings:

```toml
# Example: Adding new pressure plate materials
[pressure_plate_materials]
wooden = "wooden_pressure_plate"
oak = "wooden_pressure_plate"
stone = "stone_pressure_plate"
# ... add more materials
```

**Step 2: Create converter class in `grabcraft_to_bedrock.py`**

```python
class YourBlockConverter(BaseConverter):
    """Converter for your block type."""
    # Define regex pattern to match GrabCraft block names
    PATTERN = re.compile(r'^(.+?)\s+Your\s+Block\s*\(([^)]*)\)$', re.IGNORECASE)

    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        # Extract material and properties
        material = match.group(1).lower().strip()
        props = match.group(2).lower().strip()

        # Get block name from material mappings
        block_name = BlockParser.get_material_block(
            material,
            YOUR_MATERIAL_MAP,  # From TOML
            "_suffix"
        )

        # Parse direction/state from properties
        direction = BlockParser.parse_direction_int(props, DIRECTION_MAP, default=0)

        # Return BedrockBlock with states
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'state_name': state_value,
                'another_state': another_value,
            }
        )
```

**Step 3: Load material mappings**

Add to top of `grabcraft_to_bedrock.py`:

```python
YOUR_MATERIAL_MAP = _BEDROCK_STATES["your_material_map"]
```

**Step 4: Register converter**

Add to `_init_converters()` method in order of precedence (more specific first):

```python
self.converters = [
    StairConverter(),
    # ... existing converters ...
    YourBlockConverter(),  # Add here
    # ... more converters ...
    SimpleBlockConverter()  # Always last (fallback)
]
```

**Step 5: Test**

```python
python3 -c "
from grabcraft_to_bedrock import convert_grabcraft_to_bedrock
print(convert_grabcraft_to_bedrock('Your Block Name (properties)'))
"
```

**Common Patterns:**

1. **Simple blocks with no states**: Use `SimpleBlockConverter` (fallback) and add mapping to `[grabcraft_to_be]` in TOML
2. **Blocks with direction only**: Use existing direction mappings (`HORIZONTAL_FACING`, `SIXWAY_FACING`, etc.)
3. **Blocks with material variants**: Create material mapping section in TOML, use `BlockParser.get_material_block()`
4. **Blocks with custom states**: Create dedicated converter class
5. **Blocks with age/power/level**: Parse numeric value from properties string

**Examples:**

- **FireConverter**: Parses `Fire (Age 15)` → `minecraft:fire["age"=15]`
- **PressurePlateConverter**: Maps materials from TOML → `minecraft:{material}_pressure_plate`
- **DoorConverter**: Complex states (direction, open_bit, upper_block_bit, door_hinge_bit)
- **WallSignFixConverter**: Handles special GrabCraft naming (8-way compass to 4-way)

### optimize_commands.py

```bash
python3 optimize_commands.py input.txt [output.txt] [-x N] [-y N] [-z N] [--no-fill]
```

Optimization algorithm:
1. Parse all commands into 3D grid
2. Sort materials by frequency
3. For each material: greedy cuboid expansion
4. Remaining blocks as /setblock
5. Attachable blocks (ladders, torches) placed last

Typical reduction: 30-70% fewer commands

### expand_commands.py

Verification tool - expands /fill back to /setblock for comparison.

```bash
python3 expand_commands.py original.txt optimized.txt
```

### export_pipeline_csv.py

Full pipeline export with verification.

```bash
python3 export_pipeline_csv.py <URL> [output.csv]
```

Generates: `*_bedrock.txt`, `*_optimized.txt`, `*.csv`

## Bedrock Edition Block States

All mappings defined in `bedrock_states.toml`.

### Configuration Structure

`bedrock_states.toml` contains all centralized mappings:

**Direction Mappings:**
- `[stair_direction]` - Stairs: east=0, west=1, south=2, north=3
- `[bed_direction_map]` - Beds: south=0, west=1, north=2, east=3
- `[sixway_facing]` - Pistons/Observers: down=0, up=1, south=2, north=3, east=4, west=5
- `[horizontal_facing]` - Chests/Furnaces: north=2, south=3, west=4, east=5
- `[door_direction]` - Doors: east=0, south=1, west=2, north=3
- `[vine_bits]` - Vines (bitmask): south=1, west=2, north=4, east=8
- `[torch_facing_direction]` - Torches: opposite direction mapping
- `[pillar_axis]` - Logs: "x", "y", "z"
- `[button_facing]` - Buttons: down=0, up=1, north=2, south=3, west=4, east=5
- `[wall_sign_direction]` - Wall signs: 8-way compass to 6-way facing

**Material Mappings:**
- `[pressure_plate_materials]` - Pressure plates by material
- `[stair_materials]` - Stairs by material
- `[slab_materials]` - Slabs by material
- `[double_slab_to_block]` - Double slab to full block
- `[door_materials]` - Doors by material
- `[trapdoor_materials]` - Trapdoors by material
- `[wall_materials]` - Walls by material

**Block Name Mappings:**
- `[je_to_be_names]` - Java Edition → Bedrock Edition names
- `[grabcraft_to_be]` - GrabCraft → Bedrock Edition names

**Colors:**
- `[colors]` - List of valid color names
- `[grabcraft_color_map]` - GrabCraft color variations

### Direction Mappings

| Block Type | State | Values |
|------------|-------|--------|
| Stairs | weirdo_direction | east=0, west=1, south=2, north=3 |
| Beds | direction | south=0, west=1, north=2, east=3 |
| 6-way (pistons) | facing_direction | down=0, up=1, south=2, north=3, east=4, west=5 |
| Horizontal | facing_direction | north=2, south=3, west=4, east=5 |
| Doors | direction | east=0, south=1, west=2, north=3 |
| Vines | vine_direction_bits | south=1, west=2, north=4, east=8 (bitmask) |
| Logs | pillar_axis | "x", "y", "z" |

### Adding New Materials to TOML

**Example 1: Add new stair material**

Edit `bedrock_states.toml`:

```toml
[stair_materials]
# Existing materials...
tuff = "tuff_stairs"
"polished tuff" = "polished_tuff_stairs"
"tuff brick" = "tuff_brick_stairs"
"new material" = "new_material_stairs"  # Add this line
```

**Example 2: Add new pressure plate**

```toml
[pressure_plate_materials]
# Existing materials...
"new material" = "new_material_pressure_plate"  # Add this line
```

**Example 3: Add new block name mapping**

```toml
[grabcraft_to_be]
# Existing mappings...
"grabcraft name" = "bedrock_id"  # Add this line
"Stone Bricks" = "stone_bricks"
"Chiseled Tuff" = "chiseled_tuff"
```

**Example 4: Add new direction mapping (rare)**

```toml
[your_new_direction_map]
north = 0
south = 1
east = 2
west = 3
```

Then load in `grabcraft_to_bedrock.py`:

```python
YOUR_DIRECTION_MAP = _BEDROCK_STATES["your_new_direction_map"]
```

**Tips:**
- Use lowercase keys with spaces: `"dark oak"`, `"polished blackstone"`
- Values are Bedrock block IDs without `minecraft:` prefix
- Test changes: `python3 -c "from grabcraft_to_bedrock import convert_grabcraft_to_bedrock; print(convert_grabcraft_to_bedrock('Your Block Name'))"`

### Common Block Patterns

```
# Stairs
minecraft:oak_stairs["weirdo_direction"=3,"upside_down_bit"=false]

# Slabs
minecraft:stone_slab["minecraft:vertical_half"="bottom"]

# Doors
minecraft:oak_door["direction"=0,"open_bit"=false,"upper_block_bit"=false]

# Logs
minecraft:oak_log["pillar_axis"="y"]

# Leaves (persistent)
minecraft:oak_leaves["persistent_bit"=true,"update_bit"=false]
```

## File Structure

```
src/
├── main.rs              # CLI entry point, orchestration
├── gui.rs               # eframe/egui GUI application
├── config.rs            # Config structs, timing constants
├── executor.rs          # Keyboard emulation, command execution
├── feedback.rs          # Screen capture, chat state detection
├── commands.rs          # Command parsing, offsets, bounding box
├── clear.rs             # Area clearing commands
├── staircase.rs         # Staircase generator
├── url_handler.rs       # GrabCraft URL → commands pipeline
└── generator.rs         # Alternative generator

*.py                     # Python conversion/optimization scripts
bedrock_states.toml      # Block state mappings
config.toml              # User configuration (not in git)
config.example.toml      # Example configuration

grabcraft/               # Generated command files by URL path
  └── {name}/{category}/
      ├── build_commands.txt
      └── build_commands_optimized.txt
```

## Technical Notes

### Timing Constants (config.rs)

```rust
pub const KEY_PRESS_DELAY_MS: u64 = 50;    // Between key presses
pub const STATE_TIMEOUT_SECS: u64 = 1;      // Chat state detection timeout
pub const POLL_INTERVAL_MS: u64 = 40;       // Screen capture poll interval
pub const CHUNK_SIZE: i32 = 32;             // Max /fill dimension
```

### Keyboard Keycodes (macOS)

```rust
const CHAT_KEY: Key = Key::Other(17);  // 't' keycode
const PASTE_KEY: Key = Key::Other(9);  // 'v' keycode
```

### Command Execution Retry Logic

- Max 3 retries per command
- Escape key pressed if chat state unexpected
- Stats tracked: total time, iterations per phase

### Screen Capture

- Uses `scrap` crate for cross-platform capture
- BGRA pixel format, converted to RGBA for analysis
- Color tolerance: ±5 for each RGB channel

## Troubleshooting

**Commands not typing:**
- Check Accessibility permissions in System Settings
- Check Screen Recording permissions (for chat detection)
- Ensure Minecraft window is active and focused

**Chat detection failing:**
- Run "Show Detection Areas" to verify screen regions
- Adjust region constants in feedback.rs for your resolution
- Check that Minecraft UI scale matches expected positions

**Python scripts failing:**
- Ensure .venv is activated
- Check network connectivity for GrabCraft fetches
- Verify URL format: `https://www.grabcraft.com/minecraft/{name}/{category}`

**Interrupted build:**
- Note the last command number from logs
- Set `skip = N` in config.toml
- Area clearing automatically skipped when skip > 0

**Stop execution:**
- Press Ctrl+C in terminal
- GUI: Close window (no graceful stop currently)

## Potential Improvements

### Dependency Updates
- enigo: 0.2 → 0.5.0 (breaking API changes)
- arboard: 3.4 → 3.6.1 (Wayland support improvements)
- eframe/egui: 0.31 → 0.33.3 (new features, breaking changes)

### Code Quality
- `generator.rs` partially duplicates `url_handler.rs` functionality
- `feedback.rs:21` has `#[allow(dead_code)]` for `WaitStats.elapsed`
- Hardcoded screen coordinates in `feedback.rs` (resolution-dependent)

### Feature Ideas
- Graceful stop button in GUI
- Progress bar for long builds
- Configurable screen regions
- Multi-monitor support for detection
- Build preview/visualization
