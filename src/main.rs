mod clear;
mod commands;
mod config;
mod executor;
mod feedback;
mod staircase;

use clap::{Parser, Subcommand};

use clear::execute_clear;
use commands::{apply_offset, find_bounding_box, load_from_file};
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
    let offset = Offset::new(cli.offset_x, cli.offset_y, cli.offset_z);
    let commands = apply_skip(commands, cli.skip);
    let commands = apply_material_filter(commands, &cli.material);
    if commands.is_empty() {
        return Ok(());
    }
    let mut executor = CommandExecutor::new()?;
    executor.show_countdown(COUNTDOWN_SECONDS);

    if cli.skip == 0 && cli.material.is_none() {
        if let Some(b) = find_bounding_box(&commands) {
            execute_clear(&mut executor, b, offset)?;
        }
    }
    execute_build_phase(&mut executor, &commands, offset, cli.skip)?;
    Ok(())
}

fn apply_skip(commands: Vec<String>, skip: usize) -> Vec<String> {
    if skip == 0 {
        return commands;
    }
    if skip >= commands.len() {
        return Vec::new();
    }
    commands.into_iter().skip(skip).collect()
}

fn apply_material_filter(commands: Vec<String>, material: &Option<String>) -> Vec<String> {
    match material {
        Some(filter) => {
            commands
                .into_iter()
                .filter(|cmd| cmd.contains(filter))
                .collect()
        }
        None => commands,
    }
}

fn execute_build_phase(
    executor: &mut CommandExecutor,
    commands: &[String],
    offset: Offset,
    skip_count: usize,
) -> Result<()> {
    let total = skip_count + commands.len();
    for (i, command) in commands.iter().enumerate() {
        let cmd = apply_offset(command, offset);
        executor.execute(&cmd)?;
        println!("[{}/{}] {}", skip_count + i + 1, total, cmd);
    }
    Ok(())
}
