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

#[derive(Parser)]
#[command(name = "mc-commander")]
#[command(about = "Minecraft command generator and executor")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
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
const LANTERN_INTERVAL: i32 = 3; // lantern every N steps

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
            BufReader::new(File::open("commands.txt")?)
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

    let delay_before_start = 5;
    println!("У тебя {} секунд чтобы:", delay_before_start);
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

    for (i, command) in commands.iter().enumerate() {
        thread::sleep(Duration::from_millis(500));
        println!("[{}/{}] {}", i + 1, commands.len(), command);
        clipboard.set_text(command)?;

        enigo.key(Key::Unicode('t'), Click)?;
        thread::sleep(Duration::from_millis(600));

        enigo.key(Key::Meta, Press)?;
        thread::sleep(Duration::from_millis(100));
        enigo.key(Key::Unicode('v'), Click)?;
        thread::sleep(Duration::from_millis(100));
        enigo.key(Key::Meta, Release)?;
        thread::sleep(Duration::from_millis(200));
        enigo.key(Key::Return, Click)?;
        thread::sleep(Duration::from_millis(200));
    }

    println!();
    println!("Готово! Выполнено команд: {}", commands.len());
    Ok(())
}
