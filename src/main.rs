use arboard::Clipboard;
use enigo::{
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Settings,
};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::thread;
use std::time::Duration;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let commands: Vec<String> = BufReader::new(File::open("commands.txt")?)
        .lines()
        .filter_map(|line| line.ok())
        .filter(|line| {
            let trimmed = line.trim();
            !trimmed.is_empty()
                && !trimmed.starts_with('#')
                && !trimmed.starts_with('=')
        })
        .map(|line| {
            let trimmed = line.trim();
            trimmed.to_string()
        })
        .collect();
    let delay_before_start = 5;
    println!("⚠️  У тебя {} секунд чтобы:", delay_before_start);
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
        thread::sleep(Duration::from_millis(250));
        println!("[{}/{}] {}", i + 1, commands.len(), command);
        clipboard.set_text(command)?;
        enigo.key(Key::Unicode('t'), Click)?;
        thread::sleep(Duration::from_millis(400));
        enigo.key(Key::Meta, Press)?;
        thread::sleep(Duration::from_millis(50));
        enigo.key(Key::Unicode('v'), Click)?;
        thread::sleep(Duration::from_millis(50));
        enigo.key(Key::Meta, Release)?;
        thread::sleep(Duration::from_millis(100));
        enigo.key(Key::Return, Click)?;
        thread::sleep(Duration::from_millis(100));
    }
    println!();
    println!("✅ Готово! Выполнено команд: {}", commands.len());
    Ok(())
}
