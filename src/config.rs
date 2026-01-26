// Configuration constants and structures

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::time::Duration;

// Timing constants (milliseconds)
pub const KEY_PRESS_DELAY_MS: u64 = 50;
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

    #[serde(default)]
    pub screen_regions: ScreenRegionsConfig,
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

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ScreenRegion {
    pub x: u32,
    pub y: u32,
    pub width: u32,
    pub height: u32,
}

impl Default for ScreenRegion {
    fn default() -> Self {
        Self {
            x: 0,
            y: 0,
            width: 0,
            height: 0,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ScreenRegionsConfig {
    #[serde(default = "default_panel_region")]
    pub panel_region: ScreenRegion,

    #[serde(default = "default_health_region")]
    pub health_region: ScreenRegion,

    #[serde(default = "default_command_region")]
    pub command_region: ScreenRegion,
}

fn default_panel_region() -> ScreenRegion {
    ScreenRegion {
        x: 75,
        y: 645,
        width: 75,
        height: 30,
    }
}

fn default_health_region() -> ScreenRegion {
    ScreenRegion {
        x: 450,
        y: 1360,
        width: 200,
        height: 20,
    }
}

fn default_command_region() -> ScreenRegion {
    ScreenRegion {
        x: 1250,
        y: 1392,
        width: 15,
        height: 40,
    }
}

impl Default for ScreenRegionsConfig {
    fn default() -> Self {
        Self {
            panel_region: default_panel_region(),
            health_region: default_health_region(),
            command_region: default_command_region(),
        }
    }
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

    pub fn save_to_file<P: AsRef<Path>>(&self, path: P) -> Result<(), Box<dyn std::error::Error>> {
        let content = toml::to_string_pretty(self)?;
        fs::write(path, content)?;
        Ok(())
    }

    pub fn offset(&self) -> Offset {
        Offset::new(
            self.coordinates.offset_x,
            self.coordinates.offset_y,
            self.coordinates.offset_z,
        )
    }
}
