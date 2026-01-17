// Configuration constants and structures

use std::time::Duration;

// Timing constants (milliseconds)
pub const KEY_PRESS_DELAY_MS: u64 = 50;
pub const STATE_TIMEOUT_SECS: u64 = 3;
pub const POLL_INTERVAL_MS: u64 = 50;
pub const COUNTDOWN_SECONDS: u64 = 3;

// Minecraft limits
pub const CHUNK_SIZE: i32 = 32;

#[derive(Clone, Copy, Default)]
pub struct Offset {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

impl Offset {
    pub fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }

    pub fn is_zero(&self) -> bool {
        self.x == 0 && self.y == 0 && self.z == 0
    }
}

pub struct Timing;

impl Timing {
    pub fn key_press_delay() -> Duration {
        Duration::from_millis(KEY_PRESS_DELAY_MS)
    }

    pub fn state_timeout() -> Duration {
        Duration::from_secs(STATE_TIMEOUT_SECS)
    }

    pub fn poll_interval() -> Duration {
        Duration::from_millis(POLL_INTERVAL_MS)
    }
}
