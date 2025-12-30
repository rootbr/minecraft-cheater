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

    // Читаем команды из файла
    let file = File::open("commands.txt")?;
    let reader = BufReader::new(file);

    let commands: Vec<String> = reader
        .lines()
        .filter_map(|line| line.ok())
        .filter(|line| {
            let trimmed = line.trim();
            // Пропускаем пустые строки, комментарии и заголовки
            !trimmed.is_empty()
                && !trimmed.starts_with('#')
                && !trimmed.starts_with('=')
        })
        .map(|line| {
            let trimmed = line.trim();
            trimmed.to_string()
        })
        .collect();

    println!("═══════════════════════════════════════════");
    println!("       MC Commander - Автоввод команд");
    println!("═══════════════════════════════════════════");
    println!();
    println!("Найдено команд: {}", commands.len());
    println!("Задержка между командами: {} мс", 100);
    println!("Пропущено команд: {}", 0);
    println!();
    println!("⚠️  У тебя {} секунд чтобы:", 5);
    println!("   1. Переключиться на Parallels Desktop");
    println!("   2. Кликнуть в окно Minecraft");
    println!("   3. Убедиться что чат закрыт (нажми Esc)");
    println!();

    // Обратный отсчёт
    for i in (1..=5).rev() {
        println!("Начинаю через {}...", i);
        thread::sleep(Duration::from_secs(1));
    }

    println!();
    println!("🚀 ПОЕХАЛИ!");
    println!();

    let mut enigo = Enigo::new(&Settings::default())?;
    let mut clipboard = Clipboard::new()?;

    for (i, command) in commands.iter().enumerate() {
        println!("[{}/{}] {}", i + 1, commands.len(), command);

        // 1. Открываем чат (клавиша T или /)
        // В Bedrock лучше использовать /
        enigo.key(Key::Other(47), Click)?; // '/' key
        thread::sleep(Duration::from_millis(500));

        // 2. Копируем команду в буфер обмена
        clipboard.set_text(command)?;
        thread::sleep(Duration::from_millis(100));

        // 3. Вставляем из буфера (Cmd+V на macOS)
        enigo.key(Key::Meta, Press)?;
        enigo.key(Key::Unicode('v'), Click)?;
        enigo.key(Key::Meta, Release)?;
        thread::sleep(Duration::from_millis(400));

        // 4. Нажимаем Enter для выполнения
        enigo.key(Key::Return, Click)?;

        // 5. Ждём перед следующей командой
        thread::sleep(Duration::from_millis(250));
    }

    println!();
    println!("═══════════════════════════════════════════");
    println!("✅ Готово! Выполнено команд: {}", commands.len());
    println!("═══════════════════════════════════════════");

    Ok(())
}
