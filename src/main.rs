mod staircase;

use arboard::Clipboard;
use clap::{Parser, Subcommand};
use enigo::{
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Settings,
};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::thread;
use std::time::Duration;

/// Chunk size for clearing (32x32x32 = 32768 blocks, Bedrock limit)
const CHUNK_SIZE: i32 = 32;

/// Parse coordinates from a command (setblock or fill)
fn parse_coordinates(cmd: &str) -> Option<Vec<(i32, i32, i32)>> {
    let parts: Vec<&str> = cmd.split_whitespace().collect();
    if parts.is_empty() {
        return None;
    }

    let cmd_type = parts[0].trim_start_matches('/');

    match cmd_type {
        "setblock" if parts.len() >= 4 => {
            let x = parts[1].parse().ok()?;
            let y = parts[2].parse().ok()?;
            let z = parts[3].parse().ok()?;
            Some(vec![(x, y, z)])
        }
        "fill" if parts.len() >= 7 => {
            let x1 = parts[1].parse().ok()?;
            let y1 = parts[2].parse().ok()?;
            let z1 = parts[3].parse().ok()?;
            let x2 = parts[4].parse().ok()?;
            let y2 = parts[5].parse().ok()?;
            let z2 = parts[6].parse().ok()?;
            Some(vec![(x1, y1, z1), (x2, y2, z2)])
        }
        _ => None,
    }
}

/// Find bounding box of all commands
fn find_bounding_box(commands: &[String]) -> Option<((i32, i32, i32), (i32, i32, i32))> {
    let mut min_x = i32::MAX;
    let mut min_y = i32::MAX;
    let mut min_z = i32::MAX;
    let mut max_x = i32::MIN;
    let mut max_y = i32::MIN;
    let mut max_z = i32::MIN;
    let mut found = false;

    for cmd in commands {
        if let Some(coords) = parse_coordinates(cmd) {
            for (x, y, z) in coords {
                min_x = min_x.min(x);
                min_y = min_y.min(y);
                min_z = min_z.min(z);
                max_x = max_x.max(x);
                max_y = max_y.max(y);
                max_z = max_z.max(z);
                found = true;
            }
        }
    }

    if found {
        Some(((min_x, min_y, min_z), (max_x, max_y, max_z)))
    } else {
        None
    }
}

/// Generate clear commands for a bounding box, respecting fill limit (32x32x32 chunks)
fn generate_clear_commands(min: (i32, i32, i32), max: (i32, i32, i32)) -> Vec<String> {
    let mut commands = Vec::new();
    let (min_x, min_y, min_z) = min;
    let (max_x, max_y, max_z) = max;

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

#[derive(Parser)]
#[command(name = "mc-commander")]
#[command(about = "Minecraft command generator and executor")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    /// Skip first N commands (useful if execution was interrupted)
    #[arg(short, long, default_value_t = 0)]
    skip: usize,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate and execute staircase with landing
    Staircase,
}

