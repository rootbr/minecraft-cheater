// Command execution via keyboard emulation

use arboard::Clipboard;
use enigo::{
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Settings,
};
use std::thread;

use crate::config::{Timing, MAX_COMMAND_RETRIES};
use crate::feedback::{ChatState, FeedbackDetector};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

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

    pub fn execute(&mut self, command: &str) -> Result<()> {
        for attempt in 1..=MAX_COMMAND_RETRIES {
            match self.execute_once(command) {
                Ok(_) => return Ok(()),
                Err(e) => {
                    if attempt < MAX_COMMAND_RETRIES {
                        self.handle_retry(attempt, &e)?;
                    } else {
                        self.handle_failure(&e)?;
                        return Err(e);
                    }
                }
            }
        }
        Ok(())
    }

    fn handle_retry(&mut self, attempt: u32, error: &Box<dyn std::error::Error>) -> Result<()> {
        eprintln!(
            "⚠ Попытка {}/{} не удалась: {}. Нажимаю ESC и повторяю...",
            attempt, MAX_COMMAND_RETRIES, error
        );
        self.press_esc_twice()?;
        thread::sleep(Timing::retry_delay());
        eprintln!("  → Повторяю команду (попытка {})", attempt + 1);
        Ok(())
    }

    fn handle_failure(&mut self, error: &Box<dyn std::error::Error>) -> Result<()> {
        eprintln!("✗ Команда не выполнена после {} попыток: {}", MAX_COMMAND_RETRIES, error);
        self.press_esc_twice()
    }

    fn press_esc_twice(&mut self) -> Result<()> {
        self.enigo.key(Key::Escape, Click)?;
        thread::sleep(Timing::key_press_delay());
        self.enigo.key(Key::Escape, Click)?;
        thread::sleep(Timing::esc_delay());
        Ok(())
    }

    fn execute_once(&mut self, command: &str) -> Result<()> {
        self.copy_to_clipboard(command)?;

        loop {
            self.open_chat()?;
            self.paste_command()?;
            self.press_enter()?;

            if self.wait_for_chat_close() {
                break;
            }
            self.enigo.key(Key::Escape, Click)?;
            thread::sleep(Timing::key_press_delay());
        }

        Ok(())
    }

    fn copy_to_clipboard(&mut self, command: &str) -> Result<()> {
        self.clipboard.set_text(command)?;
        thread::sleep(Timing::clipboard_delay());
        Ok(())
    }

    fn open_chat(&mut self) -> Result<()> {
        loop {
            self.enigo.key(Key::Unicode('t'), Click)?;

            let state = self.detector.wait_for_state(ChatState::Open, Timing::state_timeout());

            if !matches!(state, ChatState::Closed) {
                break;
            }
        }
        Ok(())
    }

    fn paste_command(&mut self) -> Result<()> {
        thread::sleep(Timing::key_press_delay());
        self.enigo.key(Key::Meta, Press)?;
        thread::sleep(Timing::key_press_delay());
        self.enigo.key(Key::Unicode('v'), Click)?;
        thread::sleep(Timing::key_press_delay());
        self.enigo.key(Key::Meta, Release)?;
        Ok(())
    }

    fn press_enter(&mut self) -> Result<()> {
        thread::sleep(Timing::clipboard_delay());
        self.enigo.key(Key::Return, Click)?;
        Ok(())
    }

    fn wait_for_chat_close(&mut self) -> bool {
        let state = self.detector.wait_for_state(ChatState::Closed, Timing::state_timeout());
        !matches!(state, ChatState::Open)
    }

    pub fn show_countdown(&mut self, seconds: u64) {
        let _ = self.detector.show_live_preview(seconds as u32);
    }
}
