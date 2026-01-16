mod commands;
mod config;
mod executor;
mod feedback;
mod staircase;

use clap::{Parser, Subcommand};

use commands::{apply_offset, filter_by_material, find_bounding_box, generate_clear_commands, load_from_file};
use config::{Offset, COUNTDOWN_SECONDS};
use executor::CommandExecutor;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Parser)]
#[command(name = "mc-commander")]
#[command(about = "Minecraft command generator and executor")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    #[arg(short, long, default_value_t = 0)]
    skip: usize,

    #[arg(long, default_value_t = 0)]
    offset_x: i32,

    #[arg(long, default_value_t = 0)]
    offset_y: i32,

    #[arg(long, default_value_t = 0)]
    offset_z: i32,

    #[arg(short, long, default_value = "build_commands_optimized.txt")]
    file: String,

    #[arg(short = 'm', long)]
    material: Option<String>,
}

#[derive(Subcommand)]
enum Commands {
    Staircase,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Some(Commands::Staircase) => run_staircase(&cli),
        None => run_from_file(&cli),
    }
}

fn run_staircase(cli: &Cli) -> Result<()> {
    println!("Generating staircase commands...");
    let commands = staircase::generate_commands();
    execute_commands(cli, commands)
}

fn run_from_file(cli: &Cli) -> Result<()> {
    println!("Читаю команды из файла: {}", cli.file);
    let commands = load_from_file(&cli.file)?;
    execute_commands(cli, commands)
}

fn execute_commands(cli: &Cli, commands: Vec<String>) -> Result<()> {
    if commands.is_empty() {
        println!("No commands to execute.");
        return Ok(());
    }

    let offset = Offset::new(cli.offset_x, cli.offset_y, cli.offset_z);
    let bbox = find_bounding_box(&commands);
    let clear_commands = prepare_clear_commands(&bbox);

    let commands = apply_skip_and_filter(commands, cli);
    if commands.is_empty() {
        return Ok(());
    }

    print_execution_info(&commands, &offset);

    let mut executor = CommandExecutor::new()?;
    print_countdown_instructions();
    executor.show_countdown(COUNTDOWN_SECONDS);

    let should_clear = cli.skip == 0 && cli.material.is_none();
    execute_clear_phase(&mut executor, &clear_commands, offset, should_clear, cli)?;
    execute_build_phase(&mut executor, &commands, offset, cli.skip)?;

    print_completion(commands.len(), cli.skip);
    Ok(())
}

fn prepare_clear_commands(bbox: &Option<commands::BoundingBox>) -> Vec<String> {
    match bbox {
        Some(b) => {
            let size = b.size();
            println!(
                "Bounding box: ({}, {}, {}) to ({}, {}, {})",
                b.min.0, b.min.1, b.min.2, b.max.0, b.max.1, b.max.2
            );
            println!(
                "Size: {}x{}x{} = {} blocks",
                size.0, size.1, size.2, b.total_blocks()
            );

            let clears = generate_clear_commands(*b);
            println!("Clear commands: {} (32x32x32 chunks)", clears.len());
            clears
        }
        None => {
            println!("Warning: Could not determine bounding box, skipping clear");
            Vec::new()
        }
    }
}

fn apply_skip_and_filter(commands: Vec<String>, cli: &Cli) -> Vec<String> {
    let after_skip = apply_skip(commands, cli.skip);
    apply_material_filter(after_skip, &cli.material)
}

fn apply_skip(commands: Vec<String>, skip: usize) -> Vec<String> {
    if skip == 0 {
        return commands;
    }

    if skip >= commands.len() {
        println!(
            "Skip count ({}) >= total commands ({}). Nothing to execute.",
            skip,
            commands.len()
        );
        return Vec::new();
    }

    println!("Пропускаю первые {} команд...", skip);
    commands.into_iter().skip(skip).collect()
}

fn apply_material_filter(commands: Vec<String>, material: &Option<String>) -> Vec<String> {
    match material {
        Some(filter) => {
            let before = commands.len();
            let filtered = filter_by_material(commands, filter);
            println!(
                "Фильтр по материалу '{}': {} команд из {} прошли фильтр",
                filter,
                filtered.len(),
                before
            );
            filtered
        }
        None => commands,
    }
}

fn print_execution_info(commands: &[String], offset: &Offset) {
    println!("Команд к выполнению: {}", commands.len());

    if !offset.is_zero() {
        println!(
            "Применяется offset: X={}, Y={}, Z={}",
            offset.x, offset.y, offset.z
        );
    }
}

fn print_countdown_instructions() {
    println!("\nУ тебя {} секунд чтобы:", COUNTDOWN_SECONDS);
    println!("   1. Переключиться на Parallels Desktop");
    println!("   2. Кликнуть в окно Minecraft");
    println!("   3. ВАЖНО: Расположи окно Minecraft в НИЖНИЙ ЛЕВЫЙ угол экрана!");
    println!("   4. Убедиться что чат закрыт (нажми Esc)");
    println!();
}

fn execute_clear_phase(
    executor: &mut CommandExecutor,
    clear_commands: &[String],
    offset: Offset,
    should_clear: bool,
    cli: &Cli,
) -> Result<()> {
    if clear_commands.is_empty() {
        return Ok(());
    }

    if !should_clear {
        print_skip_clear_reason(cli);
        return Ok(());
    }

    println!("\n=== Очистка области ===");
    for (i, command) in clear_commands.iter().enumerate() {
        let cmd = apply_offset(command, offset);
        executor.execute(&cmd)?;
        println!("[clear {}/{}] {}", i + 1, clear_commands.len(), cmd);
    }
    println!("Очистка завершена!\n");

    Ok(())
}

fn print_skip_clear_reason(cli: &Cli) {
    if cli.skip > 0 {
        println!("\nℹ Пропускаю очистку области (используется --skip)\n");
    } else if cli.material.is_some() {
        println!("\nℹ Пропускаю очистку области (используется --material фильтр)\n");
    }
}

fn execute_build_phase(
    executor: &mut CommandExecutor,
    commands: &[String],
    offset: Offset,
    skip_count: usize,
) -> Result<()> {
    println!("=== Строительство ===");

    let total = skip_count + commands.len();

    for (i, command) in commands.iter().enumerate() {
        let cmd = apply_offset(command, offset);
        executor.execute(&cmd)?;
        println!("[{}/{}] {}", skip_count + i + 1, total, cmd);
    }

    Ok(())
}

fn print_completion(count: usize, skip: usize) {
    println!();
    println!(
        "Готово! Выполнено команд: {} (с {} по {})",
        count,
        skip + 1,
        skip + count
    );
}
