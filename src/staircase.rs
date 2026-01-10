// Staircase with landing and turnaround generator

/// Staircase configuration
pub struct StaircaseConfig<'a> {
    pub direction: &'a str,
    pub material: &'a str,
    pub x: i32,
    pub y: i32,
    pub z: i32,
    pub flight_height: i32,
    pub width: i32,                    // width of flight (default 2)
    pub num_flights: i32,              // number of flight pairs (up + down) (default 1)
    pub wall_material: Option<&'a str>, // None = no walls
    pub lantern: Option<&'a str>,      // None = no lanterns
    pub lantern_interval: i32,         // every N steps (default 3)
}

/// Get direction offsets (dx, dz) and opposite direction
fn get_direction_info(dir: &str) -> (i32, i32, &'static str) {
    match dir {
        "east" => (1, 0, "west"),
        "west" => (-1, 0, "east"),
        "north" => (0, -1, "south"),
        "south" => (0, 1, "north"),
        _ => (1, 0, "west"), // default to east
    }
}

/// Generate fill command for a rectangular area
fn fill_cmd(x1: i32, y1: i32, z1: i32, x2: i32, y2: i32, z2: i32, block: &str) -> String {
    format!("/fill {} {} {} {} {} {} {}", x1, y1, z1, x2, y2, z2, block)
}

/// Generate setblock command for single block
fn setblock_cmd(x: i32, y: i32, z: i32, block: &str) -> String {
    format!("/setblock {} {} {} {}", x, y, z, block)
}

/// Generate fill command for step blocks with direction
fn fill_step_cmd(
    x1: i32,
    y1: i32,
    z1: i32,
    x2: i32,
    y2: i32,
    z2: i32,
    block: &str,
    direction: &str,
) -> String {
    format!(
        "/fill {} {} {} {} {} {} {} [\"minecraft:cardinal_direction\"=\"{}\"]",
        x1, y1, z1, x2, y2, z2, block, direction
    )
}

