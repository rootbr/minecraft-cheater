// Command execution via keyboard emulation

use arboard::Clipboard;
use enigo::{
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Settings,
};
use std::thread;

use crate::config::Timing;
use crate::feedback::{ChatState, FeedbackDetector};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

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

    pub fn execute(&mut self, command: &str) -> Result<()> {
        if let Err(e) = self.execute_once(command) {
            eprintln!("⚠ Команда пропущена: {}", e);
        }
        Ok(())
    }

    fn execute_once(&mut self, command: &str) -> Result<()> {
        self.copy_to_clipboard(command)?;
        self.open_chat()?;
        self.paste_command()?;
        self.send_command()
    }

    fn copy_to_clipboard(&mut self, command: &str) -> Result<()> {
        self.clipboard.set_text(command)?;
        Ok(())
    }

    fn open_chat(&mut self) -> Result<()> {
        loop {
            self.enigo.key(CHAT_KEY, Click)?;
            let state = self.detector.wait_for_state(ChatState::Open, Timing::state_timeout());
            if matches!(state, ChatState::Open) {
                break;
            }
        }
        Ok(())
    }

    fn paste_command(&mut self) -> Result<()> {
        loop {
            thread::sleep(Timing::key_press_delay());
            self.enigo.key(Key::Meta, Press)?;
            thread::sleep(Timing::key_press_delay());

            self.enigo.key(PASTE_KEY, Click)?;
            thread::sleep(Timing::key_press_delay());
            self.enigo.key(Key::Meta, Release)?;

            let state = self.detector.wait_for_state(ChatState::CommandEntered, Timing::state_timeout());
            if matches!(state, ChatState::CommandEntered) {
                break;
            }
        }
        Ok(())
    }

    fn send_command(&mut self) -> Result<()> {
        loop {
            self.enigo.key(Key::Return, Click)?;
            let state = self.detector.wait_for_state(ChatState::Closed, Timing::state_timeout());
            if matches!(state, ChatState::Closed) {
                break;
            }
        }
        Ok(())
    }

    pub fn show_countdown(&mut self, seconds: u64) {
        let _ = self.detector.show_live_preview(seconds as u32);
    }
}
