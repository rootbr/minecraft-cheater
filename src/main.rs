mod feedback;
mod staircase;

use arboard::Clipboard;
use feedback::{CommandResult, FeedbackDetector};
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

/// Execute a single Minecraft command via keyboard emulation with retry logic
fn execute_command(
    command: &str,
    offset_x: i32,
    offset_y: i32,
    offset_z: i32,
    enigo: &mut Enigo,
    clipboard: &mut Clipboard,
    mut detector: Option<&mut FeedbackDetector>,
    no_feedback: bool,
) -> Result<String, Box<dyn std::error::Error>> {
    let command_with_offset = apply_offset(command, offset_x, offset_y, offset_z);
    const MAX_RETRIES: u32 = 3;

    for attempt in 1..=MAX_RETRIES {
        match execute_command_once(
            &command_with_offset,
            enigo,
            clipboard,
            detector.as_deref_mut(),
            no_feedback,
        ) {
            Ok(_) => return Ok(command_with_offset),
            Err(e) => {
                if attempt < MAX_RETRIES {
                    eprintln!("⚠ Попытка {}/{} не удалась: {}. Нажимаю ESC и повторяю...", attempt, MAX_RETRIES, e);
                    // Press ESC multiple times to ensure chat closes
                    eprintln!("  → Нажимаю ESC...");
                    enigo.key(Key::Escape, Click)?;
                    thread::sleep(Duration::from_millis(100));
                    enigo.key(Key::Escape, Click)?;
                    thread::sleep(Duration::from_millis(100));
                    eprintln!("  → ESC нажат, жду 500ms...");
                    thread::sleep(Duration::from_millis(500));
                    eprintln!("  → Повторяю команду (попытка {})", attempt + 1);
                } else {
                    eprintln!("✗ Команда не выполнена после {} попыток: {}", MAX_RETRIES, e);
                    // Press ESC multiple times to ensure chat is closed
                    eprintln!("  → Нажимаю ESC для очистки...");
                    enigo.key(Key::Escape, Click)?;
                    thread::sleep(Duration::from_millis(100));
                    enigo.key(Key::Escape, Click)?;
                    thread::sleep(Duration::from_millis(200));
                    return Err(e);
                }
            }
        }
    }

    Ok(command_with_offset)
}

/// Execute command once (internal helper for retry logic)
fn execute_command_once(
    command_with_offset: &str,
    enigo: &mut Enigo,
    clipboard: &mut Clipboard,
    mut detector: Option<&mut FeedbackDetector>,
    no_feedback: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    eprintln!("  [1] Копирую команду в буфер обмена...");
    clipboard.set_text(command_with_offset)?;
    thread::sleep(Duration::from_millis(75));
    // Open chat
    eprintln!("  [2] Нажимаю T для открытия чата...");
    enigo.key(Key::Unicode('t'), Click)?;

    // Wait for chat to open
    eprintln!("  [3] Жду открытия чата...");
    if !no_feedback && detector.is_some() {
        match detector.as_mut().unwrap().wait_for_chat_open() {
            Ok(_) => eprintln!("  [3] ✓ Чат открылся"),
            Err(e) => {
                eprintln!("  [3] ✗ Таймаут открытия чата: {}", e);
                return Err(Box::new(e));
            }
        }
    } else {
        // Fallback to fixed delay
        thread::sleep(Duration::from_millis(700));
        eprintln!("  [3] Использую фиксированную задержку (no feedback)");
    }

    // Paste command
    eprintln!("  [4] Вставляю команду (Cmd+V)...");
    thread::sleep(Duration::from_millis(100));
    enigo.key(Key::Meta, Press)?;
    thread::sleep(Duration::from_millis(100));
    enigo.key(Key::Unicode('v'), Click)?;
    thread::sleep(Duration::from_millis(100));
    enigo.key(Key::Meta, Release)?;

    // Execute command
    eprintln!("  [5] Нажимаю Enter...");
    thread::sleep(Duration::from_millis(75));
    enigo.key(Key::Return, Click)?;

    // Check command result and wait for chat close
    eprintln!("  [6] Жду закрытия чата...");
    if !no_feedback && detector.is_some() {
        let det = detector.as_mut().unwrap();

        match det.read_command_response() {
            Ok(CommandResult::Success) => {}
            Ok(CommandResult::Error(err)) => {
                eprintln!("  [6] ⚠ Command execution error: {}", err);
            }
            Ok(CommandResult::Unknown) => {
                // No response detected, assume success
            }
            Err(e) => {
                eprintln!("  [6] ⚠ Failed to read command response: {}", e);
            }
        }

        // Wait for chat to close
        match det.wait_for_chat_close() {
            Ok(_) => eprintln!("  [6] ✓ Чат закрылся"),
            Err(e) => {
                eprintln!("  [6] ✗ Таймаут закрытия чата: {}", e);
                return Err(Box::new(e));
            }
        }
    } else {
        // Fallback to fixed delay
        thread::sleep(Duration::from_millis(250));
        eprintln!("  [6] Использую фиксированную задержку (no feedback)");
    }

    eprintln!("  [7] ✓ Команда выполнена успешно");
    Ok(())
}

