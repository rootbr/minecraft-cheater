// Staircase with landing and turnaround generator

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
pub fn generate_staircase(
    direction: &str,
    material: &str,
    x: i32,
    y: i32,
    z: i32,
    flight_height: i32,
) -> Vec<String> {
    let mut commands = Vec::new();

    let (dx, dz, opposite) = get_direction_info(direction);
    let step_material = format!("{}_step", material);

    // Entry platform (under first step, same as landing platform)
    if dx != 0 {
        // For east/west: platform at x-1 to x, z to z+3
        let plat_x1 = x - dx.abs();
        let plat_x2 = x;
        commands.push(fill_cmd(
            plat_x1.min(plat_x2),
            y - 1,
            z,
            plat_x1.max(plat_x2),
            y - 1,
            z + 3,
            material,
        ));
    } else {
        // For north/south: platform at x to x+3, z-1 to z
        let plat_z1 = z - dz.abs();
        let plat_z2 = z;
        commands.push(fill_cmd(
            x,
            y - 1,
            plat_z1.min(plat_z2),
            x + 3,
            y - 1,
            plat_z1.max(plat_z2),
            material,
        ));
    }

    // Entry step (before first stair)
    if dx != 0 {
        commands.push(fill_step_cmd(x, y, z, x, y, z + 1, &step_material, direction));
    } else {
        commands.push(fill_step_cmd(x, y, z, x + 1, y, z, &step_material, direction));
    }

    // First flight: steps going in DIRECTION
    // Width is 2 blocks (z to z+1 for east/west, x to x+1 for north/south)
    for i in 0..flight_height {
        let step_x = x + (i + 1) * dx;
        let step_z = z + (i + 1) * dz;
        let step_y = y + i;

        if dx != 0 {
            // Moving along X axis (east/west), width along Z
            // Base block
            commands.push(fill_cmd(step_x, step_y, z, step_x, step_y, z + 1, material));
            // Step block on top
            commands.push(fill_step_cmd(
                step_x,
                step_y + 1,
                z,
                step_x,
                step_y + 1,
                z + 1,
                &step_material,
                direction,
            ));
        } else {
            // Moving along Z axis (north/south), width along X
            // Base block
            commands.push(fill_cmd(x, step_y, step_z, x + 1, step_y, step_z, material));
            // Step block on top
            commands.push(fill_step_cmd(
                x,
                step_y + 1,
                step_z,
                x + 1,
                step_y + 1,
                step_z,
                &step_material,
                direction,
            ));
        }
    }

    // Landing platform (2x4 blocks)
    let landing_y = y + flight_height;
    if dx != 0 {
        // For east/west: platform extends further in X and wider in Z
        let landing_x = x + (flight_height + 1) * dx;
        let landing_x2 = x + (flight_height + 2) * dx;
        commands.push(fill_cmd(
            landing_x.min(landing_x2),
            landing_y,
            z,
            landing_x.max(landing_x2),
            landing_y,
            z + 3,
            material,
        ));
    } else {
        // For north/south: platform extends further in Z and wider in X
        let landing_z = z + (flight_height + 1) * dz;
        let landing_z2 = z + (flight_height + 2) * dz;
        commands.push(fill_cmd(
            x,
            landing_y,
            landing_z.min(landing_z2),
            x + 3,
            landing_y,
            landing_z.max(landing_z2),
            material,
        ));
    }

    // Extend platform under second flight start (fill the gap)
    if dx != 0 {
        let extend_x = x + flight_height * dx;
        commands.push(fill_cmd(extend_x, landing_y, z + 2, extend_x, landing_y, z + 3, material));
    } else {
        let extend_z = z + flight_height * dz;
        commands.push(fill_cmd(x + 2, landing_y, extend_z, x + 3, landing_y, extend_z, material));
    }

    // Second flight: steps going back (opposite direction)
    for i in 0..flight_height {
        let step_y = landing_y + i;

        if dx != 0 {
            // Was moving along X, now going back
            let step_x = x + (flight_height - i) * dx;
            // Base block (at z+2 to z+3)
            commands.push(fill_cmd(step_x, step_y, z + 2, step_x, step_y, z + 3, material));
            // Step block on top
            commands.push(fill_step_cmd(
                step_x,
                step_y + 1,
                z + 2,
                step_x,
                step_y + 1,
                z + 3,
                &step_material,
                opposite,
            ));
        } else {
            // Was moving along Z, now going back
            let step_z = z + (flight_height - i) * dz;
            // Base block (at x+2 to x+3)
            commands.push(fill_cmd(x + 2, step_y, step_z, x + 3, step_y, step_z, material));
            // Step block on top
            commands.push(fill_step_cmd(
                x + 2,
                step_y + 1,
                step_z,
                x + 3,
                step_y + 1,
                step_z,
                &step_material,
                opposite,
            ));
        }
    }

    commands
}
