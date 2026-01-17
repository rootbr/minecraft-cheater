use image::{DynamicImage, GenericImageView, Rgba};
use scrap::{Capturer, Display};
use std::thread;
use std::time::{Duration, Instant};

use crate::config::Timing;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChatState {
    Open,
    CommandEntered,
    Closed,
    Undefined,
}

pub struct FeedbackDetector {
    capturer: Capturer,
    width: usize,
    height: usize,
    panel_region: (u32, u32, u32, u32), // (x, y, width, height)
    health_region: (u32, u32, u32, u32), // (x, y, width, height)
    command_region: (u32, u32, u32, u32), // (x, y, width, height)
}

impl FeedbackDetector {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let display = Display::primary()?;
        let width = display.width();
        let height = display.height();
        let capturer = Capturer::new(display)?;
        Ok(Self {
            capturer,
            width,
            height,
            panel_region: (75, 635, 75, 35),
            health_region: (440, 1355, 200, 20),
            command_region: (1210, 1390, 25, 45),
        })
    }

    fn capture_screen(&mut self) -> DynamicImage {
        // Wait for frame
        let frame = loop {
            if let Ok(frame) = self.capturer.frame() {
                break frame;
            }
            thread::sleep(Duration::from_millis(1));
        };

        // Convert BGRA to RGBA
        let rgba_data: Vec<u8> = frame
            .chunks_exact(4)
            .flat_map(|bgra| [bgra[2], bgra[1], bgra[0], bgra[3]])
            .collect();

        let img = image::RgbaImage::from_raw(self.width as u32, self.height as u32, rgba_data)
            .expect("Failed to create image");

        DynamicImage::ImageRgba8(img)
    }

    /// Wait for expected chat state, return last state on timeout
    pub fn wait_for_state(&mut self, expected: ChatState, timeout: Duration) -> ChatState {
        let start = Instant::now();
        loop {
            let state = self.detect_chat_state();
            if state == expected {
                println!("✓ Chat state {:?} (detected in {:?})", state, start.elapsed());
                return state;
            }
            if start.elapsed() >= timeout {
                println!("⏱ Timeout, last state: {:?}", state);
                return state;
            }
            thread::sleep(Timing::poll_interval());
        }
    }

    pub fn detect_chat_state(&mut self) -> ChatState {
        let screenshot = self.capture_screen();
        if self.is_command_empty(&screenshot) {
            return ChatState::Open;
        }
        if self.is_command_entered(&screenshot) {
            return ChatState::CommandEntered;
        }
        if self.is_closed(&screenshot) {
            return ChatState::Closed;
        }
        ChatState::Undefined
    }

    fn is_open(&self, screenshot: &DynamicImage) -> bool {
        let (x, y, width, height) = self.panel_region;
        let panel = screenshot.crop_imm(x, y, width, height);
        panel.pixels().all(|p| Self::rgb_matches(&p.2, 198, 198, 198, 5))
    }

    fn is_closed(&self, screenshot: &DynamicImage) -> bool {
        let (x, y, width, height) = self.health_region;
        let health = screenshot.crop_imm(x, y, width, height);
        let mut has_heart = false;
        let mut has_health = false;
        for pixel in health.pixels() {
            let rgba = pixel.2;
            if Self::rgb_matches(&rgba, 217, 61, 41, 5) {
                has_heart = true;
            } else if Self::rgb_matches(&rgba, 148, 235, 58, 5) {
                has_health = true;
            }
        }
        has_heart && has_health
    }

    fn is_command_empty(&self, screenshot: &DynamicImage) -> bool {
        let (x, y, width, height) = self.command_region;
        let command = screenshot.crop_imm(x, y, width, height);
        command.pixels().all(|p| Self::rgb_matches(&p.2, 117, 117, 117, 5))
    }

    fn is_command_entered(&self, screenshot: &DynamicImage) -> bool {
        let (x, y, width, height) = self.command_region;
        let command = screenshot.crop_imm(x, y, width, height);
        command.pixels().all(|p| Self::rgb_matches(&p.2, 198, 198, 198, 5))
    }

    fn rgb_matches(rgba: &Rgba<u8>, r: u8, g: u8, b: u8, tolerance: u8) -> bool {
        Self::color_matches(rgba[0], r, tolerance) &&
            Self::color_matches(rgba[1], g, tolerance) &&
            Self::color_matches(rgba[2], b, tolerance)
    }

    fn color_matches(value: u8, target: u8, tolerance: u8) -> bool {
        let min = target.saturating_sub(tolerance);
        let max = target.saturating_add(tolerance);
        value >= min && value <= max
    }

    fn draw_rectangle(&self, img: &mut image::RgbaImage, x: u32, y: u32, width: u32, height: u32, color: Rgba<u8>) {
        let border_thickness = 5; // Make borders thicker (5 pixels)

        // Draw thick borders
        for t in 0..border_thickness {
            // Top and bottom borders
            for dx in 0..width {
                if x + dx < img.width() && y + t < img.height() {
                    img.put_pixel(x + dx, y + t, color);
                }
                if x + dx < img.width() && y + height > t && y + height - 1 - t < img.height() {
                    img.put_pixel(x + dx, y + height - 1 - t, color);
                }
            }

            // Left and right borders
            for dy in 0..height {
                if x + t < img.width() && y + dy < img.height() {
                    img.put_pixel(x + t, y + dy, color);
                }
                if x + width > t && x + width - 1 - t < img.width() && y + dy < img.height() {
                    img.put_pixel(x + width - 1 - t, y + dy, color);
                }
            }
        }
    }

    /// Show live preview during countdown - capture and save screenshots every second
    pub fn show_live_preview(&mut self, seconds: u32) {
        println!("📹 Live preview: Capturing detection regions every second...");
        println!("   🔴 Red box = Chat detection area");
        println!("   🔵 Blue box = Health detection area");
        println!("   🟡 Yellow box = Command detection area");
        println!("   Position your Minecraft window in the bottom-left corner!");
        println!();

        for i in 0..seconds {
            // Capture and annotate
            let screenshot = self.capture_screen();
            let mut img = screenshot.to_rgba8();

            // Draw colored rectangles with filled semi-transparent overlay
            let (chat_x, chat_y, chat_w, chat_h) = self.panel_region;
            self.draw_filled_region(&mut img, chat_x, chat_y, chat_w, chat_h, Rgba([255, 0, 0, 60]));
            self.draw_rectangle(&mut img, chat_x, chat_y, chat_w, chat_h, Rgba([255, 0, 0, 255]));

            let (resp_x, resp_y, resp_w, resp_h) = self.health_region;
            self.draw_filled_region(&mut img, resp_x, resp_y, resp_w, resp_h, Rgba([0, 0, 255, 60]));
            self.draw_rectangle(&mut img, resp_x, resp_y, resp_w, resp_h, Rgba([0, 0, 255, 255]));

            let (cmd_x, cmd_y, cmd_w, cmd_h) = self.command_region;
            self.draw_filled_region(&mut img, cmd_x, cmd_y, cmd_w, cmd_h, Rgba([255, 255, 0, 60]));
            self.draw_rectangle(&mut img, cmd_x, cmd_y, cmd_w, cmd_h, Rgba([255, 255, 0, 255]));

            // Save preview
            let output_path = format!("/tmp/mc_preview_{}.png", i);
            img.save(&output_path).expect("Failed to save preview");

            println!("   [{}s] Preview saved: {}", seconds - i, output_path);

            if i < seconds - 1 {
                thread::sleep(Duration::from_secs(1));
            }
        }

        println!();
        println!("✅ Preview complete! Last capture saved to /tmp/mc_preview_{}.png", seconds - 1);
        println!("   Open this file to verify the regions are positioned correctly");
        println!();
    }

    fn draw_filled_region(&self, img: &mut image::RgbaImage, x: u32, y: u32, width: u32, height: u32, color: Rgba<u8>) {
        // Fill region with semi-transparent color
        for dy in 0..height {
            for dx in 0..width {
                let px = x + dx;
                let py = y + dy;

                if px < img.width() && py < img.height() {
                    let existing = img.get_pixel(px, py);

                    // Alpha blend
                    let alpha = color[3] as f32 / 255.0;
                    let inv_alpha = 1.0 - alpha;

                    let r = (color[0] as f32 * alpha + existing[0] as f32 * inv_alpha) as u8;
                    let g = (color[1] as f32 * alpha + existing[1] as f32 * inv_alpha) as u8;
                    let b = (color[2] as f32 * alpha + existing[2] as f32 * inv_alpha) as u8;

                    img.put_pixel(px, py, Rgba([r, g, b, 255]));
                }
            }
        }
    }
}
