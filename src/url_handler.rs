use std::path::PathBuf;
use std::process::Command;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

pub fn extract_path_from_url(url: &str) -> Option<String> {
    if url.starts_with("https://www.grabcraft.com/minecraft/") {
        let path = url.trim_start_matches("https://www.grabcraft.com/minecraft/");
        Some(path.to_string())
    } else {
        None
    }
}

pub fn get_commands_file_path(url: &str, optimized: bool) -> Result<PathBuf> {
    let path = extract_path_from_url(url)
        .ok_or("Invalid GrabCraft URL format")?;

    let filename = if optimized {
        "build_commands_optimized.txt"
    } else {
        "build_commands.txt"
    };

    Ok(PathBuf::from(path).join(filename))
}

pub fn ensure_commands_exist(url: &str) -> Result<PathBuf> {
    let optimized_path = get_commands_file_path(url, true)?;
    let base_path = get_commands_file_path(url, false)?;

    if optimized_path.exists() {
        return Ok(optimized_path);
    }

    if base_path.exists() {
        return Ok(base_path);
    }

    generate_commands_from_url(url)?;

    if optimized_path.exists() {
        Ok(optimized_path)
    } else if base_path.exists() {
        Ok(base_path)
    } else {
        Err("Failed to generate commands from URL".into())
    }
}

fn generate_commands_from_url(url: &str) -> Result<()> {
    let path = extract_path_from_url(url)
        .ok_or("Invalid GrabCraft URL format")?;

    let dir_path = PathBuf::from(&path);
    std::fs::create_dir_all(&dir_path)?;

    let base_output = dir_path.join("build_commands.txt");
    let optimized_output = dir_path.join("build_commands_optimized.txt");

    println!("Generating commands from URL: {}", url);
    println!("Output directory: {}", dir_path.display());

    let status = Command::new("python3")
        .arg("grabcraft_to_commands.py")
        .arg(url)
        .arg("-o")
        .arg(&base_output)
        .status()?;

    if !status.success() {
        return Err("Failed to run grabcraft_to_commands.py".into());
    }

    if !base_output.exists() {
        return Err("grabcraft_to_commands.py did not create output file".into());
    }

    println!("Base commands generated: {}", base_output.display());

    println!("Optimizing commands...");
    let status = Command::new("python3")
        .arg("optimize_commands.py")
        .arg(&base_output)
        .arg(&optimized_output)
        .status()?;

    if !status.success() {
        return Err("Failed to run optimize_commands.py".into());
    }

    if optimized_output.exists() {
        println!("Optimized commands generated: {}", optimized_output.display());
    }

    Ok(())
}