/// Generate all commands for staircase with landing and turnaround
pub fn generate_staircase(cfg: &StaircaseConfig) -> Vec<String> {
    let mut commands = Vec::new();

    let (dx, dz, opposite) = get_direction_info(cfg.direction);
    let step_material = format!("{}_step", cfg.material);
    let width = cfg.width;
    // Total width = width (first flight) + width (second flight) = 2*width
    // Platform depth = width (same as flight width)
    let total_width = 2 * width; // both flights side by side

    let x = cfg.x;
    let y = cfg.y;
    let z = cfg.z;
    let landing_y = y + cfg.flight_height;

    // Entry platform (under first step)
    // Size: 2 blocks deep (in direction) x total_width wide
    if dx != 0 {
        let plat_x1 = x - dx.abs();
        let plat_x2 = x;
        commands.push(fill_cmd(
            plat_x1.min(plat_x2),
            y - 1,
            z,
            plat_x1.max(plat_x2),
            y - 1,
            z + total_width - 1,
            cfg.material,
        ));
    } else {
        let plat_z1 = z - dz.abs();
        let plat_z2 = z;
        commands.push(fill_cmd(
            x,
            y - 1,
            plat_z1.min(plat_z2),
            x + total_width - 1,
            y - 1,
            plat_z1.max(plat_z2),
            cfg.material,
        ));
    }

    // Entry step (before first stair)
    if dx != 0 {
        commands.push(fill_step_cmd(
            x, y, z, x, y, z + width - 1, &step_material, cfg.direction,
        ));
    } else {
        commands.push(fill_step_cmd(
            x, y, z, x + width - 1, y, z, &step_material, cfg.direction,
        ));
    }

    // First flight: steps going in DIRECTION
    for i in 0..cfg.flight_height {
        let step_x = x + (i + 1) * dx;
        let step_z = z + (i + 1) * dz;
        let step_y = y + i;

        if dx != 0 {
            // Moving along X axis (east/west), width along Z
            commands.push(fill_cmd(
                step_x, step_y, z, step_x, step_y, z + width - 1, cfg.material,
            ));
            commands.push(fill_step_cmd(
                step_x,
                step_y + 1,
                z,
                step_x,
                step_y + 1,
                z + width - 1,
                &step_material,
                cfg.direction,
            ));
        } else {
            // Moving along Z axis (north/south), width along X
            commands.push(fill_cmd(
                x, step_y, step_z, x + width - 1, step_y, step_z, cfg.material,
            ));
            commands.push(fill_step_cmd(
                x,
                step_y + 1,
                step_z,
                x + width - 1,
                step_y + 1,
                step_z,
                &step_material,
                cfg.direction,
            ));
        }
    }

    // Landing platform
    // Depth = width (same as flight width for turnaround space)
    if dx != 0 {
        let landing_x1 = x + (cfg.flight_height + 1) * dx;
        let landing_x2 = x + (cfg.flight_height + width) * dx;
        commands.push(fill_cmd(
            landing_x1.min(landing_x2),
            landing_y,
            z,
            landing_x1.max(landing_x2),
            landing_y,
            z + total_width - 1,
            cfg.material,
        ));
    } else {
        let landing_z1 = z + (cfg.flight_height + 1) * dz;
        let landing_z2 = z + (cfg.flight_height + width) * dz;
        commands.push(fill_cmd(
            x,
            landing_y,
            landing_z1.min(landing_z2),
            x + total_width - 1,
            landing_y,
            landing_z1.max(landing_z2),
            cfg.material,
        ));
    }

    // Extend platform under second flight start (fill the gap)
    if dx != 0 {
        let extend_x = x + cfg.flight_height * dx;
        commands.push(fill_cmd(
            extend_x,
            landing_y,
            z + width,
            extend_x,
            landing_y,
            z + total_width - 1,
            cfg.material,
        ));
    } else {
        let extend_z = z + cfg.flight_height * dz;
        commands.push(fill_cmd(
            x + width,
            landing_y,
            extend_z,
            x + total_width - 1,
            landing_y,
            extend_z,
            cfg.material,
        ));
    }

    // Second flight: steps going back (opposite direction)
    // Same width as first flight
    for i in 0..cfg.flight_height {
        let step_y = landing_y + i;

        if dx != 0 {
            let step_x = x + (cfg.flight_height - i) * dx;
            // Second flight is at z + width to z + total_width - 1
            commands.push(fill_cmd(
                step_x,
                step_y,
                z + width,
                step_x,
                step_y,
                z + total_width - 1,
                cfg.material,
            ));
            commands.push(fill_step_cmd(
                step_x,
                step_y + 1,
                z + width,
                step_x,
                step_y + 1,
                z + total_width - 1,
                &step_material,
                opposite,
            ));
        } else {
            let step_z = z + (cfg.flight_height - i) * dz;
            // Second flight is at x + width to x + total_width - 1
            commands.push(fill_cmd(
                x + width,
                step_y,
                step_z,
                x + total_width - 1,
                step_y,
                step_z,
                cfg.material,
            ));
            commands.push(fill_step_cmd(
                x + width,
                step_y + 1,
                step_z,
                x + total_width - 1,
                step_y + 1,
                step_z,
                &step_material,
                opposite,
            ));
        }
    }

    // Walls (if enabled)
    if let Some(wall_mat) = cfg.wall_material {
        commands.extend(generate_walls(cfg, wall_mat, dx, dz, landing_y, total_width));
    }

    // Lanterns (if enabled)
    if let Some(lantern) = cfg.lantern {
        if cfg.wall_material.is_some() {
            commands.extend(generate_lanterns(cfg, lantern, dx, dz, landing_y, total_width));
        }
    }

    commands
}