/// Apply coordinate offset to a command
fn apply_offset(command: &str, offset_x: i32, offset_y: i32, offset_z: i32) -> String {
    // If all offsets are 0, return original command
    if offset_x == 0 && offset_y == 0 && offset_z == 0 {
        return command.to_string();
    }

    let parts: Vec<&str> = command.split_whitespace().collect();
    if parts.is_empty() {
        return command.to_string();
    }

    let cmd_type = parts[0].trim_start_matches('/');

    match cmd_type {
        "setblock" if parts.len() >= 5 => {
            if let (Ok(x), Ok(y), Ok(z)) = (
                parts[1].parse::<i32>(),
                parts[2].parse::<i32>(),
                parts[3].parse::<i32>(),
            ) {
                let new_x = x + offset_x;
                let new_y = y + offset_y;
                let new_z = z + offset_z;
                let rest = parts[4..].join(" ");
                format!("/setblock {} {} {} {}", new_x, new_y, new_z, rest)
            } else {
                command.to_string()
            }
        }
        "fill" if parts.len() >= 8 => {
            if let (Ok(x1), Ok(y1), Ok(z1), Ok(x2), Ok(y2), Ok(z2)) = (
                parts[1].parse::<i32>(),
                parts[2].parse::<i32>(),
                parts[3].parse::<i32>(),
                parts[4].parse::<i32>(),
                parts[5].parse::<i32>(),
                parts[6].parse::<i32>(),
            ) {
                let new_x1 = x1 + offset_x;
                let new_y1 = y1 + offset_y;
                let new_z1 = z1 + offset_z;
                let new_x2 = x2 + offset_x;
                let new_y2 = y2 + offset_y;
                let new_z2 = z2 + offset_z;
                let rest = parts[7..].join(" ");
                format!(
                    "/fill {} {} {} {} {} {} {}",
                    new_x1, new_y1, new_z1, new_x2, new_y2, new_z2, rest
                )
            } else {
                command.to_string()
            }
        }
        _ => command.to_string(),
    }
}

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

    /// X coordinate offset to apply to all commands
    #[arg(long, default_value_t = 0)]
    offset_x: i32,

    /// Y coordinate offset to apply to all commands
    #[arg(long, default_value_t = 0)]
    offset_y: i32,

    /// Z coordinate offset to apply to all commands
    #[arg(long, default_value_t = 0)]
    offset_z: i32,

    /// Command file to execute (default: build_commands_optimized.txt)
    #[arg(short, long, default_value = "build_commands_optimized.txt")]
    file: String,

    /// Filter commands by material (only execute commands containing this string)
    #[arg(short = 'm', long)]
    material: Option<String>,

    /// Disable feedback detection and use fixed delays (fallback mode)
    #[arg(long, default_value_t = false)]
    no_feedback: bool,

    /// Maximum retry attempts for chat open detection (default: 50 = ~1000ms)
    #[arg(long, default_value_t = 50)]
    max_retries: u32,

    /// Poll interval in milliseconds for state detection
    #[arg(long, default_value_t = 10)]
    poll_interval: u64,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate and execute staircase with landing
    Staircase,

    /// Test ESC key press (opens chat and closes it 3 times)
    TestEsc,
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

    // Handle test-esc command separately
    if matches!(cli.command, Some(Commands::TestEsc)) {
        println!("=== Тест нажатия ESC ===");
        println!("У тебя 5 секунд чтобы переключиться на Minecraft...");
        for i in (1..=5).rev() {
            println!("  {}...", i);
            thread::sleep(Duration::from_secs(1));
        }

        let mut enigo = Enigo::new(&Settings::default())?;

        for i in 1..=3 {
            println!("\nТест {}/3:", i);
            println!("  → Нажимаю T (открытие чата)");
            enigo.key(Key::Unicode('t'), Click)?;
            thread::sleep(Duration::from_millis(500));

            println!("  → Нажимаю ESC (закрытие чата)");
            enigo.key(Key::Escape, Click)?;
            thread::sleep(Duration::from_millis(500));

            println!("  → Нажимаю ESC еще раз (для надежности)");
            enigo.key(Key::Escape, Click)?;
            thread::sleep(Duration::from_millis(1000));
        }

        println!("\n✓ Тест завершен! Если чат открывался и закрывался, ESC работает корректно.");
        return Ok(());
    }

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
        Some(Commands::TestEsc) => {
            unreachable!("TestEsc handled above")
        }
        None => {
            // Default: read from specified file
            println!("Читаю команды из файла: {}", cli.file);
            BufReader::new(File::open(&cli.file)?)
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

    // Apply skip first
    let skip_count = cli.skip;
    let mut commands_after_skip: Vec<String> = if skip_count > 0 {
        if skip_count >= commands.len() {
            println!("Skip count ({}) >= total commands ({}). Nothing to execute.", skip_count, commands.len());
            return Ok(());
        }
        println!("Пропускаю первые {} команд...", skip_count);
        commands.into_iter().skip(skip_count).collect()
    } else {
        commands
    };

    // Apply material filter after skip
    let commands_to_execute: Vec<String> = if let Some(ref material_filter) = cli.material {
        let before_filter = commands_after_skip.len();
        commands_after_skip.retain(|cmd| cmd.contains(material_filter));
        println!("Фильтр по материалу '{}': {} команд из {} прошли фильтр",
                 material_filter, commands_after_skip.len(), before_filter);
        commands_after_skip
    } else {
        commands_after_skip
    };

    let total_commands = commands_to_execute.len();
    println!("Команд к выполнению: {}", total_commands);

    // Show offset info if any offset is non-zero
    if cli.offset_x != 0 || cli.offset_y != 0 || cli.offset_z != 0 {
        println!("Применяется offset: X={}, Y={}, Z={}", cli.offset_x, cli.offset_y, cli.offset_z);
    }

    // Initialize feedback detector BEFORE countdown (unless disabled)
    let mut detector = if !cli.no_feedback {
        let retry_config = feedback::RetryConfig {
            max_attempts_open: cli.max_retries,     // For chat open
            max_attempts_close: 20,                 // Fixed at 20 for chat close (~300ms)
            initial_delay_ms: 5,
            poll_interval_ms: cli.poll_interval,
        };

        match FeedbackDetector::with_config(retry_config) {
            Ok(det) => {
                if det.is_enabled() {
                    println!("✓ Feedback detection enabled (smart timing)");
                } else {
                    println!("⚠ Feedback detection unavailable, using fixed delays");
                }
                Some(det)
            }
            Err(e) => {
                eprintln!("⚠ Failed to initialize feedback detector: {}", e);
                eprintln!("  Falling back to fixed delays");
                None
            }
        }
    } else {
        println!("ℹ Feedback detection disabled (--no-feedback), using fixed delays");
        None
    };

    let delay_before_start = 5;
    println!("\nУ тебя {} секунд чтобы:", delay_before_start);
    println!("   1. Переключиться на Parallels Desktop");
    println!("   2. Кликнуть в окно Minecraft");
    println!("   3. ВАЖНО: Расположи окно Minecraft в НИЖНИЙ ЛЕВЫЙ угол экрана!");
    println!("   4. Убедиться что чат закрыт (нажми Esc)");
    println!();

    // Show live preview during countdown
    if let Some(ref mut det) = detector {
        if det.is_enabled() {
            let _ = det.show_live_preview(delay_before_start as u32);
        } else {
            // No feedback - just countdown
            for i in (1..=delay_before_start).rev() {
                println!("Начинаю через {}...", i);
                thread::sleep(Duration::from_secs(1));
            }
        }
    } else {
        // No detector - just countdown
        for i in (1..=delay_before_start).rev() {
            println!("Начинаю через {}...", i);
            thread::sleep(Duration::from_secs(1));
        }
    }

    let mut enigo = Enigo::new(&Settings::default())?;
    let mut clipboard = Clipboard::new()?;

    // Execute clear commands first (only if building full structure: no skip, no filter)
    let should_clear = skip_count == 0 && cli.material.is_none();
    if !clear_commands.is_empty() && should_clear {
        println!("\n=== Очистка области ===");
        for (i, command) in clear_commands.iter().enumerate() {
            let command_with_offset = execute_command(
                command,
                cli.offset_x,
                cli.offset_y,
                cli.offset_z,
                &mut enigo,
                &mut clipboard,
                detector.as_mut(),
                cli.no_feedback,
            )?;
            println!("[clear {}/{}] {}", i + 1, clear_commands.len(), command_with_offset);
        }
        println!("Очистка завершена!\n");
    } else if !clear_commands.is_empty() {
        if skip_count > 0 {
            println!("\nℹ Пропускаю очистку области (используется --skip)\n");
        } else if cli.material.is_some() {
            println!("\nℹ Пропускаю очистку области (используется --material фильтр)\n");
        }
    }

    println!("=== Строительство ===");
    for (i, command) in commands_to_execute.iter().enumerate() {
        let actual_index = skip_count + i + 1;
        let command_with_offset = execute_command(
            command,
            cli.offset_x,
            cli.offset_y,
            cli.offset_z,
            &mut enigo,
            &mut clipboard,
            detector.as_mut(),
            cli.no_feedback,
        )?;
        println!("[{}/{}] {}", actual_index, skip_count + total_commands, command_with_offset);
    }

    println!();
    println!("Готово! Выполнено команд: {} (с {} по {})",
             total_commands, skip_count + 1, skip_count + total_commands);
    Ok(())
}
