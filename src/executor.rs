// Command execution via keyboard emulation

use arboard::Clipboard;
use enigo::{
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Settings,
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
        let s1 = self.open_chat()?;
        let s2 = self.paste_command()?;
        let s3 = self.send_command()?;
        let total_time = start.elapsed();

        Ok(CommandStats {
            total_time,
            iterations: [s1.iterations, s2.iterations, s3.iterations],
        })
    }

    fn copy_to_clipboard(&mut self, command: &str) -> Result<()> {
        self.clipboard.set_text(command)?;
        Ok(())
    }

    fn open_chat(&mut self) -> Result<WaitStats> {
        let mut total_iterations = 0;
        loop {
            self.enigo.key(CHAT_KEY, Click)?;
            let (state, stats) = self.detector.wait_for_state(ChatState::Open, Timing::state_timeout());
            total_iterations += stats.iterations;
            if matches!(state, ChatState::Open) {
                return Ok(WaitStats { elapsed: stats.elapsed, iterations: total_iterations });
            }
        }
    }

    fn paste_command(&mut self) -> Result<WaitStats> {
        let mut total_iterations = 0;
        loop {
            thread::sleep(Timing::key_press_delay());
            self.enigo.key(Key::Meta, Press)?;
            thread::sleep(Timing::key_press_delay());

            self.enigo.key(PASTE_KEY, Click)?;
            thread::sleep(Timing::key_press_delay());
            self.enigo.key(Key::Meta, Release)?;

            let (state, stats) = self.detector.wait_for_state(ChatState::CommandEntered, Timing::state_timeout());
            total_iterations += stats.iterations;
            if matches!(state, ChatState::CommandEntered) {
                return Ok(WaitStats { elapsed: stats.elapsed, iterations: total_iterations });
            }
        }
    }

    fn send_command(&mut self) -> Result<WaitStats> {
        let mut total_iterations = 0;
        loop {
            self.enigo.key(Key::Return, Click)?;
            let (state, stats) = self.detector.wait_for_state(ChatState::Closed, Timing::state_timeout());
            total_iterations += stats.iterations;
            if matches!(state, ChatState::Closed) {
                return Ok(WaitStats { elapsed: stats.elapsed, iterations: total_iterations });
            }
        }
    }

    pub fn show_countdown(&mut self, seconds: u64) {
        let _ = self.detector.show_live_preview(seconds as u32);
    }
}
