// Command execution via keyboard emulation

use arboard::Clipboard;
use enigo::{
    Button, Coordinate,
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Mouse, Settings,
};
use std::thread;
use std::time::{Duration, Instant};

use crate::config::Timing;
use crate::feedback::{ChatState, FeedbackDetector, WaitStats};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

pub struct CommandStats {
    pub total_time: Duration,
    pub iterations: [i32; 3],
}

#[cfg(target_os = "macos")]
const CHAT_KEY: Key = Key::Other(17); // 't' keycode on macOS
#[cfg(not(target_os = "macos"))]
const CHAT_KEY: Key = Key::Unicode('t');

#[cfg(target_os = "macos")]
const PASTE_KEY: Key = Key::Other(9); // 'v' keycode on macOS
#[cfg(not(target_os = "macos"))]
const PASTE_KEY: Key = Key::Unicode('v');

pub struct CommandExecutor {
    enigo: Enigo,
    clipboard: Clipboard,
    detector: FeedbackDetector,
}

impl CommandExecutor {
    pub fn new() -> Result<Self> {
        let enigo = Enigo::new(&Settings::default())?;
        let clipboard = Clipboard::new()?;
        let detector = FeedbackDetector::new()?;

        Ok(Self { enigo, clipboard, detector })
    }

    pub fn execute(&mut self, command: &str) -> Result<Option<CommandStats>> {
        match self.execute_once(command) {
            Ok(stats) => Ok(Some(stats)),
            Err(e) => {
                eprintln!("⚠ Команда пропущена: {}", e);
                Ok(None)
            }
        }
    }

    fn execute_once(&mut self, command: &str) -> Result<CommandStats> {
        self.copy_to_clipboard(command)?;
        let start = Instant::now();

        loop {
            let s1 = match self.open_chat() {
                Ok(s) => s,
                Err(_) => {
                    self.ensure_chat_closed()?;
                    continue;
                }
            };
            let s2 = match self.paste_command() {
                Ok(s) => s,
                Err(_) => {
                    self.ensure_chat_closed()?;
                    continue;
                }
            };
            let s3 = match self.send_command() {
                Ok(s) => s,
                Err(_) => {
                    self.ensure_chat_closed()?;
                    continue;
                }
            };

            let total_time = start.elapsed();
            return Ok(CommandStats {
                total_time,
                iterations: [s1.iterations, s2.iterations, s3.iterations],
            });
        }
    }

    fn ensure_chat_closed(&mut self) -> Result<()> {
        let state = self.detector.detect_chat_state();
        if !matches!(state, ChatState::Closed) {
            self.enigo.key(Key::Escape, Click)?;
            thread::sleep(Timing::key_press_delay());
        }
        Ok(())
    }

    fn copy_to_clipboard(&mut self, command: &str) -> Result<()> {
        self.clipboard.set_text(command)?;
        Ok(())
    }

    fn open_chat(&mut self) -> Result<WaitStats> {
        self.enigo.key(CHAT_KEY, Click)?;
        let (state, stats) = self.detector.wait_for_state(ChatState::Open, Timing::state_timeout());
        if matches!(state, ChatState::Open) {
            Ok(stats)
        } else {
            Err("Timeout waiting for chat to open".into())
        }
    }

    fn paste_command(&mut self) -> Result<WaitStats> {
        self.enigo.key(Key::Meta, Press)?;
        thread::sleep(Timing::key_press_delay());

        self.enigo.key(PASTE_KEY, Click)?;
        thread::sleep(Timing::key_press_delay());
        self.enigo.key(Key::Meta, Release)?;

        let (state, stats) = self.detector.wait_for_state(ChatState::CommandEntered, Timing::state_timeout());
        if matches!(state, ChatState::CommandEntered) {
            thread::sleep(Timing::key_press_delay());
            Ok(stats)
        } else {
            Err("Timeout waiting for command paste".into())
        }
    }

    fn send_command(&mut self) -> Result<WaitStats> {
        self.enigo.key(Key::Return, Click)?;
        let (state, stats) = self.detector.wait_for_state(ChatState::Closed, Timing::state_timeout());
        if matches!(state, ChatState::Closed) {
            Ok(stats)
        } else {
            Err("Timeout waiting for command send".into())
        }
    }

    pub fn activate_minecraft_window(&mut self) -> Result<()> {
        println!("🖱️  Activating Minecraft window...");
        let (x, y) = self.detector.health_region_center();
        println!("   Clicking at health bar position: ({}, {})", x, y);

        self.enigo.move_mouse(x, y, Coordinate::Abs)?;
        thread::sleep(Duration::from_millis(100));
        self.enigo.button(Button::Left, Click)?;
        thread::sleep(Duration::from_millis(200));

        println!("✅ Window activated!");
        Ok(())
    }

    pub fn show_detection_preview(&mut self) -> Result<()> {
        self.detector.show_live_preview(5);
        Ok(())
    }
}
