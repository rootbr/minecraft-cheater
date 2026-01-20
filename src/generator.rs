use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

pub struct BuildPaths {
    pub original: PathBuf,
    pub optimized: PathBuf,
    pub csv: PathBuf,
}

impl BuildPaths {
    pub fn from_url(url: &str) -> Result<Self> {
        let path = parse_url_to_path(url)?;
        fs::create_dir_all(&path)?;

        Ok(Self {
            original: path.join("original.txt"),
            optimized: path.join("optimized.txt"),
            csv: path.join("blocks.csv"),
        })
    }
}

fn parse_url_to_path(url: &str) -> Result<PathBuf> {
    let parts: Vec<&str> = url
        .trim_end_matches('/')
        .split('/')
        .collect();

    if parts.len() < 2 {
        return Err("Invalid GrabCraft URL format".into());
    }

    let name = parts[parts.len() - 2];
    let category = parts[parts.len() - 1];

    Ok(PathBuf::from(format!("{}/{}", name, category)))
}

pub fn generate_from_url(url: &str) -> Result<BuildPaths> {
    let paths = BuildPaths::from_url(url)?;

    println!("Generating commands from GrabCraft URL...");
    println!("  URL: {}", url);
    println!("  Directory: {}", paths.original.parent().unwrap().display());

    run_grabcraft_script(url, &paths)?;
    run_optimize_script(&paths)?;

    println!("\nGeneration complete:");
    println!("  Original: {}", paths.original.display());
    println!("  Optimized: {}", paths.optimized.display());

    Ok(paths)
}

fn run_grabcraft_script(url: &str, paths: &BuildPaths) -> Result<()> {
    println!("\nRunning grabcraft_to_commands.py...");

    let output = Command::new("python3")
        .arg("grabcraft_to_commands.py")
        .arg(url)
        .arg("-o")
        .arg(&paths.original)
        .arg("--save-csv")
        .arg(&paths.csv)
        .output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("grabcraft_to_commands.py failed: {}", stderr).into());
    }

    print!("{}", String::from_utf8_lossy(&output.stdout));
    Ok(())
}

fn run_optimize_script(paths: &BuildPaths) -> Result<()> {
    println!("\nRunning optimize_commands.py...");

    let output = Command::new("python3")
        .arg("optimize_commands.py")
        .arg(&paths.original)
        .arg(&paths.optimized)
        .output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("optimize_commands.py failed: {}", stderr).into());
    }

    print!("{}", String::from_utf8_lossy(&output.stdout));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_url() {
        let url = "https://www.grabcraft.com/minecraft/small-modern-villa/modern-houses";
        let path = parse_url_to_path(url).unwrap();
        assert_eq!(path, PathBuf::from("small-modern-villa/modern-houses"));
    }

    #[test]
    fn test_parse_url_with_trailing_slash() {
        let url = "https://www.grabcraft.com/minecraft/castle-tower/military/";
        let path = parse_url_to_path(url).unwrap();
        assert_eq!(path, PathBuf::from("castle-tower/military"));
    }
}
