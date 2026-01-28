use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;

use crate::config::StairDirection;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

pub fn extract_path_from_url(url: &str) -> Option<String> {
    if let Some(path) = url.strip_prefix("https://www.grabcraft.com/minecraft/") {
        let slug = path.split('/').next().unwrap_or(path);
        let slug = slug.split('#').next().unwrap_or(slug);
        Some(slug.to_string())
    } else {
        None
    }
}

pub fn get_commands_file_path(url: &str, optimized: bool) -> Result<PathBuf> {
    let path = extract_path_from_url(url).ok_or("Invalid GrabCraft URL format")?;

    let filename = if optimized {
        "build_commands_optimized.txt"
    } else {
        "build_commands.txt"
    };

    Ok(PathBuf::from("grabcraft").join(path).join(filename))
}

pub fn ensure_commands_exist(url: &str) -> Result<PathBuf> {
    ensure_commands_exist_with_options(url, None, false, &StairDirection::Auto)
}

pub fn ensure_commands_exist_with_options(
    url: &str,
    logs: Option<Arc<Mutex<Vec<String>>>>,
    force_regenerate: bool,
    stair_direction: &StairDirection,
) -> Result<PathBuf> {
    let optimized_path = get_commands_file_path(url, true)?;
    let base_path = get_commands_file_path(url, false)?;

    let files_exist = optimized_path.exists() || base_path.exists();

    if files_exist && !force_regenerate {
        log_message(
            &logs,
            "Commands already exist. Loading from cache...".to_string(),
        );
        if optimized_path.exists() {
            return Ok(optimized_path);
        }
        return Ok(base_path);
    }

    if files_exist && force_regenerate {
        log_message(
            &logs,
            "Force regeneration requested. Deleting existing files...".to_string(),
        );
        if optimized_path.exists() {
            std::fs::remove_file(&optimized_path).ok();
        }
        if base_path.exists() {
            std::fs::remove_file(&base_path).ok();
        }
        log_message(&logs, "✓ Old files removed".to_string());
        log_message(&logs, String::new());
    }

    generate_commands_from_url(url, logs, stair_direction)?;

    if optimized_path.exists() {
        Ok(optimized_path)
    } else if base_path.exists() {
        Ok(base_path)
    } else {
        Err("Failed to generate commands from URL".into())
    }
}

fn log_message(logs: &Option<Arc<Mutex<Vec<String>>>>, message: String) {
    if let Some(logs) = logs {
        if let Ok(mut logs) = logs.lock() {
            logs.push(message.clone());
        }
    }
    println!("{}", message);
}

fn run_python_with_output(
    script: &str,
    args: Vec<String>,
    logs: &Option<Arc<Mutex<Vec<String>>>>,
) -> Result<()> {
    let mut child = Command::new("python3")
        .arg(script)
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    let logs_clone = logs.clone();
    let stdout_thread = thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(line) = line {
                log_message(&logs_clone, line);
            }
        }
    });

    let logs_clone = logs.clone();
    let stderr_thread = thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(line) = line {
                log_message(&logs_clone, format!("ERROR: {}", line));
            }
        }
    });

    stdout_thread.join().ok();
    stderr_thread.join().ok();

    let status = child.wait()?;
    if !status.success() {
        return Err(format!("Python script {} failed", script).into());
    }

    Ok(())
}

fn generate_commands_from_url(
    url: &str,
    logs: Option<Arc<Mutex<Vec<String>>>>,
    stair_direction: &StairDirection,
) -> Result<()> {
    let path = extract_path_from_url(url).ok_or("Invalid GrabCraft URL format")?;

    let dir_path = PathBuf::from("grabcraft").join(&path);
    std::fs::create_dir_all(&dir_path)?;

    let base_output = dir_path.join("build_commands.txt");
    let optimized_output = dir_path.join("build_commands_optimized.txt");
    let csv_output = dir_path.join("build.csv");

    log_message(&logs, format!("Generating commands from URL: {}", url));
    log_message(&logs, format!("Output directory: {}", dir_path.display()));
    log_message(&logs, String::new());

    let stair_arg = match stair_direction {
        StairDirection::Auto => "auto",
        StairDirection::Normal => "normal",
        StairDirection::Invert => "invert",
    };

    run_python_with_output(
        "grabcraft_to_commands.py",
        vec![
            url.to_string(),
            "-o".to_string(),
            base_output.to_string_lossy().to_string(),
            "--stair-direction".to_string(),
            stair_arg.to_string(),
            "--save-csv".to_string(),
            csv_output.to_string_lossy().to_string(),
        ],
        &logs,
    )?;

    if !base_output.exists() {
        return Err("grabcraft_to_commands.py did not create output file".into());
    }

    log_message(&logs, String::new());
    log_message(
        &logs,
        format!("✓ Base commands generated: {}", base_output.display()),
    );
    log_message(&logs, String::new());
    log_message(&logs, "Optimizing commands...".to_string());

    run_python_with_output(
        "optimize_commands.py",
        vec![
            base_output.to_string_lossy().to_string(),
            optimized_output.to_string_lossy().to_string(),
        ],
        &logs,
    )?;

    if optimized_output.exists() {
        log_message(&logs, String::new());
        log_message(
            &logs,
            format!(
                "✓ Optimized commands generated: {}",
                optimized_output.display()
            ),
        );
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_path_from_url() {
        let url = "https://www.grabcraft.com/minecraft/american-suburban-home-4/modern-houses#blueprints";
        assert_eq!(extract_path_from_url(url), Some("american-suburban-home-4".to_string()));

        let url = "https://www.grabcraft.com/minecraft/simple-house#blueprints";
        assert_eq!(extract_path_from_url(url), Some("simple-house".to_string()));

        let url = "https://www.grabcraft.com/minecraft/another-house";
        assert_eq!(extract_path_from_url(url), Some("another-house".to_string()));

        let url = "https://other-site.com/minecraft/house";
        assert_eq!(extract_path_from_url(url), None);
    }
}
