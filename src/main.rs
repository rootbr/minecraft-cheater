mod clear;
mod commands;
mod config;
mod executor;
mod feedback;
mod gui;
mod staircase;
mod url_handler;

use clap::{Parser, Subcommand};

use clear::execute_clear;
use commands::{apply_offset, find_bounding_box, load_from_file};
use config::{Config, Offset};
use executor::CommandExecutor;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

const DEFAULT_CONFIG_PATH: &str = "config.toml";

#[derive(Parser)]
#[command(name = "mc-commander")]
#[command(about = "Minecraft command generator and executor")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    #[arg(short, long, default_value = DEFAULT_CONFIG_PATH)]
    config: String,
}

#[derive(Subcommand)]
enum Commands {
    Cli,
    Staircase,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Cli) => {
            let config = load_config(&cli.config)?;
            run_from_file(&config)
        }
        Some(Commands::Staircase) => {
            let config = load_config(&cli.config)?;
            run_staircase(&config)
        }
        None => gui::run_gui(),
    }
}

fn load_config(path: &str) -> Result<Config> {
    println!("Loading configuration from: {}", path);
    Config::from_file(path)
}

fn run_staircase(config: &Config) -> Result<()> {
    println!("Generating staircase commands...");
    let commands = staircase::generate_commands();
    execute_commands(config, commands)
}

fn run_from_file(config: &Config) -> Result<()> {
    println!("Loading commands from URL: {}", config.execution.url);

    let file_path = url_handler::ensure_commands_exist(&config.execution.url)?;
    println!("Reading commands from: {}", file_path.display());

    let commands = load_from_file(&file_path.to_string_lossy())?;
    execute_commands(config, commands)
}

fn execute_commands(config: &Config, commands: Vec<String>) -> Result<()> {
    let offset = config.offset();
    let clear_bbox = find_clear_bbox(config, &commands);
    let commands = filter_commands(commands, config);

    if commands.is_empty() {
        return Ok(());
    }

    let mut executor = CommandExecutor::with_config(&config.screen_regions)?;
    executor.activate_minecraft_window()?;

    perform_clear_phase(&mut executor, clear_bbox, offset, config)?;
    perform_build_phase(&mut executor, &commands, offset, config.execution.skip)?;

    Ok(())
}

fn find_clear_bbox(config: &Config, commands: &[String]) -> Option<commands::BoundingBox> {
    if config.execution.skip == 0 {
        find_bounding_box(commands)
    } else {
        None
    }
}

fn filter_commands(commands: Vec<String>, config: &Config) -> Vec<String> {
    let commands = apply_skip(commands, config.execution.skip);
    apply_material_filter(commands, &config.execution.material)
}

fn perform_clear_phase(
    executor: &mut CommandExecutor,
    bbox: Option<commands::BoundingBox>,
    offset: Offset,
    config: &Config,
) -> Result<()> {
    if config.execution.skip == 0 && config.execution.material.is_none() {
        if let Some(bbox) = bbox {
            execute_clear(executor, bbox, offset, None, None, None)?;
        }
    }
    Ok(())
}

fn perform_build_phase(
    executor: &mut CommandExecutor,
    commands: &[String],
    offset: Offset,
    skip_count: usize,
) -> Result<()> {
    execute_build_phase(executor, commands, offset, skip_count)
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
        Some(filter) => commands
            .into_iter()
            .filter(|cmd| cmd.contains(filter))
            .collect(),
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
        let stats = executor.execute(&cmd, None)?;

        print!("[{}/{}] {}", skip_count + i + 1, total, cmd);
        if let Some(s) = stats {
            println!(
                " ({}ms {}/{}/{} iterations)",
                s.total_time.as_millis(),
                s.iterations[0],
                s.iterations[1],
                s.iterations[2]
            );
        } else {
            println!();
        }
    }
    Ok(())
}
