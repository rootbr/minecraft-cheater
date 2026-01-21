// Configuration constants and structures

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::time::Duration;

// Timing constants (milliseconds)
pub const KEY_PRESS_DELAY_MS: u64 = 40;
pub const STATE_TIMEOUT_SECS: u64 = 1;
pub const POLL_INTERVAL_MS: u64 = 40;

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

#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub execution: ExecutionConfig,

    #[serde(default)]
    pub coordinates: CoordinatesConfig,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ExecutionConfig {
    #[serde(default = "default_url")]
    pub url: String,

    #[serde(default)]
    pub skip: usize,

    #[serde(default)]
    pub material: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CoordinatesConfig {
    #[serde(default)]
    pub offset_x: i32,

    #[serde(default)]
    pub offset_y: i32,

    #[serde(default)]
    pub offset_z: i32,
}

impl Default for ExecutionConfig {
    fn default() -> Self {
        Self {
            url: default_url(),
            skip: 0,
            material: None,
        }
    }
}

impl Default for CoordinatesConfig {
    fn default() -> Self {
        Self {
            offset_x: 0,
            offset_y: 0,
            offset_z: 0,
        }
    }
}

fn default_url() -> String {
    "https://www.grabcraft.com/minecraft/small-modern-villa/modern-houses".to_string()
}

impl Config {
    pub fn from_file<P: AsRef<Path>>(path: P) -> Result<Self, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let config: Config = toml::from_str(&content)?;
        Ok(config)
    }

    pub fn offset(&self) -> Offset {
        Offset::new(
            self.coordinates.offset_x,
            self.coordinates.offset_y,
            self.coordinates.offset_z,
        )
    }
}