/// Generate wall commands
fn generate_walls(
    cfg: &StaircaseConfig,
    wall_mat: &str,
    dx: i32,
    dz: i32,
    landing_y: i32,
    total_width: i32,
) -> Vec<String> {
    let mut commands = Vec::new();
    let x = cfg.x;
    let y = cfg.y;
    let z = cfg.z;
    let width = cfg.width;
    let wall_height = 2; // wall height above step

    // First flight walls (both sides)
    for i in 0..cfg.flight_height {
        let step_y = y + i;

        if dx != 0 {
            let wall_x = x + (i + 1) * dx;
            // Left wall (z - 1)
            commands.push(fill_cmd(
                wall_x,
                step_y,
                z - 1,
                wall_x,
                step_y + wall_height,
                z - 1,
                wall_mat,
            ));
            // Middle wall between flights (z + width - 1 and z + width)
            // Only inner wall for first flight
        } else {
            let wall_z = z + (i + 1) * dz;
            // Left wall (x - 1)
            commands.push(fill_cmd(
                x - 1,
                step_y,
                wall_z,
                x - 1,
                step_y + wall_height,
                wall_z,
                wall_mat,
            ));
        }
    }

    // Second flight walls (both sides)
    for i in 0..cfg.flight_height {
        let step_y = landing_y + i;

        if dx != 0 {
            let wall_x = x + (cfg.flight_height - i) * dx;
            // Right wall (z + total_width)
            commands.push(fill_cmd(
                wall_x,
                step_y,
                z + total_width,
                wall_x,
                step_y + wall_height,
                z + total_width,
                wall_mat,
            ));
        } else {
            let wall_z = z + (cfg.flight_height - i) * dz;
            // Right wall (x + total_width)
            commands.push(fill_cmd(
                x + total_width,
                step_y,
                wall_z,
                x + total_width,
                step_y + wall_height,
                wall_z,
                wall_mat,
            ));
        }
    }

    // Landing walls (outer edges only - not blocking the platform)
    if dx != 0 {
        // End wall (behind landing platform)
        let end_x = x + (cfg.flight_height + width + 1) * dx;
        commands.push(fill_cmd(
            end_x,
            landing_y,
            z - 1,
            end_x,
            landing_y + wall_height,
            z + total_width,
            wall_mat,
        ));
        // Side walls along landing
        let landing_x1 = x + (cfg.flight_height + 1) * dx;
        let landing_x2 = x + (cfg.flight_height + width) * dx;
        // Left side (z - 1)
        commands.push(fill_cmd(
            landing_x1.min(landing_x2),
            landing_y,
            z - 1,
            landing_x1.max(landing_x2),
            landing_y + wall_height,
            z - 1,
            wall_mat,
        ));
        // Right side (z + total_width)
        commands.push(fill_cmd(
            landing_x1.min(landing_x2),
            landing_y,
            z + total_width,
            landing_x1.max(landing_x2),
            landing_y + wall_height,
            z + total_width,
            wall_mat,
        ));
    } else {
        // End wall (behind landing platform)
        let end_z = z + (cfg.flight_height + width + 1) * dz;
        commands.push(fill_cmd(
            x - 1,
            landing_y,
            end_z,
            x + total_width,
            landing_y + wall_height,
            end_z,
            wall_mat,
        ));
        // Side walls along landing
        let landing_z1 = z + (cfg.flight_height + 1) * dz;
        let landing_z2 = z + (cfg.flight_height + width) * dz;
        // Left side (x - 1)
        commands.push(fill_cmd(
            x - 1,
            landing_y,
            landing_z1.min(landing_z2),
            x - 1,
            landing_y + wall_height,
            landing_z1.max(landing_z2),
            wall_mat,
        ));
        // Right side (x + total_width)
        commands.push(fill_cmd(
            x + total_width,
            landing_y,
            landing_z1.min(landing_z2),
            x + total_width,
            landing_y + wall_height,
            landing_z1.max(landing_z2),
            wall_mat,
        ));
    }

    commands
}

/// Generate lantern commands on walls
fn generate_lanterns(
    cfg: &StaircaseConfig,
    lantern: &str,
    dx: i32,
    dz: i32,
    landing_y: i32,
    total_width: i32,
) -> Vec<String> {
    let mut commands = Vec::new();
    let x = cfg.x;
    let y = cfg.y;
    let z = cfg.z;
    let interval = cfg.lantern_interval;

    // First flight lanterns (left wall only)
    for i in (0..cfg.flight_height).step_by(interval as usize) {
        let step_y = y + i + 2; // lantern height above base

        if dx != 0 {
            let lantern_x = x + (i + 1) * dx;
            commands.push(setblock_cmd(lantern_x, step_y, z - 1, lantern));
        } else {
            let lantern_z = z + (i + 1) * dz;
            commands.push(setblock_cmd(x - 1, step_y, lantern_z, lantern));
        }
    }

    // Second flight lanterns (right wall only)
    for i in (0..cfg.flight_height).step_by(interval as usize) {
        let step_y = landing_y + i + 2;

        if dx != 0 {
            let lantern_x = x + (cfg.flight_height - i) * dx;
            commands.push(setblock_cmd(lantern_x, step_y, z + total_width, lantern));
        } else {
            let lantern_z = z + (cfg.flight_height - i) * dz;
            commands.push(setblock_cmd(x + total_width, step_y, lantern_z, lantern));
        }
    }

    commands
}
