#!/usr/bin/env python3
"""
GrabCraft to Bedrock Edition Block Converter

Converts GrabCraft's human-readable block format (e.g., "Oak Wood Stairs (North, Normal)")
to Minecraft Bedrock Edition block IDs with proper numeric/bit-based states.

Based on GeyserMC/mappings patterns and Bedrock Edition 1.21+ block state system.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


# =============================================================================
# LOAD BEDROCK BLOCK STATE CONSTANTS FROM TOML
# =============================================================================

def _load_bedrock_states() -> dict:
    """Load Bedrock block state constants from TOML config."""
    config_path = Path(__file__).parent / "bedrock_states.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)

_BEDROCK_STATES = _load_bedrock_states()

# Direction mappings
STAIR_DIRECTION = _BEDROCK_STATES["stair_direction"]
BED_DIRECTION = _BEDROCK_STATES["bed_direction_map"]
SIXWAY_FACING = _BEDROCK_STATES["sixway_facing"]
HORIZONTAL_FACING = _BEDROCK_STATES["horizontal_facing"]
DOOR_DIRECTION = _BEDROCK_STATES["door_direction"]
VINE_BITS = _BEDROCK_STATES["vine_bits"]
TORCH_FACING_DIRECTION = _BEDROCK_STATES["torch_facing_direction"]
PILLAR_AXIS = _BEDROCK_STATES["pillar_axis"]
BUTTON_FACING = _BEDROCK_STATES["button_facing"]

# Block name mappings
JE_TO_BE_NAMES = _BEDROCK_STATES["je_to_be_names"]
GRABCRAFT_TO_BE = _BEDROCK_STATES["grabcraft_to_be"]
COLORS = _BEDROCK_STATES["colors"]["list"]
GRABCRAFT_COLOR_MAP = _BEDROCK_STATES["grabcraft_color_map"]

# Material mappings
STAIR_MATERIALS = _BEDROCK_STATES["stair_materials"]
SLAB_MATERIALS = _BEDROCK_STATES["slab_materials"]
DOUBLE_SLAB_TO_BLOCK = _BEDROCK_STATES["double_slab_to_block"]
DOOR_MATERIALS = _BEDROCK_STATES["door_materials"]
TRAPDOOR_MATERIALS = _BEDROCK_STATES["trapdoor_materials"]
WALL_MATERIALS = _BEDROCK_STATES["wall_materials"]


# =============================================================================
# RESULT DATA CLASS
# =============================================================================

@dataclass
class BedrockBlock:
    """Result of conversion to Bedrock Edition block."""
    block_id: str  # e.g., "minecraft:oak_stairs"
    states: dict   # e.g., {"weirdo_direction": 3, "upside_down_bit": False}
    
    def to_command_string(self) -> str:
        """Format as Bedrock /setblock command block specifier."""
        if not self.states:
            return self.block_id
        
        state_parts = []
        for key, value in self.states.items():
            if isinstance(value, bool):
                state_parts.append(f'"{key}"={str(value).lower()}')
            elif isinstance(value, int):
                state_parts.append(f'"{key}"={value}')
            else:
                state_parts.append(f'"{key}"="{value}"')
        
        return f'{self.block_id}[{",".join(state_parts)}]'


# =============================================================================
# BLOCK PARSING HELPERS
# =============================================================================

class BlockParser:
    """Helper methods for parsing block names and properties."""
    
    DIRECTION_MAP = {
        'north': 'north', 'south': 'south', 'east': 'east', 'west': 'west',
        'up': 'top', 'down': 'down',
        'facing north': 'north', 'facing south': 'south', 
        'facing east': 'east', 'facing west': 'west',
        'facing up': 'top', 'facing down': 'down',
    }

    @staticmethod
    def normalize_color(color_name: str, color_lookup: dict) -> Optional[str]:
        if not color_name:
            return None
        return color_lookup.get(color_name.lower().strip())

    @staticmethod
    def parse_direction_int(props: str, mapping: dict, default=0) -> int:
        props_lower = props.lower()
        for dir_name, dir_val in mapping.items():
            if dir_name in props_lower:
                return dir_val
        return default

    @staticmethod
    def get_material_block(material: str, mapping: dict, suffix: str = "") -> str:
        material = material.lower().strip()
        for mat_key, be_name in mapping.items():
            if material == mat_key or material.startswith(mat_key):
                return be_name
        return material.replace(' ', '_') + suffix


# =============================================================================
# CONVERTER INTERFACE
# =============================================================================

class BaseConverter:
    """Base class for specialized block converters."""
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        raise NotImplementedError


# =============================================================================
# CONVERTER IMPLEMENTATIONS
# =============================================================================

class StairConverter(BaseConverter):
    PATTERN = re.compile(
        r'^(.+?)\s+Stairs?\s*\(([^,)]+)(?:,\s*(Normal|Upside-down|Upside down))?\)?$',
        re.IGNORECASE
    )
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        direction = match.group(2).lower().strip()
        position = match.group(3).lower().strip() if match.group(3) else 'normal'
        
        block_name = BlockParser.get_material_block(material, STAIR_MATERIALS, "_stairs")
        weirdo_dir = STAIR_DIRECTION.get(direction, 3)
        upside_down = position in ('upside-down', 'upside down', 'top', 'upper')
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'weirdo_direction': weirdo_dir,
                'upside_down_bit': upside_down,
            }
        )

class SlabConverter(BaseConverter):
    PATTERN = re.compile(
        r'^(?:(Double)\s+)?(.+?)\s+Slab\s*(?:\((Upper|Lower|Top|Bottom)\))?$',
        re.IGNORECASE
    )
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None
        
        is_double = match.group(1) is not None
        material = match.group(2).lower().strip()
        position = match.group(3).lower().strip() if match.group(3) else 'bottom'
        
        if is_double:
            block_name = DOUBLE_SLAB_TO_BLOCK.get(material, material.replace(' ', '_'))
            return BedrockBlock(block_id=f'minecraft:{block_name}', states={})
        
        block_name = BlockParser.get_material_block(material, SLAB_MATERIALS, "_slab")
        vertical_half = 'top' if position in ('upper', 'top') else 'bottom'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={'minecraft:vertical_half': vertical_half}
        )

class DoorConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Door\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_name = BlockParser.get_material_block(material, DOOR_MATERIALS, "_door")
        direction = BlockParser.parse_direction_int(props, DOOR_DIRECTION, 2)
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'direction': direction,
                'open_bit': 'open' in props and 'closed' not in props,
                'upper_block_bit': 'upper' in props,
                'door_hinge_bit': 'right' in props,
            }
        )

class TrapdoorConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Trapdoor\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_name = BlockParser.get_material_block(material, TRAPDOOR_MATERIALS, "_trapdoor")
        direction = BlockParser.parse_direction_int(props, DOOR_DIRECTION, 0)
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'direction': direction,
                'open_bit': 'open' in props,
                'upside_down_bit': 'top' in props or 'upper' in props,
            }
        )

class ChestConverter(BaseConverter):
    PATTERN = re.compile(r'^(Trapped\s+|Ender\s+)?Chest\s*\(([^)]+)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        prefix, direction_str = (match.group(1) or "").lower().strip(), match.group(2).lower().strip()
        block_id = "ender_chest" if "ender" in prefix else ("trapped_chest" if "trapped" in prefix else "chest")
        direction = HORIZONTAL_FACING.get(direction_str, 2)
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={'facing_direction': direction})

class FurnaceConverter(BaseConverter):
    PATTERN = re.compile(r'^(Blast\s+|)Furnace\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        prefix, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_id = "blast_furnace" if "blast" in prefix else "furnace"
        direction = HORIZONTAL_FACING.get(props, 2)
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={'facing_direction': direction})

class LadderConverter(BaseConverter):
    PATTERN = re.compile(r'^Ladder\s*\((?:facing\s+)?([^)]+)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        direction = HORIZONTAL_FACING.get(match.group(1).lower().strip(), 2)
        return BedrockBlock(block_id='minecraft:ladder', states={'facing_direction': direction})

class TorchConverter(BaseConverter):
    PATTERN = re.compile(r'^(Soul\s+|Redstone\s+)?Torch\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        prefix, props = (match.group(1) or "").lower().strip(), (match.group(2) or "up").lower().strip()
        block_id = "soul_torch" if "soul" in prefix else ("redstone_torch" if "redstone" in prefix else "torch")
        direction = parser._parse_direction(props) or "west"
        direction = TORCH_FACING_DIRECTION.get(direction, 2)
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={'torch_facing_direction': direction})

class VineConverter(BaseConverter):
    PATTERN = re.compile(r'^Vines?\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        props = match.group(1).lower().strip()
        bits = 0
        for dir_name, bit_val in VINE_BITS.items():
            if dir_name in props: bits |= bit_val
        return BedrockBlock(block_id='minecraft:vine', states={'vine_direction_bits': bits})

class LogConverter(BaseConverter):
    PATTERN = re.compile(r'^(?:Stripped\s+)?(.+?)\s+(Wood|Log|Stem)\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, wood_type, props = match.group(1).lower().strip(), match.group(2).lower().strip(), match.group(3).lower().strip()
        is_stripped = "stripped" in name.lower()
        
        # Determine if it's a log or wood
        suffix = "_log"
        if wood_type == "wood" or wood_type == "stem":
            suffix = "_wood" if wood_type == "wood" else "_stem"
        
        block_name = GRABCRAFT_TO_BE.get(material, material.replace(' ', '_'))
        
        # If block_name already ends with _log or _wood, don't append suffix
        if not (block_name.endswith("_log") or block_name.endswith("_wood") or block_name.endswith("_stem")):
            block_name = f"{block_name}{suffix}"
            
        if is_stripped and not block_name.startswith("stripped_"):
            block_name = f"stripped_{block_name}"
            
        axis = PILLAR_AXIS.get(props, "y")
        return BedrockBlock(block_id=f'minecraft:{block_name}', states={'pillar_axis': axis})

class ButtonConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Button\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, props = match.group(1).lower().strip(), match.group(2).lower().strip()
        block_name = f"{material.replace(' ', '_')}_button"
        facing = BUTTON_FACING.get(props, 0)
        return BedrockBlock(block_id=f'minecraft:{block_name}', states={'facing_direction': facing, 'button_pressed_bit': False})

class LeverConverter(BaseConverter):
    PATTERN = re.compile(r'^Lever\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        props = match.group(1).lower().strip()
        lever_dir = "down_x_axis"
        if 'up' in props: lever_dir = "up_x_axis"
        elif 'north' in props: lever_dir = "north"
        elif 'south' in props: lever_dir = "south"
        elif 'east' in props: lever_dir = "east"
        elif 'west' in props: lever_dir = "west"
        return BedrockBlock(block_id='minecraft:lever', states={'lever_direction': lever_dir, 'open_bit': 'on' in props})

class PistonConverter(BaseConverter):
    PATTERN = re.compile(r'^(Sticky\s+)?Piston\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        is_sticky, props = match.group(1), match.group(2).lower().strip()
        block_id = "sticky_piston" if is_sticky else "piston"
        facing = SIXWAY_FACING.get(props, 0)
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={'facing_direction': facing})

class ObserverConverter(BaseConverter):
    PATTERN = re.compile(r'^Observer\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        facing = SIXWAY_FACING.get(match.group(1).lower().strip(), 0)
        return BedrockBlock(block_id='minecraft:observer', states={'facing_direction': facing})

class DispenserConverter(BaseConverter):
    PATTERN = re.compile(r'^(Dispenser|Dropper)\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        block_id, facing_str = match.group(1).lower(), match.group(2).lower().strip()
        facing = SIXWAY_FACING.get(facing_str, 0)
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={'facing_direction': facing})

class HopperConverter(BaseConverter):
    PATTERN = re.compile(r'^Hopper\s*\(([^)]*)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        facing = SIXWAY_FACING.get(match.group(1).lower().strip(), 0)
        return BedrockBlock(block_id='minecraft:hopper', states={'facing_direction': facing})

class WallConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Wall$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material = match.group(1).lower().strip()
        block_name = BlockParser.get_material_block(material, WALL_MATERIALS, "_wall")
        return BedrockBlock(block_id=f'minecraft:{block_name}', states={})

class FenceGateConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Fence\s+Gate\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material, props = match.group(1).lower().strip(), (match.group(2) or "").lower().strip()
        block_name = f"{material.replace(' ', '_')}_fence_gate"
        direction = HORIZONTAL_FACING.get(props, 2)
        return BedrockBlock(block_id=f'minecraft:{block_name}', states={'facing_direction': direction, 'open_bit': 'open' in props})

class LeavesConverter(BaseConverter):
    PATTERN = re.compile(r'^(.+?)\s+Leaves\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material = match.group(1).lower().strip()
        block_name = f"{material.replace(' ', '_')}_leaves"
        return BedrockBlock(block_id=f'minecraft:{block_name}', states={'persistent_bit': True, 'update_bit': False})

class RedstoneWireConverter(BaseConverter):
    PATTERN = re.compile(r'^Redstone\s+Wire\s*\(Power:\s*(\d+)\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        power = int(match.group(1))
        return BedrockBlock(block_id='minecraft:redstone_wire', states={'redstone_signal': power})

class WaterConverter(BaseConverter):
    PATTERN = re.compile(r'^(?:Still\s+)?Water\s*(?:\(([^)]*)\))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        return BedrockBlock(block_id='minecraft:water', states={'liquid_depth': 0})

class FlowerConverter(BaseConverter):
    PATTERN = re.compile(r'^Flower\s*\(([^,]+)(?:,\s*(Upper|Lower))?\)$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        flower_type, position = match.group(1).lower().strip(), (match.group(2) or "lower").lower().strip()
        block_id = GRABCRAFT_TO_BE.get(flower_type, flower_type.replace(' ', '_'))
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={'upper_block_bit': position == 'upper'})

class ColoredBlockConverter(BaseConverter):
    """Generic converter for colored blocks (wool, terracotta, concrete, etc.)"""
    def __init__(self, pattern, block_type, suffix=""):
        self.PATTERN = pattern
        self.block_type = block_type
        self.suffix = suffix
        
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        color_name = match.group(1).lower().strip()
        normalized_color = parser._normalize_color(color_name)
        final_color = normalized_color if normalized_color else color_name.replace(" ", "_")
        return BedrockBlock(block_id=f'minecraft:{final_color}_{self.block_type}{self.suffix}', states={})

class BedConverter(BaseConverter):
    # Match both "Bed (...)" format and check for Foot/Head
    PATTERN = re.compile(
        r'^(?!(?:' + '|'.join(COLORS) + r')\s+)Bed\s*(?:\(([^)]*)\))?',
        re.IGNORECASE
    )

    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match:
            return None

        props = (match.group(1) or "").lower()

        # Check if this is a foot piece - skip it
        if "foot" in props:
            return BedrockBlock(block_id='__SKIP__', states={})  # Special marker to skip

        direction = 0
        for dir_name, dir_val in BED_DIRECTION.items():
            if dir_name in props:
                direction = dir_val
                break

        occupied = "occupied" in props

        states = {
            'direction': direction,
            'occupied_bit': occupied,
            'head_piece_bit': True
        }

        return BedrockBlock(block_id='minecraft:bed', states=states)

class SignConverter(BaseConverter):
    PATTERN = re.compile(r'^(?:(.+?)\s+)?(?:Wall[- ]?(?:mounted|Mounted)?\s*)?Sign(?:\s+Block)?\s*[,\s]*(?:\(([^)]*)\)|(.+))?$', re.IGNORECASE)
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        match = self.PATTERN.match(name)
        if not match: return None
        material = (match.group(1) or "Oak").lower().strip()
        props = (match.group(2) or match.group(3) or "").lower().strip()

        is_wall = "wall" in name.lower() or "mounted" in props
        block_base = DOOR_MATERIALS.get(material, material.replace(' ', '_'))
        block_id = f"minecraft:{block_base}_wall_sign" if is_wall else f"minecraft:{block_base}_standing_sign"

        states = {}
        if is_wall:
            states['facing_direction'] = HORIZONTAL_FACING.get(props, 2)
        else:
            # Simple rotation mapping
            rot_map = {'south': 0, 'west': 4, 'north': 8, 'east': 12}
            states['ground_sign_direction'] = rot_map.get(props, 0)

        return BedrockBlock(block_id=block_id, states=states)

class SimpleBlockConverter(BaseConverter):
    """Fallback converter for simple blocks with no states."""
    def convert(self, name: str, parser: 'GrabCraftToBedrockConverter') -> Optional[BedrockBlock]:
        clean_name = name.lower().strip()
        block_id = GRABCRAFT_TO_BE.get(clean_name)
        if not block_id:
            block_id = JE_TO_BE_NAMES.get(clean_name)
        if not block_id:
            block_id = clean_name.replace(' ', '_')
        return BedrockBlock(block_id=f'minecraft:{block_id}', states={})

# =============================================================================
# MAIN CONVERTER CLASS
# =============================================================================

class GrabCraftToBedrockConverter:
    """
    Converts GrabCraft's human-readable block format to Bedrock Edition.
    """
    
    def __init__(self):
        """Initialize converter with lookup tables and sub-converters."""
        self._build_color_lookup()
        self._init_converters()
    
    def _build_color_lookup(self):
        """Build color name lookup table."""
        self.color_lookup = {color: color for color in COLORS}
        # Add space-separated versions
        self.color_lookup.update({color.replace('_', ' '): color for color in COLORS})
        # Add custom GrabCraft mappings
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
        """Normalize color name to Bedrock format."""
        if not color_name: return None
        return self.color_lookup.get(color_name.lower().strip())
    
    def _parse_direction(self, direction_str: str) -> Optional[str]:
        """Parse direction from GrabCraft format."""
        return BlockParser.DIRECTION_MAP.get(direction_str.lower().strip())
    
    def convert(self, grabcraft_name: str) -> Optional[BedrockBlock]:
        """
        Convert a GrabCraft block name to Bedrock Edition format.
        """
        if not grabcraft_name or not grabcraft_name.strip():
            return None
        
        name = grabcraft_name.strip()
        for converter in self.converters:
            result = converter.convert(name, self)
            if result is not None:
                return result
        
        return None
# CONVENIENCE FUNCTIONS
# =============================================================================

_converter = None

def get_converter() -> GrabCraftToBedrockConverter:
    """Get singleton converter instance."""
    global _converter
    if _converter is None:
        _converter = GrabCraftToBedrockConverter()
    return _converter


def convert_grabcraft_to_bedrock(grabcraft_name: str) -> Optional[str]:
    """
    Convert a GrabCraft block name to Bedrock Edition command string.
    
    Args:
        grabcraft_name: Block name from GrabCraft (e.g., "Oak Wood Stairs (North, Normal)")
        
    Returns:
        Bedrock block command string (e.g., 'minecraft:oak_stairs["weirdo_direction"=3,"upside_down_bit"=false]')
        or None if conversion failed.
    
    Examples:
        >>> convert_grabcraft_to_bedrock("Oak Wood Stairs (North, Normal)")
        'minecraft:oak_stairs["weirdo_direction"=3,"upside_down_bit"=false]'
        
        >>> convert_grabcraft_to_bedrock("Cobblestone Slab (Upper)")
        'minecraft:cobblestone_slab["minecraft:vertical_half"="top"]'
        
        >>> convert_grabcraft_to_bedrock("Light Blue Wool")
        'minecraft:light_blue_wool'
    """
    converter = get_converter()
    result = converter.convert(grabcraft_name)
    return result.to_command_string() if result else None


def convert_grabcraft_to_bedrock_detailed(grabcraft_name: str) -> Optional[BedrockBlock]:
    """
    Convert a GrabCraft block name to Bedrock Edition with detailed result.
    
    Returns BedrockBlock with separate block_id and states dict,
    useful when you need to manipulate states programmatically.
    """
    converter = get_converter()
    return converter.convert(grabcraft_name)


# =============================================================================
# MAIN - TEST/DEMO
# =============================================================================

if __name__ == '__main__':
    # Test cases
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
        "Redstone Torch (on) (Facing East)",
        
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
        "Water (Water level Max)",
        "Water (Water level Max - 1, Falling)",
        
        # Flowers
        "Flower (Rose Bush, Lower)",
        "Flower (Lilac, Upper)",
        "Flower (Sunflower, Upper)",
        
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
    
    print("GrabCraft to Bedrock Edition Conversion Test")
    print("=" * 70)
    
    for test in test_cases:
        result = convert_grabcraft_to_bedrock(test)
        print(f"\n{test}")
        print(f"  -> {result}")
