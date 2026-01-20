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
SIXWAY_FACING = _BEDROCK_STATES["sixway_facing"]
HORIZONTAL_FACING = _BEDROCK_STATES["horizontal_facing"]
DOOR_DIRECTION = _BEDROCK_STATES["door_direction"]
VINE_BITS = _BEDROCK_STATES["vine_bits"]
TORCH_FACING = _BEDROCK_STATES["torch_facing"]
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
# MAIN CONVERTER CLASS
# =============================================================================

class GrabCraftToBedrockConverter:
    """
    Converts GrabCraft's human-readable block format to Bedrock Edition.
    
    Examples:
        "Oak Wood Stairs (North, Normal)" -> minecraft:oak_stairs["weirdo_direction"=3,"upside_down_bit"=false]
        "Cobblestone Slab (Upper)" -> minecraft:cobblestone_slab["minecraft:vertical_half"="top"]
        "Chest (East)" -> minecraft:chest["facing_direction"=5]
        "Vines (North&West)" -> minecraft:vine["vine_direction_bits"=6]
    """
    
    # Regex patterns for parsing GrabCraft names
    STAIRS_PATTERN = re.compile(
        r'^(.+?)\s+Stairs?\s*\(([^,)]+)(?:,\s*(Normal|Upside-down|Upside down))?\)?$',
        re.IGNORECASE
    )
    
    SLAB_PATTERN = re.compile(
        r'^(?:(Double)\s+)?(.+?)\s+Slab\s*(?:\((Upper|Lower|Top|Bottom)\))?$',
        re.IGNORECASE
    )
    
    DOOR_PATTERN = re.compile(
        r'^(.+?)\s+Door\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    TRAPDOOR_PATTERN = re.compile(
        r'^(.+?)\s+Trapdoor\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    CHEST_PATTERN = re.compile(
        r'^(Trapped\s+|Ender\s+)?Chest\s*\(([^)]+)\)$',
        re.IGNORECASE
    )
    
    FURNACE_PATTERN = re.compile(
        r'^(Blast\s+|)Furnace\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    LADDER_PATTERN = re.compile(
        r'^Ladder\s*\((?:facing\s+)?([^)]+)\)$',
        re.IGNORECASE
    )
    
    TORCH_PATTERN = re.compile(
        r'^(Soul\s+|Redstone\s+)?Torch\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    VINE_PATTERN = re.compile(
        r'^Vines?\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    LOG_PATTERN = re.compile(
        r'^(?:Stripped\s+)?(.+?)\s+(?:Wood|Log|Stem)\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    BUTTON_PATTERN = re.compile(
        r'^(.+?)\s+Button\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    LEVER_PATTERN = re.compile(
        r'^Lever\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    PISTON_PATTERN = re.compile(
        r'^(Sticky\s+)?Piston\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    OBSERVER_PATTERN = re.compile(
        r'^Observer\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    DISPENSER_PATTERN = re.compile(
        r'^(Dispenser|Dropper)\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    HOPPER_PATTERN = re.compile(
        r'^Hopper\s*\(([^)]*)\)$',
        re.IGNORECASE
    )
    
    WALL_PATTERN = re.compile(
        r'^(.+?)\s+Wall$',
        re.IGNORECASE
    )
    
    FENCE_GATE_PATTERN = re.compile(
        r'^(.+?)\s+Fence\s+Gate\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    LEAVES_PATTERN = re.compile(
        r'^(.+?)\s+Leaves\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    REDSTONE_WIRE_PATTERN = re.compile(
        r'^Redstone\s+Wire\s*\(Power:\s*(\d+)\)$',
        re.IGNORECASE
    )
    
    WATER_PATTERN = re.compile(
        r'^(?:Still\s+)?Water\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    FLOWER_PATTERN = re.compile(
        r'^Flower\s*\(([^,]+)(?:,\s*(Upper|Lower))?\)$',
        re.IGNORECASE
    )

    SIGN_PATTERN = re.compile(
        r'^(?:(.+?)\s+)?(?:Wall[- ]?(?:mounted|Mounted)?\s*)?Sign(?:\s+Block)?\s*[,\s]*(?:\(([^)]*)\)|(.+))?$',
        re.IGNORECASE
    )

    # Colored block patterns
    COLORED_WOOL_PATTERN = re.compile(
        r'^(.+?)\s+Wool$',
        re.IGNORECASE
    )
    
    COLORED_TERRACOTTA_PATTERN = re.compile(
        r'^(.+?)\s+(?:Stained\s+Clay|Terracotta)$',
        re.IGNORECASE
    )
    
    COLORED_CONCRETE_PATTERN = re.compile(
        r'^(.+?)\s+Concrete(?:\s+Powder)?$',
        re.IGNORECASE
    )
    
    COLORED_GLASS_PATTERN = re.compile(
        r'^(.+?)\s+(?:Stained\s+)?Glass(?:\s+Pane)?$',
        re.IGNORECASE
    )
    
    COLORED_CARPET_PATTERN = re.compile(
        r'^(.+?)\s+Carpet$',
        re.IGNORECASE
    )
    
    COLORED_BED_PATTERN = re.compile(
        r'^(.+?)\s+Bed\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    COLORED_CANDLE_PATTERN = re.compile(
        r'^(.+?)\s+Candle\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    COLORED_SHULKER_PATTERN = re.compile(
        r'^(.+?)\s+Shulker\s+Box\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    GLAZED_TERRACOTTA_PATTERN = re.compile(
        r'^(.+?)\s+Glazed\s+Terracotta\s*(?:\(([^)]*)\))?$',
        re.IGNORECASE
    )
    
    def __init__(self):
        """Initialize converter with lookup tables."""
        self._build_color_lookup()
    
    def _build_color_lookup(self):
        """Build color name lookup table."""
        self.color_lookup = {}
        for color in COLORS:
            # Standard form
            self.color_lookup[color] = color
            # With spaces
            self.color_lookup[color.replace('_', ' ')] = color
        
        # Add variations
        self.color_lookup.update(GRABCRAFT_COLOR_MAP)
    
    def _normalize_color(self, color_name: str) -> Optional[str]:
        """Normalize color name to Bedrock format."""
        return self.color_lookup.get(color_name.lower().strip())
    
    def _parse_direction(self, direction_str: str) -> Optional[str]:
        """Parse direction from GrabCraft format."""
        direction_str = direction_str.lower().strip()
        
        # Handle compound directions
        if '&' in direction_str or 'and' in direction_str.lower():
            return direction_str  # Handle in vine converter
        
        # Map common variations
        direction_map = {
            'north': 'north',
            'south': 'south',
            'east': 'east',
            'west': 'west',
            'up': 'up',
            'down': 'down',
            'facing north': 'north',
            'facing south': 'south',
            'facing east': 'east',
            'facing west': 'west',
            'facing up': 'up',
            'facing down': 'down',
        }
        
        return direction_map.get(direction_str)
    
    def convert(self, grabcraft_name: str) -> Optional[BedrockBlock]:
        """
        Convert a GrabCraft block name to Bedrock Edition format.
        
        Args:
            grabcraft_name: Block name from GrabCraft (e.g., "Oak Wood Stairs (North, Normal)")
            
        Returns:
            BedrockBlock with block_id and states, or None if conversion failed.
        """
        if not grabcraft_name or grabcraft_name.strip() == '':
            return None
        
        name = grabcraft_name.strip()
        
        # Try each converter in order of specificity
        converters = [
            self._convert_stairs,
            self._convert_slab,
            self._convert_door,
            self._convert_trapdoor,
            self._convert_chest,
            self._convert_furnace,
            self._convert_ladder,
            self._convert_torch,
            self._convert_vine,
            self._convert_log,
            self._convert_button,
            self._convert_lever,
            self._convert_piston,
            self._convert_observer,
            self._convert_dispenser,
            self._convert_hopper,
            self._convert_wall,
            self._convert_fence_gate,
            self._convert_leaves,
            self._convert_redstone_wire,
            self._convert_water,
            self._convert_flower,
            self._convert_sign,
            self._convert_colored_wool,
            self._convert_colored_terracotta,
            self._convert_colored_concrete,
            self._convert_colored_glass,
            self._convert_colored_carpet,
            self._convert_colored_bed,
            self._convert_colored_candle,
            self._convert_colored_shulker,
            self._convert_glazed_terracotta,
            self._convert_simple_block,  # Fallback
        ]
        
        for converter in converters:
            result = converter(name)
            if result is not None:
                return result
        
        return None
    
    def _convert_stairs(self, name: str) -> Optional[BedrockBlock]:
        """Convert stair blocks."""
        match = self.STAIRS_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        direction = match.group(2).lower().strip()
        position = match.group(3).lower().strip() if match.group(3) else 'normal'
        
        # Get block ID
        block_name = None
        for mat_key, be_name in STAIR_MATERIALS.items():
            if material == mat_key or material.startswith(mat_key):
                block_name = be_name
                break
        
        if not block_name:
            # Try to construct from material name
            block_name = material.replace(' ', '_') + '_stairs'
        
        # Convert direction to weirdo_direction
        weirdo_dir = STAIR_DIRECTION.get(direction, 3)  # Default north
        
        # Convert position to upside_down_bit
        upside_down = position in ('upside-down', 'upside down', 'top', 'upper')
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'weirdo_direction': weirdo_dir,
                'upside_down_bit': upside_down,
            }
        )
    
    def _convert_slab(self, name: str) -> Optional[BedrockBlock]:
        """Convert slab blocks."""
        match = self.SLAB_PATTERN.match(name)
        if not match:
            return None
        
        is_double = match.group(1) is not None
        material = match.group(2).lower().strip()
        position = match.group(3).lower().strip() if match.group(3) else 'bottom'
        
        if is_double:
            # Double slabs -> full blocks
            block_name = DOUBLE_SLAB_TO_BLOCK.get(material)
            if not block_name:
                block_name = material.replace(' ', '_')
            return BedrockBlock(
                block_id=f'minecraft:{block_name}',
                states={}
            )
        
        # Regular slab
        block_name = SLAB_MATERIALS.get(material)
        if not block_name:
            block_name = material.replace(' ', '_') + '_slab'
        
        # Convert position to minecraft:vertical_half (BE 1.21+)
        vertical_half = 'top' if position in ('upper', 'top') else 'bottom'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'minecraft:vertical_half': vertical_half,
            }
        )
    
    def _convert_door(self, name: str) -> Optional[BedrockBlock]:
        """Convert door blocks."""
        match = self.DOOR_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        props = match.group(2).lower().strip()
        
        # Get block name
        block_name = DOOR_MATERIALS.get(material)
        if not block_name:
            block_name = material.replace(' ', '_') + '_door'
        
        # Parse properties
        is_upper = 'upper' in props
        is_open = 'open' in props and 'closed' not in props
        
        # Parse direction
        direction = 2  # Default west
        for dir_name, dir_val in DOOR_DIRECTION.items():
            if dir_name in props:
                direction = dir_val
                break
        
        # Parse hinge
        hinge_right = 'right' in props
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'direction': direction,
                'open_bit': is_open,
                'upper_block_bit': is_upper,
                'door_hinge_bit': hinge_right,
            }
        )
    
    def _convert_trapdoor(self, name: str) -> Optional[BedrockBlock]:
        """Convert trapdoor blocks."""
        match = self.TRAPDOOR_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        props = match.group(2).lower().strip()
        
        block_name = TRAPDOOR_MATERIALS.get(material)
        if not block_name:
            block_name = material.replace(' ', '_') + '_trapdoor'
        
        # Parse properties
        is_open = 'open' in props
        is_top = 'top' in props or 'upper' in props
        
        # Parse direction (trapdoors use 0-3)
        direction = 0
        for dir_name, dir_val in DOOR_DIRECTION.items():
            if dir_name in props:
                direction = dir_val
                break
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'direction': direction,
                'open_bit': is_open,
                'upside_down_bit': is_top,
            }
        )
    
    def _convert_chest(self, name: str) -> Optional[BedrockBlock]:
        """Convert chest blocks."""
        match = self.CHEST_PATTERN.match(name)
        if not match:
            return None
        
        prefix = (match.group(1) or '').lower().strip()
        direction = match.group(2).lower().strip()
        
        if 'trapped' in prefix:
            block_name = 'trapped_chest'
        elif 'ender' in prefix:
            block_name = 'ender_chest'
        else:
            block_name = 'chest'
        
        facing = HORIZONTAL_FACING.get(direction, 2)  # Default north
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'facing_direction': facing,
            }
        )
    
    def _convert_furnace(self, name: str) -> Optional[BedrockBlock]:
        """Convert furnace blocks."""
        match = self.FURNACE_PATTERN.match(name)
        if not match:
            return None
        
        prefix = (match.group(1) or '').lower().strip()
        props = match.group(2).lower().strip()
        
        if 'blast' in prefix:
            block_name = 'blast_furnace'
        else:
            block_name = 'furnace'
        
        # Check if lit
        is_lit = 'lit' in props or 'active' in props
        if is_lit:
            block_name = 'lit_' + block_name
        
        # Parse direction
        facing = 2  # Default north
        for dir_name, dir_val in HORIZONTAL_FACING.items():
            if dir_name in props:
                facing = dir_val
                break
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'facing_direction': facing,
            }
        )
    
    def _convert_ladder(self, name: str) -> Optional[BedrockBlock]:
        """Convert ladder blocks."""
        match = self.LADDER_PATTERN.match(name)
        if not match:
            return None
        
        direction = match.group(1).lower().strip()
        facing = HORIZONTAL_FACING.get(direction, 2)  # Default north
        
        return BedrockBlock(
            block_id='minecraft:ladder',
            states={
                'facing_direction': facing,
            }
        )
    
    def _convert_torch(self, name: str) -> Optional[BedrockBlock]:
        """Convert torch blocks (including redstone and soul torches)."""
        match = self.TORCH_PATTERN.match(name)
        if not match:
            return None
        
        prefix = (match.group(1) or '').lower().strip()
        direction = (match.group(2) or 'up').lower().strip()
        
        # Determine torch type
        if 'soul' in prefix:
            block_name = 'soul_torch'
        elif 'redstone' in prefix:
            # Check if active/on
            if '(on)' in name.lower() or 'active' in name.lower():
                block_name = 'redstone_torch'
            else:
                block_name = 'unlit_redstone_torch'
        else:
            block_name = 'torch'
        
        # Parse direction
        torch_facing = 'top'  # Default standing
        for dir_name, facing_val in TORCH_FACING.items():
            if dir_name in direction:
                torch_facing = facing_val
                break
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'torch_facing_direction': torch_facing,
            }
        )
    
    def _convert_vine(self, name: str) -> Optional[BedrockBlock]:
        """Convert vine blocks with directional bits."""
        match = self.VINE_PATTERN.match(name)
        if not match:
            return None
        
        directions_str = match.group(1).strip()
        
        if not directions_str:
            return BedrockBlock(
                block_id='minecraft:vine',
                states={'vine_direction_bits': 0}
            )
        
        # Parse compound directions (North&West, etc.)
        directions_str = directions_str.lower()
        directions = re.split(r'[&,\s]+', directions_str)
        
        vine_bits = 0
        for d in directions:
            d = d.strip()
            if d in VINE_BITS:
                vine_bits |= VINE_BITS[d]
        
        return BedrockBlock(
            block_id='minecraft:vine',
            states={
                'vine_direction_bits': vine_bits,
            }
        )
    
    def _convert_log(self, name: str) -> Optional[BedrockBlock]:
        """Convert log/wood blocks with axis."""
        match = self.LOG_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        axis_str = match.group(2).lower().strip()
        
        # Determine block name
        is_stripped = 'stripped' in name.lower()
        
        # Map material to block
        block_suffix = '_log'
        if 'stem' in name.lower():
            block_suffix = '_stem'
        
        block_name = material.replace(' ', '_') + block_suffix
        if is_stripped:
            block_name = 'stripped_' + block_name
        
        # Parse axis
        axis = 'y'  # Default vertical
        if 'north' in axis_str or 'south' in axis_str or axis_str == 'z':
            axis = 'z'
        elif 'east' in axis_str or 'west' in axis_str or axis_str == 'x':
            axis = 'x'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'pillar_axis': axis,
            }
        )
    
    def _convert_button(self, name: str) -> Optional[BedrockBlock]:
        """Convert button blocks."""
        match = self.BUTTON_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        props = match.group(2).lower().strip()
        
        # Determine button type
        if 'stone' in material:
            block_name = 'stone_button'
        elif 'polished blackstone' in material:
            block_name = 'polished_blackstone_button'
        elif any(wood in material for wood in ['oak', 'spruce', 'birch', 'jungle', 'acacia', 'dark oak', 'mangrove', 'cherry', 'bamboo', 'crimson', 'warped']):
            block_name = material.replace(' ', '_').replace('wood', '').strip('_') + '_button'
        else:
            block_name = 'wooden_button'  # Default
        
        # Parse facing
        facing = 1  # Default up
        for dir_name, dir_val in BUTTON_FACING.items():
            if dir_name in props:
                facing = dir_val
                break
        
        # Parse powered state
        powered = 'pressed' in props or 'active' in props
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'facing_direction': facing,
                'button_pressed_bit': powered,
            }
        )
    
    def _convert_lever(self, name: str) -> Optional[BedrockBlock]:
        """Convert lever blocks."""
        match = self.LEVER_PATTERN.match(name)
        if not match:
            return None
        
        props = match.group(1).lower().strip()
        
        # Lever uses lever_direction string state in BE
        lever_direction = 'up_east_west'  # Default
        
        if 'down' in props and ('north' in props or 'south' in props):
            lever_direction = 'down_north_south'
        elif 'down' in props:
            lever_direction = 'down_east_west'
        elif 'up' in props and ('north' in props or 'south' in props):
            lever_direction = 'up_north_south'
        elif 'up' in props:
            lever_direction = 'up_east_west'
        elif 'north' in props:
            lever_direction = 'north'
        elif 'south' in props:
            lever_direction = 'south'
        elif 'east' in props:
            lever_direction = 'east'
        elif 'west' in props:
            lever_direction = 'west'
        
        powered = 'on' in props or 'active' in props
        
        return BedrockBlock(
            block_id='minecraft:lever',
            states={
                'lever_direction': lever_direction,
                'open_bit': powered,
            }
        )
    
    def _convert_piston(self, name: str) -> Optional[BedrockBlock]:
        """Convert piston blocks."""
        match = self.PISTON_PATTERN.match(name)
        if not match:
            return None
        
        is_sticky = match.group(1) is not None
        props = match.group(2).lower().strip()
        
        block_name = 'sticky_piston' if is_sticky else 'piston'
        
        # Parse facing
        facing = 1  # Default up
        for dir_name, dir_val in SIXWAY_FACING.items():
            if dir_name in props:
                facing = dir_val
                break
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'facing_direction': facing,
            }
        )
    
    def _convert_observer(self, name: str) -> Optional[BedrockBlock]:
        """Convert observer blocks."""
        match = self.OBSERVER_PATTERN.match(name)
        if not match:
            return None
        
        props = match.group(1).lower().strip()
        
        # Parse facing
        facing = 3  # Default south
        for dir_name, dir_val in SIXWAY_FACING.items():
            if dir_name in props:
                facing = dir_val
                break
        
        powered = 'powered' in props or 'active' in props
        
        return BedrockBlock(
            block_id='minecraft:observer',
            states={
                'facing_direction': facing,
                'powered_bit': powered,
            }
        )
    
    def _convert_dispenser(self, name: str) -> Optional[BedrockBlock]:
        """Convert dispenser/dropper blocks."""
        match = self.DISPENSER_PATTERN.match(name)
        if not match:
            return None
        
        block_type = match.group(1).lower().strip()
        props = match.group(2).lower().strip()
        
        block_name = 'dropper' if 'dropper' in block_type else 'dispenser'
        
        # Parse facing
        facing = 3  # Default south
        for dir_name, dir_val in SIXWAY_FACING.items():
            if dir_name in props:
                facing = dir_val
                break
        
        triggered = 'triggered' in props or 'active' in props
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'facing_direction': facing,
                'triggered_bit': triggered,
            }
        )
    
    def _convert_hopper(self, name: str) -> Optional[BedrockBlock]:
        """Convert hopper blocks."""
        match = self.HOPPER_PATTERN.match(name)
        if not match:
            return None
        
        props = match.group(1).lower().strip()
        
        # Hopper facing (output direction)
        facing = 0  # Default down
        if 'north' in props:
            facing = 2
        elif 'south' in props:
            facing = 3
        elif 'west' in props:
            facing = 4
        elif 'east' in props:
            facing = 5
        
        toggled = 'disabled' in props or 'locked' in props
        
        return BedrockBlock(
            block_id='minecraft:hopper',
            states={
                'facing_direction': facing,
                'toggle_bit': toggled,
            }
        )
    
    def _convert_wall(self, name: str) -> Optional[BedrockBlock]:
        """Convert wall blocks."""
        match = self.WALL_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        
        block_name = WALL_MATERIALS.get(material)
        if not block_name:
            block_name = material.replace(' ', '_') + '_wall'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={}  # Wall connections are calculated automatically
        )
    
    def _convert_fence_gate(self, name: str) -> Optional[BedrockBlock]:
        """Convert fence gate blocks."""
        match = self.FENCE_GATE_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        props = (match.group(2) or '').lower().strip()
        
        # Oak fence gate is just "fence_gate" in BE
        if 'oak' in material:
            block_name = 'fence_gate'
        else:
            block_name = material.replace(' ', '_') + '_fence_gate'
        
        # Parse direction
        direction = 0  # Default south
        if 'north' in props:
            direction = 2
        elif 'east' in props:
            direction = 1
        elif 'west' in props:
            direction = 3
        
        is_open = 'open' in props
        in_wall = 'wall' in props
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'direction': direction,
                'open_bit': is_open,
                'in_wall_bit': in_wall,
            }
        )
    
    def _convert_leaves(self, name: str) -> Optional[BedrockBlock]:
        """Convert leaf blocks."""
        match = self.LEAVES_PATTERN.match(name)
        if not match:
            return None
        
        material = match.group(1).lower().strip()
        props = (match.group(2) or '').lower().strip()
        
        block_name = material.replace(' ', '_') + '_leaves'
        
        # Parse persistence
        persistent = 'no decay' in props or 'persistent' in props
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'persistent_bit': persistent,
                'update_bit': False,
            }
        )
    
    def _convert_redstone_wire(self, name: str) -> Optional[BedrockBlock]:
        """Convert redstone wire with power level."""
        match = self.REDSTONE_WIRE_PATTERN.match(name)
        if not match:
            return None
        
        power = int(match.group(1))
        power = max(0, min(15, power))  # Clamp 0-15
        
        return BedrockBlock(
            block_id='minecraft:redstone_wire',
            states={
                'redstone_signal': power,
            }
        )
    
    def _convert_water(self, name: str) -> Optional[BedrockBlock]:
        """Convert water blocks with level."""
        match = self.WATER_PATTERN.match(name)
        if not match:
            return None
        
        props = (match.group(1) or '').lower().strip()
        
        # Parse water level (0 = full, 7 = almost empty, 8+ = falling)
        level = 0  # Default full
        
        if 'max' in props:
            if '- 1' in props or '-1' in props:
                level = 1
            elif '- 2' in props or '-2' in props:
                level = 2
            elif '- 3' in props or '-3' in props:
                level = 3
            # etc.
        
        if 'falling' in props:
            level |= 8  # Set falling bit
        
        return BedrockBlock(
            block_id='minecraft:water',
            states={
                'liquid_depth': level,
            }
        )
    
    def _convert_flower(self, name: str) -> Optional[BedrockBlock]:
        """Convert flower blocks (including tall flowers)."""
        match = self.FLOWER_PATTERN.match(name)
        if not match:
            return None
        
        flower_type = match.group(1).lower().strip()
        half = (match.group(2) or 'lower').lower().strip()
        
        # Map flower type to block name
        flower_map = {
            'rose bush': 'rose_bush',
            'lilac': 'lilac',
            'sunflower': 'sunflower',
            'peony': 'peony',
            'tall grass': 'tall_grass',
            'large fern': 'large_fern',
        }
        
        block_name = flower_map.get(flower_type, flower_type.replace(' ', '_'))
        
        # For tall flowers, upper/lower half
        is_upper = half == 'upper'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'upper_block_bit': is_upper,
            }
        )

    def _convert_sign(self, name: str) -> Optional[BedrockBlock]:
        """Convert sign blocks (wall signs and standing signs)."""
        match = self.SIGN_PATTERN.match(name)
        if not match:
            return None

        material = (match.group(1) or '').lower().strip()
        direction_in_parens = (match.group(2) or '').lower().strip()
        direction_after = (match.group(3) or '').lower().strip()

        # Combine direction from both possible locations
        direction_str = direction_in_parens or direction_after

        # Check if it's a wall sign
        is_wall = 'wall' in name.lower()

        # Determine sign material (oak is default)
        wood_types = ['oak', 'spruce', 'birch', 'jungle', 'acacia',
                      'dark oak', 'mangrove', 'cherry', 'bamboo',
                      'crimson', 'warped']

        sign_material = 'oak'  # Default
        for wood in wood_types:
            if wood in material:
                sign_material = wood.replace(' ', '_')
                break

        if is_wall:
            # Wall signs use facing_direction
            facing = 2  # Default north

            # Parse direction
            if 'west' in direction_str and 'north' in direction_str:
                facing = 4  # West
            elif 'east' in direction_str and 'north' in direction_str:
                facing = 5  # East
            elif 'west' in direction_str and 'south' in direction_str:
                facing = 4  # West
            elif 'east' in direction_str and 'south' in direction_str:
                facing = 5  # East
            elif 'west' in direction_str:
                facing = 4
            elif 'east' in direction_str:
                facing = 5
            elif 'north' in direction_str:
                facing = 2
            elif 'south' in direction_str:
                facing = 3

            return BedrockBlock(
                block_id='minecraft:wall_sign',
                states={
                    'facing_direction': facing,
                }
            )
        else:
            # Standing signs use ground_sign_direction (0-15 for rotation)
            rotation = 0  # Default

            # Parse rotation from direction
            direction_to_rotation = {
                'south': 0,
                'south-southwest': 1,
                'southwest': 2,
                'west-southwest': 3,
                'west': 4,
                'west-northwest': 5,
                'northwest': 6,
                'north-northwest': 7,
                'north': 8,
                'north-northeast': 9,
                'northeast': 10,
                'east-northeast': 11,
                'east': 12,
                'east-southeast': 13,
                'southeast': 14,
                'south-southeast': 15,
            }

            for dir_name, rot_value in direction_to_rotation.items():
                if dir_name in direction_str:
                    rotation = rot_value
                    break

            return BedrockBlock(
                block_id=f'minecraft:{sign_material}_standing_sign',
                states={
                    'ground_sign_direction': rotation,
                }
            )

    def _convert_colored_wool(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored wool blocks."""
        match = self.COLORED_WOOL_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        color = self._normalize_color(color_name)
        
        if not color:
            return None
        
        return BedrockBlock(
            block_id=f'minecraft:{color}_wool',
            states={}
        )
    
    def _convert_colored_terracotta(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored terracotta (stained clay) blocks."""
        match = self.COLORED_TERRACOTTA_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        color = self._normalize_color(color_name)
        
        if not color:
            # Might be uncolored terracotta
            if 'terracotta' in name.lower() and not any(c in name.lower() for c in COLORS):
                return BedrockBlock(
                    block_id='minecraft:hardened_clay',
                    states={}
                )
            return None
        
        return BedrockBlock(
            block_id=f'minecraft:{color}_terracotta',
            states={}
        )
    
    def _convert_colored_concrete(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored concrete blocks."""
        match = self.COLORED_CONCRETE_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        color = self._normalize_color(color_name)
        
        if not color:
            return None
        
        is_powder = 'powder' in name.lower()
        suffix = '_concrete_powder' if is_powder else '_concrete'
        
        return BedrockBlock(
            block_id=f'minecraft:{color}{suffix}',
            states={}
        )
    
    def _convert_colored_glass(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored glass blocks."""
        match = self.COLORED_GLASS_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        
        # Check if it's actually colored or just "Glass"
        if color_name in ('', 'glass'):
            if 'pane' in name.lower():
                return BedrockBlock(block_id='minecraft:glass_pane', states={})
            return BedrockBlock(block_id='minecraft:glass', states={})
        
        color = self._normalize_color(color_name)
        if not color:
            return None
        
        is_pane = 'pane' in name.lower()
        
        if is_pane:
            return BedrockBlock(
                block_id=f'minecraft:{color}_stained_glass_pane',
                states={}
            )
        
        return BedrockBlock(
            block_id=f'minecraft:{color}_stained_glass',
            states={}
        )
    
    def _convert_colored_carpet(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored carpet blocks."""
        match = self.COLORED_CARPET_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        color = self._normalize_color(color_name)
        
        if not color:
            return None
        
        return BedrockBlock(
            block_id=f'minecraft:{color}_carpet',
            states={}
        )
    
    def _convert_colored_bed(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored bed blocks."""
        match = self.COLORED_BED_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        props = (match.group(2) or '').lower().strip()
        
        color = self._normalize_color(color_name)
        if not color:
            color = 'red'  # Default bed color
        
        # Parse properties
        is_head = 'head' in props
        direction = 0  # Default south
        for dir_name, dir_val in DOOR_DIRECTION.items():
            if dir_name in props:
                direction = dir_val
                break
        
        occupied = 'occupied' in props
        
        return BedrockBlock(
            block_id=f'minecraft:{color}_bed',  # BE 1.21+ uses colored bed IDs
            states={
                'direction': direction,
                'head_piece_bit': is_head,
                'occupied_bit': occupied,
            }
        )
    
    def _convert_colored_candle(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored candle blocks."""
        match = self.COLORED_CANDLE_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        props = (match.group(2) or '').lower().strip()
        
        color = self._normalize_color(color_name)
        
        # Parse candle count (1-4)
        candles = 1
        for n in ['1', '2', '3', '4', 'one', 'two', 'three', 'four']:
            if n in props:
                candles = {'1': 1, '2': 2, '3': 3, '4': 4,
                          'one': 1, 'two': 2, 'three': 3, 'four': 4}.get(n, 1)
                break
        
        lit = 'lit' in props
        
        if color:
            block_name = f'{color}_candle'
        else:
            block_name = 'candle'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={
                'candles': candles - 1,  # BE uses 0-3
                'lit': lit,
            }
        )
    
    def _convert_colored_shulker(self, name: str) -> Optional[BedrockBlock]:
        """Convert colored shulker box blocks."""
        match = self.COLORED_SHULKER_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        props = (match.group(2) or '').lower().strip()
        
        color = self._normalize_color(color_name)
        
        if color:
            block_name = f'{color}_shulker_box'
        else:
            block_name = 'undyed_shulker_box'
        
        return BedrockBlock(
            block_id=f'minecraft:{block_name}',
            states={}
        )
    
    def _convert_glazed_terracotta(self, name: str) -> Optional[BedrockBlock]:
        """Convert glazed terracotta blocks."""
        match = self.GLAZED_TERRACOTTA_PATTERN.match(name)
        if not match:
            return None
        
        color_name = match.group(1).lower().strip()
        props = (match.group(2) or '').lower().strip()
        
        color = self._normalize_color(color_name)
        if not color:
            return None
        
        # Parse facing
        facing = 2  # Default north
        for dir_name, dir_val in HORIZONTAL_FACING.items():
            if dir_name in props:
                facing = dir_val
                break
        
        return BedrockBlock(
            block_id=f'minecraft:{color}_glazed_terracotta',
            states={
                'facing_direction': facing,
            }
        )
    
    def _convert_simple_block(self, name: str) -> Optional[BedrockBlock]:
        """
        Fallback converter for simple blocks without complex states.
        Uses the GRABCRAFT_TO_BE mapping table.
        """
        # Remove any parenthetical content for lookup
        base_name = re.sub(r'\s*\([^)]*\)', '', name).strip()
        lookup_name = base_name.lower()
        
        # Try direct lookup
        if lookup_name in GRABCRAFT_TO_BE:
            block_name = GRABCRAFT_TO_BE[lookup_name]
            return BedrockBlock(
                block_id=f'minecraft:{block_name}',
                states={}
            )
        
        # Try converting to snake_case
        snake_name = lookup_name.replace(' ', '_')
        
        # Check JE->BE name changes
        if snake_name in JE_TO_BE_NAMES:
            block_name = JE_TO_BE_NAMES[snake_name]
            return BedrockBlock(
                block_id=f'minecraft:{block_name}',
                states={}
            )
        
        # Last resort: just use snake_case name
        return BedrockBlock(
            block_id=f'minecraft:{snake_name}',
            states={}
        )


# =============================================================================
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
