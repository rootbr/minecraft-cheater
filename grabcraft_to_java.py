#!/usr/bin/env python3
"""
GrabCraft to Java Edition Block Converter

Converts GrabCraft's human-readable block format (e.g., "Oak Wood Stairs (North, Normal)")
to Minecraft Java Edition block IDs with proper string-based states.

Java Edition uses string states without quotes: minecraft:oak_stairs[facing=north,half=bottom]
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


# =============================================================================
# LOAD JAVA BLOCK STATE CONSTANTS FROM TOML
# =============================================================================

def _load_java_states() -> dict:
    """Load Java block state constants from TOML config."""
    config_path = Path(__file__).parent / "java_states.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)

_JAVA_STATES = _load_java_states()

# Direction mappings
STAIR_FACING = _JAVA_STATES["stair_facing"]
BED_FACING = _JAVA_STATES["bed_facing"]
SIXWAY_FACING = _JAVA_STATES["sixway_facing"]
HORIZONTAL_FACING = _JAVA_STATES["horizontal_facing"]
DOOR_FACING = _JAVA_STATES["door_facing"]
TRAPDOOR_FACING = _JAVA_STATES["trapdoor_facing"]
VINE_BITS = _JAVA_STATES["vine_bits"]
TORCH_FACING = _JAVA_STATES["torch_facing"]
PILLAR_AXIS = _JAVA_STATES["pillar_axis"]
BUTTON_FACE = _JAVA_STATES["button_face"]
BUTTON_FACING = _JAVA_STATES["button_facing"]
WALL_SIGN_FACING = _JAVA_STATES["wall_sign_facing"]

# Half/position mappings
STAIR_HALF = _JAVA_STATES["stair_half"]
SLAB_TYPE = _JAVA_STATES["slab_type"]
DOOR_HALF = _JAVA_STATES["door_half"]
TRAPDOOR_HALF = _JAVA_STATES["trapdoor_half"]

# Block name mappings
GRABCRAFT_TO_JAVA = _JAVA_STATES["grabcraft_to_java"]
COLORS = _JAVA_STATES["colors"]["list"]
GRABCRAFT_COLOR_MAP = _JAVA_STATES["grabcraft_color_map"]

# Material mappings
STAIR_MATERIALS = _JAVA_STATES["stair_materials"]
SLAB_MATERIALS = _JAVA_STATES["slab_materials"]
DOUBLE_SLAB_TO_BLOCK = _JAVA_STATES["double_slab_to_block"]
DOOR_MATERIALS = _JAVA_STATES["door_materials"]
TRAPDOOR_MATERIALS = _JAVA_STATES["trapdoor_materials"]
WALL_MATERIALS = _JAVA_STATES["wall_materials"]
PRESSURE_PLATE_MATERIALS = _JAVA_STATES["pressure_plate_materials"]


# =============================================================================
# BLOCKMAP.CSV FALLBACK (from grabcraft-to-schema project)
# =============================================================================

def _load_blockmap() -> dict:
    """Load blockmap.csv as fallback lookup: grabcraft name -> java block id (without minecraft: prefix).

    Returns two dicts:
      exact: full GrabCraft name (lowered) -> block id
      base:  name with parenthesized content stripped (lowered) -> block id
    """
    exact = {}
    base = {}
    blockmap_path = Path(__file__).parent / "grabcraft-to-schema" / "blockmap.csv"
    if not blockmap_path.exists():
        return exact, base
    with open(blockmap_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            gc_name = (row.get('from') or '').strip()
            mc_id = (row.get('to') or '').strip()
            if not gc_name or not mc_id:
                continue
            # Strip minecraft: prefix
            if mc_id.startswith('minecraft:'):
                mc_id = mc_id[len('minecraft:'):]
            gc_lower = gc_name.lower()
            if gc_lower not in exact:
                exact[gc_lower] = mc_id
            # Also index by base name (without parenthesized properties)
            base_name = re.sub(r'\s*\([^)]*\)\s*$', '', gc_lower).strip()
            if base_name and base_name not in base:
                base[base_name] = mc_id
    return exact, base

_BLOCKMAP_EXACT, _BLOCKMAP_BASE = _load_blockmap()


# =============================================================================
# RESULT DATA CLASS
# =============================================================================

@dataclass
class JavaBlock:
    """Result of conversion to Java Edition block."""
    block_id: str  # e.g., "minecraft:oak_stairs"
    states: dict   # e.g., {"facing": "north", "half": "bottom"}

    def to_command_string(self) -> str:
        """Format as Java /setblock command block specifier.

        Java format: no quotes on keys, no quotes on string values.
        Example: minecraft:oak_stairs[facing=north,half=bottom]
        """
        if not self.states:
            return self.block_id

        state_parts = []
        for key, value in self.states.items():
            if isinstance(value, bool):
                state_parts.append(f'{key}={str(value).lower()}')
            elif isinstance(value, int):
                state_parts.append(f'{key}={value}')
            else:
                state_parts.append(f'{key}={value}')

        return f'{self.block_id}[{",".join(state_parts)}]'


# =============================================================================
# BLOCK PARSING HELPERS
# =============================================================================

class BlockParser:
    """Helper methods for parsing block names and properties."""

    DIRECTION_MAP = {
        'north': 'north', 'south': 'south', 'east': 'east', 'west': 'west',
        'up': 'up', 'down': 'down',
        'facing north': 'north', 'facing south': 'south',
        'facing east': 'east', 'facing west': 'west',
        'facing up': 'up', 'facing down': 'down',
    }

    @staticmethod
    def normalize_color(color_name: str, color_lookup: dict) -> Optional[str]:
        if not color_name:
            return None
        return color_lookup.get(color_name.lower().strip())

    @staticmethod
    def parse_direction_str(props: str, mapping: dict, default="north") -> str:
        """Parse direction from properties string, returning a string value."""
        props_lower = props.lower()
        for dir_name, dir_val in mapping.items():
            if dir_name in props_lower:
                return dir_val
        return default

    @staticmethod
    def get_material_block(material: str, mapping: dict, suffix: str = "") -> str:
        material = material.lower().strip()
        for mat_key, name in mapping.items():
            if material == mat_key or material.startswith(mat_key):
                return name
        return material.replace(' ', '_') + suffix


# =============================================================================
# CONVERTER INTERFACE
# =============================================================================

class BaseConverter:
    """Base class for specialized block converters."""
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        raise NotImplementedError


# =============================================================================
# CONVERTER IMPLEMENTATIONS
# =============================================================================

class StairConverter(BaseConverter):
    PATTERN = re.compile(
        r'^(.+?)\s+Stairs?\s*\(([^,)]+)(?:,\s*(Normal|Upside-down|Upside down))?\)?$',
        re.IGNORECASE
    )
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        material = match.group(1).lower().strip()
        direction = match.group(2).lower().strip()
        position = match.group(3).lower().strip() if match.group(3) else 'normal'

        block_name = BlockParser.get_material_block(material, STAIR_MATERIALS, "_stairs")
        facing = STAIR_FACING.get(direction, "north")
        half = STAIR_HALF.get(position, "bottom")

        return JavaBlock(
            block_id=f'minecraft:{block_name}',
            states={'facing': facing, 'half': half}
        )


class SlabConverter(BaseConverter):
    PATTERN = re.compile(
        r'^(?:(Double)\s+)?(.+?)\s+Slab\s*(?:\((Upper|Lower|Top|Bottom)\))?$',
        re.IGNORECASE
    )
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        is_double = match.group(1) is not None
        material = match.group(2).lower().strip()
        position = match.group(3).lower().strip() if match.group(3) else 'bottom'

        if is_double:
            block_name = DOUBLE_SLAB_TO_BLOCK.get(material, material.replace(' ', '_'))
            return JavaBlock(block_id=f'minecraft:{block_name}', states={})

        block_name = BlockParser.get_material_block(material, SLAB_MATERIALS, "_slab")
        slab_type = 'top' if position in ('upper', 'top') else 'bottom'

        return JavaBlock(
            block_id=f'minecraft:{block_name}',
            states={'type': slab_type}
        )


class DoorConverter(BaseConverter):
    """
    Converter for door blocks with automatic hinge detection.

    GrabCraft doors consist of TWO blocks:
    - Lower block: has direction and open/closed state
    - Upper block: has hinge (left/right) and power state

    This converter:
    - Processes both Upper and Lower blocks
    - Uses cached hinge info from Upper blocks for Lower blocks
    """
    PATTERN = re.compile(r'^(.+?)\s+Door\s*\(([^)]*)\)?$', re.IGNORECASE)

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        material, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_name = BlockParser.get_material_block(material, DOOR_MATERIALS, "_door")

        # Parse direction
        facing = BlockParser.parse_direction_str(props, DOOR_FACING, "east")

        # Parse open state
        is_open = 'open' in props and 'closed' not in props

        # Parse upper/lower half
        is_upper = 'upper' in props
        half = 'upper' if is_upper else 'lower'

        # Parse hinge: Java uses "left"/"right" directly (no inversion)
        hinge = 'left'
        if 'hinge' in props:
            hinge = 'right' if 'right' in props else 'left'
        elif hasattr(parser, '_current_coords') and parser._current_coords:
            x, y, z, layer = parser._current_coords
            cache_key = (x, y, z, layer)
            if cache_key in parser.door_hinge_cache:
                hinge = parser.door_hinge_cache[cache_key]

        return JavaBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'facing': facing,
                'open': is_open,
                'half': half,
                'hinge': hinge,
            }
        )


class TrapdoorConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Trapdoor\s*\(([^)]*)\)$', re.IGNORECASE)

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        material, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_name = BlockParser.get_material_block(material, TRAPDOOR_MATERIALS, "_trapdoor")

        facing = BlockParser.parse_direction_str(props, TRAPDOOR_FACING, "north")
        is_open = 'open' in props
        half = 'top' if 'top' in props else 'bottom'

        return JavaBlock(
            block_id=f'minecraft:{block_name}',
            states={'facing': facing, 'open': is_open, 'half': half}
        )


class ChestConverter(BaseConverter):
    PATTERN = re.compile(r'^(Trapped\s+|Ender\s+)?Chest\s*\(([^)]+)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        prefix, direction_str = (match.group(1) or "").lower().strip(), match.group(2).lower().strip()
        block_id = "ender_chest" if "ender" in prefix else ("trapped_chest" if "trapped" in prefix else "chest")
        facing = HORIZONTAL_FACING.get(direction_str, "north")
        return JavaBlock(block_id=f'minecraft:{block_id}', states={'facing': facing})


class FurnaceConverter(BaseConverter):
    PATTERN = re.compile(r'^(Blast\s+|)Furnace\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        prefix, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_id = "blast_furnace" if "blast" in prefix else "furnace"
        facing = HORIZONTAL_FACING.get(props, "north")
        return JavaBlock(block_id=f'minecraft:{block_id}', states={'facing': facing})


class LadderConverter(BaseConverter):
    PATTERN = re.compile(r'^Ladder\s*\((?:facing\s+)?([^)]+)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        facing = HORIZONTAL_FACING.get(match.group(1).lower().strip(), "north")
        return JavaBlock(block_id='minecraft:ladder', states={'facing': facing})


class TorchConverter(BaseConverter):
    PATTERN = re.compile(r'^(Soul\s+|Redstone\s+)?Torch\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        prefix, props = (match.group(1) or "").lower().strip(), (match.group(2) or "up").lower().strip()

        direction = parser._parse_direction(props) or "up"

        # Floor torches have no states in Java
        if direction == "up":
            if "soul" in prefix:
                return JavaBlock(block_id='minecraft:soul_torch', states={})
            elif "redstone" in prefix:
                return JavaBlock(block_id='minecraft:redstone_torch', states={})
            else:
                return JavaBlock(block_id='minecraft:torch', states={})

        # Wall torches: Java uses separate block IDs for wall variants
        facing = TORCH_FACING.get(direction, "north")
        if "soul" in prefix:
            return JavaBlock(block_id='minecraft:soul_wall_torch', states={'facing': facing})
        elif "redstone" in prefix:
            return JavaBlock(block_id='minecraft:redstone_wall_torch', states={'facing': facing})
        else:
            return JavaBlock(block_id='minecraft:wall_torch', states={'facing': facing})


class VineConverter(BaseConverter):
    PATTERN = re.compile(r'^Vines?\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        props = match.group(1).lower().strip()
        # Java uses individual boolean states for each face
        states = {
            'north': 'north' in props,
            'south': 'south' in props,
            'east': 'east' in props,
            'west': 'west' in props,
        }
        return JavaBlock(block_id='minecraft:vine', states=states)


class LogConverter(BaseConverter):
    PATTERN = re.compile(r'^(?:Stripped\s+)?(.+?)\s+(Wood|Log|Stem)\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, wood_type, props = match.group(1).lower().strip(), match.group(2).lower().strip(), match.group(3).lower().strip()
        is_stripped = "stripped" in name.lower()

        suffix = "_log"
        if wood_type == "wood" or wood_type == "stem":
            suffix = "_wood" if wood_type == "wood" else "_stem"

        block_name = GRABCRAFT_TO_JAVA.get(material, material.replace(' ', '_'))

        if not (block_name.endswith("_log") or block_name.endswith("_wood") or block_name.endswith("_stem")):
            block_name = f"{block_name}{suffix}"

        if is_stripped and not block_name.startswith("stripped_"):
            block_name = f"stripped_{block_name}"

        axis = PILLAR_AXIS.get(props, "y")
        return JavaBlock(block_id=f'minecraft:{block_name}', states={'axis': axis})


class ButtonConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Button\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_name = f"{material.replace(' ', '_')}_button"
        face = BUTTON_FACE.get(props, "wall")
        facing = BUTTON_FACING.get(props, "north")
        return JavaBlock(block_id=f'minecraft:{block_name}', states={'face': face, 'facing': facing})


class LeverConverter(BaseConverter):
    PATTERN = re.compile(r'^Lever\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        props = match.group(1).lower().strip()

        # Determine face and facing
        if 'up' in props:
            face = 'floor'
            facing = 'north'
        elif 'down' in props:
            face = 'ceiling'
            facing = 'north'
        elif 'north' in props:
            face, facing = 'wall', 'north'
        elif 'south' in props:
            face, facing = 'wall', 'south'
        elif 'east' in props:
            face, facing = 'wall', 'east'
        elif 'west' in props:
            face, facing = 'wall', 'west'
        else:
            face, facing = 'wall', 'north'

        powered = 'on' in props
        return JavaBlock(block_id='minecraft:lever', states={'face': face, 'facing': facing, 'powered': powered})


class PistonConverter(BaseConverter):
    PATTERN = re.compile(r'^(Sticky\s+)?Piston\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        is_sticky, props = match.group(1), match.group(2).lower().strip()
        block_id = "sticky_piston" if is_sticky else "piston"
        facing = SIXWAY_FACING.get(props, "down")
        return JavaBlock(block_id=f'minecraft:{block_id}', states={'facing': facing})


class ObserverConverter(BaseConverter):
    PATTERN = re.compile(r'^Observer\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        facing = SIXWAY_FACING.get(match.group(1).lower().strip(), "down")
        return JavaBlock(block_id='minecraft:observer', states={'facing': facing})


class DispenserConverter(BaseConverter):
    PATTERN = re.compile(r'^(Dispenser|Dropper)\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        block_id, facing_str = match.group(1).lower(), match.group(2).lower().strip()
        facing = SIXWAY_FACING.get(facing_str, "down")
        return JavaBlock(block_id=f'minecraft:{block_id}', states={'facing': facing})


class HopperConverter(BaseConverter):
    PATTERN = re.compile(r'^Hopper\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        facing = SIXWAY_FACING.get(match.group(1).lower().strip(), "down")
        return JavaBlock(block_id='minecraft:hopper', states={'facing': facing})


class WallConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Wall$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material = match.group(1).lower().strip()
        block_name = BlockParser.get_material_block(material, WALL_MATERIALS, "_wall")
        return JavaBlock(block_id=f'minecraft:{block_name}', states={})


class FenceGateConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Fence\s+Gate\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, props = match.group(1).lower().strip(), (match.group(2) or "").lower().strip()
        block_name = GRABCRAFT_TO_JAVA.get(f"{material} fence gate", f"{material.replace(' ', '_')}_fence_gate")
        facing = HORIZONTAL_FACING.get(props, "north")
        is_open = 'open' in props
        return JavaBlock(block_id=f'minecraft:{block_name}', states={'facing': facing, 'open': is_open})


class LeavesConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Leaves\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material = match.group(1).lower().strip()
        block_name = f"{material.replace(' ', '_')}_leaves"
        return JavaBlock(block_id=f'minecraft:{block_name}', states={'persistent': True})


class RedstoneWireConverter(BaseConverter):
    PATTERN = re.compile(r'^Redstone\s+Wire\s*\(Power:\s*(\d+)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        power = int(match.group(1))
        return JavaBlock(block_id='minecraft:redstone_wire', states={'power': power})


class WaterConverter(BaseConverter):
    PATTERN = re.compile(r'^(?:Still\s+)?Water\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        return JavaBlock(block_id='minecraft:water', states={'level': 0})


class FlowerConverter(BaseConverter):
    PATTERN = re.compile(r'^Flower\s*\(([^,]+)(?:,\s*(Upper|Lower))?\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        flower_type, position = match.group(1).lower().strip(), (match.group(2) or "lower").lower().strip()
        block_id = GRABCRAFT_TO_JAVA.get(flower_type, flower_type.replace(' ', '_'))
        half = 'upper' if position == 'upper' else 'lower'
        return JavaBlock(block_id=f'minecraft:{block_id}', states={'half': half})


class ColoredBlockConverter(BaseConverter):
    """Generic converter for colored blocks (wool, terracotta, concrete, etc.)"""
    def __init__(self, pattern, block_type, suffix=""):
        self.PATTERN = pattern
        self.block_type = block_type
        self.suffix = suffix

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        color_name = match.group(1).lower().strip()
        normalized_color = parser._normalize_color(color_name)
        final_color = normalized_color if normalized_color else color_name.replace(" ", "_")
        return JavaBlock(block_id=f'minecraft:{final_color}_{self.block_type}{self.suffix}', states={})


class BedConverter(BaseConverter):
    PATTERN = re.compile(
        r'^(?!(?:' + '|'.join(COLORS) + r')\s+)Bed\s*(?:\(([^)]*)\))?',
        re.IGNORECASE
    )

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        props = (match.group(1) or "").lower()

        # Check if this is a foot piece - skip it
        if "foot" in props:
            return JavaBlock(block_id='__SKIP__', states={})

        facing = "south"
        for dir_name, dir_val in BED_FACING.items():
            if dir_name in props:
                facing = dir_val
                break

        occupied = "occupied" in props

        return JavaBlock(
            block_id='minecraft:bed',
            states={'facing': facing, 'occupied': occupied, 'part': 'head'}
        )


class SignConverter(BaseConverter):
    PATTERN = re.compile(r'^(?:(.+?)\s+)?(?:Wall[- ]?(?:mounted|Mounted)?\s*)?Sign(?:\s+Block)?\s*[,\s]*(?:\(([^)]*)\)|(.+))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material = (match.group(1) or "Oak").lower().strip()
        props = (match.group(2) or match.group(3) or "").lower().strip()

        is_wall = "wall" in name.lower() or "mounted" in props
        block_base = DOOR_MATERIALS.get(material, material.replace(' ', '_'))

        if is_wall:
            block_id = f"minecraft:{block_base}_wall_sign"
            facing = HORIZONTAL_FACING.get(props, "north")
            return JavaBlock(block_id=block_id, states={'facing': facing})
        else:
            block_id = f"minecraft:{block_base}_sign"
            rot_map = {'south': 0, 'west': 4, 'north': 8, 'east': 12}
            rotation = rot_map.get(props, 0)
            return JavaBlock(block_id=block_id, states={'rotation': rotation})


class WallSignFixConverter(BaseConverter):
    """Fix GrabCraft names that turn into wall_wall_sign or wall-mounted_wall_sign."""
    PATTERN = re.compile(
        r'^(?:Wall(?:-?mounted)?)\s+(?:Wall\s+)?Sign(?:\s+Block)?\s*[,\s]*(.*)$',
        re.IGNORECASE
    )

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        direction_str = match.group(1).strip().lower() if match.group(1) else ""
        direction_str = direction_str.replace('(', '').replace(')', '').strip()

        facing = WALL_SIGN_FACING.get(direction_str)
        if facing is None:
            facing = HORIZONTAL_FACING.get(direction_str, "north")

        return JavaBlock(block_id='minecraft:oak_wall_sign', states={'facing': facing})


class FireConverter(BaseConverter):
    """Converter for fire blocks with age state."""
    PATTERN = re.compile(r'^Fire\s*(?:\(Age\s*(\d+)\))?$', re.IGNORECASE)

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        age = int(match.group(1)) if match.group(1) else 0
        return JavaBlock(block_id='minecraft:fire', states={'age': age})


class PressurePlateConverter(BaseConverter):
    """Converter for pressure plates."""
    PATTERN = re.compile(r'^(.+?)\s+Pressure\s+Plate\s*(?:\((?:Active|Unactive|Inactive)\))?$', re.IGNORECASE)

    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        material = match.group(1).lower().strip()
        block_name = BlockParser.get_material_block(material, PRESSURE_PLATE_MATERIALS, "_pressure_plate")
        return JavaBlock(block_id=f'minecraft:{block_name}', states={})


class SimpleBlockConverter(BaseConverter):
    """Fallback converter for simple blocks with no states."""
    def convert(self, name: str, parser: 'GrabCraftToJavaConverter') -> Optional[JavaBlock]:
        clean_name = name.lower().strip()
        block_id = GRABCRAFT_TO_JAVA.get(clean_name)
        if not block_id:
            # Fallback: check blockmap.csv (exact match, then base name)
            block_id = _BLOCKMAP_EXACT.get(clean_name) or _BLOCKMAP_BASE.get(
                re.sub(r'\s*\([^)]*\)\s*$', '', clean_name).strip()
            )
        if not block_id:
            block_id = clean_name.replace(' ', '_')
        return JavaBlock(block_id=f'minecraft:{block_id}', states={})


# =============================================================================
# MAIN CONVERTER CLASS
# =============================================================================

class GrabCraftToJavaConverter:
    """
    Converts GrabCraft's human-readable block format to Java Edition.

    For CSV processing: supports door pair caching to merge hinge info from
    Upper blocks into Lower block commands.
    """

    def __init__(self):
        """Initialize converter with lookup tables and sub-converters."""
        self._build_color_lookup()
        self._init_converters()
        self.door_hinge_cache = {}  # key: (x, y, z, layer) -> "left"/"right"

    def _build_color_lookup(self):
        """Build color name lookup table."""
        self.color_lookup = {color: color for color in COLORS}
        self.color_lookup.update({color.replace('_', ' '): color for color in COLORS})
        self.color_lookup.update(GRABCRAFT_COLOR_MAP)

    def _init_converters(self):
        """Initialize all specialized sub-converters."""
        self.converters = [
            StairConverter(),
            SlabConverter(),
            DoorConverter(),
            TrapdoorConverter(),
            BedConverter(),
            ChestConverter(),
            FurnaceConverter(),
            LadderConverter(),
            TorchConverter(),
            VineConverter(),
            LogConverter(),
            ButtonConverter(),
            LeverConverter(),
            PistonConverter(),
            ObserverConverter(),
            DispenserConverter(),
            HopperConverter(),
            WallConverter(),
            FenceGateConverter(),
            LeavesConverter(),
            RedstoneWireConverter(),
            WaterConverter(),
            FlowerConverter(),
            FireConverter(),
            PressurePlateConverter(),
            WallSignFixConverter(),
            SignConverter(),
            # Colored blocks
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Wool$', re.IGNORECASE), "wool"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+(?:Stained\s+Clay|Terracotta)$', re.IGNORECASE), "terracotta"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Concrete$', re.IGNORECASE), "concrete"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Concrete\s+Powder$', re.IGNORECASE), "concrete_powder"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+(?:Stained\s+)?Glass$', re.IGNORECASE), "stained_glass"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+(?:Stained\s+)?Glass\s+Pane$', re.IGNORECASE), "stained_glass_pane"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Carpet$', re.IGNORECASE), "carpet"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Bed\s*(?:\(([^)]*)\))?$', re.IGNORECASE), "bed"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Candle\s*(?:\(([^)]*)\))?$', re.IGNORECASE), "candle"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Shulker\s+Box\s*(?:\(([^)]*)\))?$', re.IGNORECASE), "shulker_box"),
            ColoredBlockConverter(re.compile(r'^(.+?)\s+Glazed\s+Terracotta\s*(?:\(([^)]*)\))?$', re.IGNORECASE), "glazed_terracotta"),
            # Fallback
            SimpleBlockConverter()
        ]

    def _normalize_color(self, color_name: str) -> Optional[str]:
        """Normalize color name to Java format."""
        if not color_name: return None
        return self.color_lookup.get(color_name.lower().strip())

    def _parse_direction(self, direction_str: str) -> Optional[str]:
        """Parse direction from GrabCraft format."""
        return BlockParser.DIRECTION_MAP.get(direction_str.lower().strip())

    def register_door_upper_block(self, x: int, y: int, z: int, layer: int, block_name: str):
        """
        Register hinge info from an Upper door block for later use by Lower block.

        Java uses "left"/"right" directly — no inversion needed.
        """
        hinge = 'left'

        match = DoorConverter.PATTERN.match(block_name)
        if match:
            props = match.group(2).lower().strip()
            if 'hinge' in props:
                hinge = 'right' if 'right' in props else 'left'
        else:
            if 'hinge right' in block_name.lower():
                hinge = 'right'

        # Lower block is at same x, z, but y-1, layer-1
        lower_key = (x, y - 1, z, layer - 1)
        self.door_hinge_cache[lower_key] = hinge

    def clear_door_cache(self):
        """Clear door hinge cache."""
        self.door_hinge_cache.clear()

    def convert(self, grabcraft_name: str, x: Optional[int] = None, y: Optional[int] = None,
                z: Optional[int] = None, layer: Optional[int] = None) -> Optional[JavaBlock]:
        """
        Convert a GrabCraft block name to Java Edition format.

        Args:
            grabcraft_name: Block name from GrabCraft
            x, y, z, layer: Optional coordinates for door pair lookup
        """
        if not grabcraft_name or not grabcraft_name.strip():
            return None

        name = grabcraft_name.strip()

        self._current_coords = (x, y, z, layer) if x is not None else None

        for converter in self.converters:
            result = converter.convert(name, self)
            if result is not None:
                return result

        return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_converter = None

def get_converter() -> GrabCraftToJavaConverter:
    """Get singleton converter instance."""
    global _converter
    if _converter is None:
        _converter = GrabCraftToJavaConverter()
    return _converter


def convert_grabcraft_to_java(grabcraft_name: str, x: Optional[int] = None, y: Optional[int] = None,
                              z: Optional[int] = None, layer: Optional[int] = None) -> Optional[str]:
    """
    Convert a GrabCraft block name to Java Edition command string.

    Args:
        grabcraft_name: Block name from GrabCraft (e.g., "Oak Wood Stairs (North, Normal)")
        x, y, z, layer: Optional coordinates for door pair lookup

    Returns:
        Java block command string (e.g., 'minecraft:oak_stairs[facing=north,half=bottom]')
        or None if conversion failed.

    Examples:
        >>> convert_grabcraft_to_java("Oak Wood Stairs (North, Normal)")
        'minecraft:oak_stairs[facing=north,half=bottom]'

        >>> convert_grabcraft_to_java("Cobblestone Slab (Upper)")
        'minecraft:cobblestone_slab[type=top]'

        >>> convert_grabcraft_to_java("Light Blue Wool")
        'minecraft:light_blue_wool'
    """
    converter = get_converter()
    result = converter.convert(grabcraft_name, x, y, z, layer)
    return result.to_command_string() if result else None


def convert_grabcraft_to_java_detailed(grabcraft_name: str) -> Optional[JavaBlock]:
    """
    Convert a GrabCraft block name to Java Edition with detailed result.

    Returns JavaBlock with separate block_id and states dict.
    """
    converter = get_converter()
    return converter.convert(grabcraft_name)


# =============================================================================
# MAIN - TEST/DEMO
# =============================================================================

if __name__ == '__main__':
    test_cases = [
        # Stairs
        "Oak Wood Stairs (North, Normal)",
        "Oak Wood Stairs (South, Upside-down)",
        "Cobblestone Stairs (East, Normal)",
        "Stone Brick Stairs (West, Upside-down)",
        "Quartz Stairs (North, Normal)",

        # Slabs
        "Stone Slab",
        "Stone Slab (Upper)",
        "Cobblestone Slab (Lower)",
        "Double Stone Brick Slab",
        "Oak Slab (Upper)",

        # Doors
        "Oak Door (Lower)",
        "Oak Door (Upper, North, Open)",
        "Iron Door (Lower, East)",
        "Spruce Door (Upper, South, Hinge Right)",

        # Trapdoors
        "Oak Trapdoor (North From Block, Open, Bottom)",
        "Iron Trapdoor (East From Block, Closed, Top)",

        # Chests & Storage
        "Chest (North)",
        "Chest (East)",
        "Trapped Chest (South)",
        "Ender Chest (West)",

        # Ladders & Torches
        "Ladder (facing north)",
        "Ladder (facing east)",
        "Torch (Facing Up)",
        "Torch (Facing North)",
        "Soul Torch (Facing West)",
        "Redstone Torch (Facing East)",

        # Vines
        "Vines ()",
        "Vines (North)",
        "Vines (South&East)",
        "Vines (North&West)",

        # Logs
        "Oak Wood (facing north/south)",
        "Oak Wood (facing east/west)",
        "Spruce Wood (facing up/down)",
        "Stripped Dark Oak Wood (facing east/west)",

        # Colored blocks
        "White Wool",
        "Light Blue Wool",
        "Orange Stained Clay",
        "Cyan Terracotta",
        "Red Concrete",
        "Lime Concrete Powder",
        "Magenta Stained Glass",
        "Purple Stained Glass Pane",
        "Yellow Carpet",
        "Pink Glazed Terracotta (North)",

        # Buttons & Levers
        "Wooden Button (Facing Down, Inactive)",
        "Stone Button (Facing North, Pressed)",
        "Lever (North, On)",

        # Pistons & Observers
        "Piston (Facing Up)",
        "Sticky Piston (Facing Down)",
        "Observer (Facing South, Powered)",
        "Dispenser (Facing East)",
        "Dropper (Facing Down)",
        "Hopper (North)",

        # Walls & Fences
        "Cobblestone Wall",
        "Stone Brick Wall",
        "Oak Fence Gate (North, Open)",

        # Leaves
        "Oak Leaves (No Decay)",
        "Acacia Leaves (No Decay and Check Decay)",

        # Redstone
        "Redstone Wire (Power:0)",
        "Redstone Wire (Power:15)",

        # Water
        "Water",
        "Still Water",

        # Flowers
        "Flower (Rose Bush, Lower)",
        "Flower (Lilac, Upper)",
        "Flower (Sunflower, Upper)",

        # Fire
        "Fire (Age 15)",
        "Fire",

        # Pressure Plates
        "Oak Pressure Plate",
        "Stone Pressure Plate",

        # Simple blocks
        "Stone",
        "Cobblestone",
        "Dirt",
        "Grass",
        "Glass",
        "Bookshelf",
        "Iron Bars",
        "Lily Pad",
        "Cobweb",
    ]

    print("GrabCraft to Java Edition Conversion Test")
    print("=" * 70)

    for test in test_cases:
        result = convert_grabcraft_to_java(test)
        print(f"\n{test}")
        print(f"  -> {result}")
