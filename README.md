# mc-commander

Rust CLI tool for generating and auto-executing Minecraft Bedrock Edition commands via keyboard emulation.

## Quick Start

1. **Build the project:**
   ```bash
   cargo build --release
   ```

2. **Create your configuration:**
   ```bash
   cp config.example.toml config.toml
   # Edit config.toml with your settings
   ```

3. **Set up macOS permissions:**
   - System Settings → Privacy & Security → Accessibility
   - Add Terminal (or your terminal app)

4. **Run the tool:**
   ```bash
   ./target/release/mc-commander
   ```

## Configuration

All settings are in `config.toml`:

```toml
[execution]
file = "build_commands_optimized.txt"  # Command file to execute
skip = 0                                # Skip first N commands (for resuming)
# material = "stone_stairs"             # Filter by material (optional)

[coordinates]
offset_x = 0  # Coordinate offsets
offset_y = 0
offset_z = 0
```

## Usage Examples

**Basic build:**
```bash
./target/release/mc-commander
```

**Use custom config:**
```bash
./target/release/mc-commander --config tower.toml
```

**Generate staircase:**
```bash
./target/release/mc-commander staircase
```

## Documentation

See [CLAUDE.md](CLAUDE.md) for complete documentation including:
- Architecture details
- Python script usage (GrabCraft converter, optimizer)
- Bedrock Edition block states
- Troubleshooting

## Requirements

- Rust 2021+
- macOS (tested on macOS with Parallels Desktop)
- Minecraft Bedrock Edition
