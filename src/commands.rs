// Command parsing, offset application, and bounding box calculation

use std::fs::File;
use std::io::{BufRead, BufReader};

use crate::config::Offset;

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
    match parts {
        [x, y, z] => {
            let x = x.parse().ok()?;
            let y = y.parse().ok()?;
            let z = z.parse().ok()?;
            Some((x, y, z))
        }
        _ => None,
    }
}

pub fn find_bounding_box(commands: &[String]) -> Option<BoundingBox> {
    let mut bbox_builder = BoundingBoxBuilder::new();

    for cmd in commands {
        if let Some(coords) = extract_coordinates(cmd) {
            for coord in coords {
                bbox_builder.update(coord);
            }
        }
    }

    bbox_builder.build()
}

struct BoundingBoxBuilder {
    min: (i32, i32, i32),
    max: (i32, i32, i32),
    found: bool,
}

impl BoundingBoxBuilder {
    fn new() -> Self {
        Self {
            min: (i32::MAX, i32::MAX, i32::MAX),
            max: (i32::MIN, i32::MIN, i32::MIN),
            found: false,
        }
    }

    fn update(&mut self, (x, y, z): (i32, i32, i32)) {
        self.min = (self.min.0.min(x), self.min.1.min(y), self.min.2.min(z));
        self.max = (self.max.0.max(x), self.max.1.max(y), self.max.2.max(z));
        self.found = true;
    }

    fn build(self) -> Option<BoundingBox> {
        if self.found {
            Some(BoundingBox {
                min: self.min,
                max: self.max,
            })
        } else {
            None
        }
    }
}

fn extract_coordinates(cmd: &str) -> Option<Vec<(i32, i32, i32)>> {
    let parts: Vec<&str> = cmd.split_whitespace().collect();
    if parts.is_empty() {
        return None;
    }

    let cmd_type = parts[0].trim_start_matches('/');

    match (cmd_type, parts.len()) {
        ("setblock", len) if len >= 4 => {
            parse_coords(&parts[1..4]).map(|c| vec![c])
        }
        ("fill", len) if len >= 7 => {
            let start = parse_coords(&parts[1..4])?;
            let end = parse_coords(&parts[4..7])?;
            Some(vec![start, end])
        }
        _ => None,
    }
}
