// Command parsing, offset application, and bounding box calculation

use std::fs::File;
use std::io::{BufRead, BufReader};

use crate::config::{Offset, CHUNK_SIZE};

#[derive(Clone, Copy)]
pub struct BoundingBox {
    pub min: (i32, i32, i32),
    pub max: (i32, i32, i32),
}

impl BoundingBox {
    pub fn size(&self) -> (i32, i32, i32) {
        (
            self.max.0 - self.min.0 + 1,
            self.max.1 - self.min.1 + 1,
            self.max.2 - self.min.2 + 1,
        )
    }

    pub fn total_blocks(&self) -> i32 {
        let (x, y, z) = self.size();
        x * y * z
    }
}

pub fn load_from_file(path: &str) -> std::io::Result<Vec<String>> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);

    let commands = reader
        .lines()
        .filter_map(|line| line.ok())
        .map(|line| line.trim().to_string())
        .filter(|line| is_valid_command(line))
        .collect();

    Ok(commands)
}

fn is_valid_command(line: &str) -> bool {
    !line.is_empty() && !line.starts_with('#') && !line.starts_with('=')
}

pub fn apply_offset(command: &str, offset: Offset) -> String {
    if offset.is_zero() {
        return command.to_string();
    }

    let parts: Vec<&str> = command.split_whitespace().collect();
    if parts.is_empty() {
        return command.to_string();
    }

    let cmd_type = parts[0].trim_start_matches('/');

    match cmd_type {
        "setblock" => apply_setblock_offset(&parts, offset),
        "fill" => apply_fill_offset(&parts, offset),
        _ => command.to_string(),
    }
}

fn apply_setblock_offset(parts: &[&str], offset: Offset) -> String {
    if parts.len() < 5 {
        return parts.join(" ");
    }

    let coords = parse_coords(&parts[1..4]);
    if coords.is_none() {
        return parts.join(" ");
    }

    let (x, y, z) = coords.unwrap();
    let rest = parts[4..].join(" ");

    format!(
        "/setblock {} {} {} {}",
        x + offset.x,
        y + offset.y,
        z + offset.z,
        rest
    )
}

fn apply_fill_offset(parts: &[&str], offset: Offset) -> String {
    if parts.len() < 8 {
        return parts.join(" ");
    }

    let start = parse_coords(&parts[1..4]);
    let end = parse_coords(&parts[4..7]);

    if start.is_none() || end.is_none() {
        return parts.join(" ");
    }

    let (x1, y1, z1) = start.unwrap();
    let (x2, y2, z2) = end.unwrap();
    let rest = parts[7..].join(" ");

    format!(
        "/fill {} {} {} {} {} {} {}",
        x1 + offset.x,
        y1 + offset.y,
        z1 + offset.z,
        x2 + offset.x,
        y2 + offset.y,
        z2 + offset.z,
        rest
    )
}

fn parse_coords(parts: &[&str]) -> Option<(i32, i32, i32)> {
    if parts.len() < 3 {
        return None;
    }

    let x = parts[0].parse().ok()?;
    let y = parts[1].parse().ok()?;
    let z = parts[2].parse().ok()?;

    Some((x, y, z))
}

pub fn find_bounding_box(commands: &[String]) -> Option<BoundingBox> {
    let mut min = (i32::MAX, i32::MAX, i32::MAX);
    let mut max = (i32::MIN, i32::MIN, i32::MIN);
    let mut found = false;

    for cmd in commands {
        if let Some(coords) = extract_coordinates(cmd) {
            for (x, y, z) in coords {
                min = (min.0.min(x), min.1.min(y), min.2.min(z));
                max = (max.0.max(x), max.1.max(y), max.2.max(z));
                found = true;
            }
        }
    }

    if found {
        Some(BoundingBox { min, max })
    } else {
        None
    }
}

fn extract_coordinates(cmd: &str) -> Option<Vec<(i32, i32, i32)>> {
    let parts: Vec<&str> = cmd.split_whitespace().collect();
    if parts.is_empty() {
        return None;
    }

    let cmd_type = parts[0].trim_start_matches('/');

    match cmd_type {
        "setblock" if parts.len() >= 4 => {
            parse_coords(&parts[1..4]).map(|c| vec![c])
        }
        "fill" if parts.len() >= 7 => {
            let start = parse_coords(&parts[1..4])?;
            let end = parse_coords(&parts[4..7])?;
            Some(vec![start, end])
        }
        _ => None,
    }
}

pub fn generate_clear_commands(bbox: BoundingBox) -> Vec<String> {
    let mut commands = Vec::new();
    let (min_x, min_y, min_z) = bbox.min;
    let (max_x, max_y, max_z) = bbox.max;

    let mut x = min_x;
    while x <= max_x {
        let x_end = (x + CHUNK_SIZE - 1).min(max_x);

        let mut y = min_y;
        while y <= max_y {
            let y_end = (y + CHUNK_SIZE - 1).min(max_y);

            let mut z = min_z;
            while z <= max_z {
                let z_end = (z + CHUNK_SIZE - 1).min(max_z);

                commands.push(format!(
                    "/fill {} {} {} {} {} {} air",
                    x, y, z, x_end, y_end, z_end
                ));

                z = z_end + 1;
            }
            y = y_end + 1;
        }
        x = x_end + 1;
    }

    commands
}

pub fn filter_by_material(commands: Vec<String>, material: &str) -> Vec<String> {
    commands
        .into_iter()
        .filter(|cmd| cmd.contains(material))
        .collect()
}