// Configuration constants (hardcoded)
const START_X: i32 = 94;
const START_Y: i32 = 131; // 105 118
const START_Z: i32 = 86;
const DIRECTION: &str = "south"; // east, west, north, south
const MATERIAL: &str = "spark:light_blue_decorative_tile";
const FLIGHT_HEIGHT: i32 = 6; // steps per flight
const WIDTH: i32 = 2; // width of flight
const WALL_MATERIAL: Option<&str> = Some("spark:brown_decorative_tile"); // None = no walls
const LANTERN: Option<&str> = Some("sea_lantern"); // None = no lanterns
const LANTERN_INTERVAL: i32 = 2; // lantern every N steps

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    let commands: Vec<String> = match cli.command {
        Some(Commands::Staircase) => {
            println!("Generating staircase commands...");
            let cfg = staircase::StaircaseConfig {
                direction: DIRECTION,
                material: MATERIAL,
                x: START_X,
                y: START_Y,
                z: START_Z,
                flight_height: FLIGHT_HEIGHT,
                width: WIDTH,
                wall_material: WALL_MATERIAL,
                lantern: LANTERN,
                lantern_interval: LANTERN_INTERVAL,
            };
            staircase::generate_staircase(&cfg)
        }
        None => {
            // Default: read from commands.txt
            BufReader::new(File::open("asian_pond_garden.txt")?)
                .lines()
                .filter_map(|line| line.ok())
                .filter(|line| {
                    let trimmed = line.trim();
                    !trimmed.is_empty()
                        && !trimmed.starts_with('#')
                        && !trimmed.starts_with('=')
                })
                .map(|line| line.trim().to_string())
                .collect()
        }
    };

    if commands.is_empty() {
        println!("No commands to execute.");
        return Ok(());
    }

    // Find bounding box and generate clear commands
    let clear_commands = if let Some((min, max)) = find_bounding_box(&commands) {
        let size_x = max.0 - min.0 + 1;
        let size_y = max.1 - min.1 + 1;
        let size_z = max.2 - min.2 + 1;
        let total_blocks = size_x * size_y * size_z;

        println!("Bounding box: ({}, {}, {}) to ({}, {}, {})",
                 min.0, min.1, min.2, max.0, max.1, max.2);
        println!("Size: {}x{}x{} = {} blocks", size_x, size_y, size_z, total_blocks);

        let clears = generate_clear_commands(min, max);
        println!("Clear commands: {} (32x32x32 chunks)", clears.len());
        clears
    } else {
        println!("Warning: Could not determine bounding box, skipping clear");
        Vec::new()
    };

    // Apply skip
    let skip_count = cli.skip;
    let commands_to_execute: Vec<String> = if skip_count > 0 {
        if skip_count >= commands.len() {
            println!("Skip count ({}) >= total commands ({}). Nothing to execute.", skip_count, commands.len());
            return Ok(());
        }
        println!("Пропускаю первые {} команд...", skip_count);
        commands.into_iter().skip(skip_count).collect()
    } else {
        commands
    };

    let total_commands = commands_to_execute.len();
    println!("Команд к выполнению: {} (начиная с #{})", total_commands, skip_count + 1);

    let delay_before_start = 5;
    println!("\nУ тебя {} секунд чтобы:", delay_before_start);
    println!("   1. Переключиться на Parallels Desktop");
    println!("   2. Кликнуть в окно Minecraft");
    println!("   3. Убедиться что чат закрыт (нажми Esc)");
    println!();
    for i in (1..=delay_before_start).rev() {
        println!("Начинаю через {}...", i);
        thread::sleep(Duration::from_secs(1));
    }

    let mut enigo = Enigo::new(&Settings::default())?;
    let mut clipboard = Clipboard::new()?;

    // Execute clear commands first
    if !clear_commands.is_empty() {
        println!("\n=== Очистка области ===");
        for (i, command) in clear_commands.iter().enumerate() {
            println!("[clear {}/{}] {}", i + 1, clear_commands.len(), command);
            clipboard.set_text(command)?;

            enigo.key(Key::Unicode('t'), Click)?;
            thread::sleep(Duration::from_millis(700));

            enigo.key(Key::Meta, Press)?;
            thread::sleep(Duration::from_millis(100));
            enigo.key(Key::Unicode('v'), Click)?;
            thread::sleep(Duration::from_millis(100));
            enigo.key(Key::Meta, Release)?;
            thread::sleep(Duration::from_millis(50));
            enigo.key(Key::Return, Click)?;
            thread::sleep(Duration::from_millis(250));
            // enigo.key(Key::Escape, Click)?;
            // thread::sleep(Duration::from_millis(100));
        }
        println!("Очистка завершена!\n");
    }

    println!("=== Строительство ===");
    for (i, command) in commands_to_execute.iter().enumerate() {
        let actual_index = skip_count + i + 1;
        println!("[{}/{}] {}", actual_index, skip_count + total_commands, command);
        clipboard.set_text(command)?;

        enigo.key(Key::Unicode('t'), Click)?;
        thread::sleep(Duration::from_millis(700));

        enigo.key(Key::Meta, Press)?;
        thread::sleep(Duration::from_millis(100));
        enigo.key(Key::Unicode('v'), Click)?;
        thread::sleep(Duration::from_millis(100));
        enigo.key(Key::Meta, Release)?;
        thread::sleep(Duration::from_millis(50));
        enigo.key(Key::Return, Click)?;
        thread::sleep(Duration::from_millis(250));
        // enigo.key(Key::Escape, Click)?;
        // thread::sleep(Duration::from_millis(100));
    }

    println!();
    println!("Готово! Выполнено команд: {} (с {} по {})",
             total_commands, skip_count + 1, skip_count + total_commands);
    Ok(())
}
