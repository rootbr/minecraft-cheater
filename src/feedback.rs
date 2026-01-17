use image::{DynamicImage, Rgba};
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

        let mut rgba_data = Vec::with_capacity(frame.len());
        for bgra in frame.chunks_exact(4) {
            rgba_data.extend_from_slice(&[bgra[2], bgra[1], bgra[0], bgra[3]]);
        }

        let img = image::RgbaImage::from_raw(self.width as u32, self.height as u32, rgba_data)
            .expect("Failed to create image");

        DynamicImage::ImageRgba8(img)
    }


    /// Wait for expected chat state, return last state on timeout
    pub fn wait_for_state(&mut self, expected: ChatState, timeout: Duration) -> ChatState {
        let start = Instant::now();
        let mut iteration = 0;
        loop {
            iteration += 1;
            let elapsed = start.elapsed();

            if self.check_state_with_debug(expected, iteration, elapsed) {
                println!("✓ Chat state {:?} (detected in {:?}, {} iterations)", expected, elapsed, iteration);
                return expected;
            }

            if elapsed >= timeout {
                let actual = self.detect_chat_state();
                println!("⏱ Timeout after {:?} ({} iterations), expected {:?}, got {:?}",
                    elapsed, iteration, expected, actual);
                return actual;
            }
            thread::sleep(Timing::poll_interval());
        }
    }

    fn check_state_with_debug(&mut self, expected: ChatState, iteration: i32, elapsed: Duration) -> bool {
        match expected {
            ChatState::Open => {
                if self.check_region(self.command_region) != ChatState::Open {
                    if elapsed.as_millis() > 500 {
                        println!("Итерация {}: [{:?}] ChatState::Open не совпало: не все пиксели (198,198,198)", iteration, elapsed);
                    }
                    return false;
                }
                true
            }
            ChatState::CommandEntered => {
                if self.check_region(self.command_region) != ChatState::CommandEntered {
                    if elapsed.as_millis() > 500 {
                        println!("Итерация {}: [{:?}] ChatState::CommandEntered не совпало: не все пиксели (117,117,117)", iteration, elapsed);
                    }
                    return false;
                }
                true
            }
            ChatState::Closed => {
                if self.check_region(self.health_region) != ChatState::Closed {
                    if elapsed.as_millis() > 500 {
                        println!("Итерация {}: [{:?}] ChatState::Closed не совпало", iteration, elapsed);
                    }
                    return false;
                }
                true
            }
            ChatState::Undefined => false,
        }
    }



    pub fn detect_chat_state(&mut self) -> ChatState {
        if self.is_command_empty() {
            return ChatState::Open;
        }
        if self.is_command_entered() {
            return ChatState::CommandEntered;
        }
        if self.is_closed() {
            return ChatState::Closed;
        }
        ChatState::Undefined
    }

    fn is_closed(&mut self) -> bool {
        self.check_region(self.health_region) == ChatState::Closed
    }

    fn is_command_empty(&mut self) -> bool {
        self.check_region(self.command_region) == ChatState::Open
    }

    fn is_command_entered(&mut self) -> bool {
        self.check_region(self.command_region) == ChatState::CommandEntered
    }

    fn check_region(&mut self, region: (u32, u32, u32, u32)) -> ChatState {
        let (rx, ry, rw, rh) = region;
        let frame = loop {
            if let Ok(frame) = self.capturer.frame() {
                break frame;
            }
            thread::sleep(Duration::from_millis(1));
        };

        let stride = self.width * 4;
        let mut has_heart = false;
        let mut has_health = false;
        let mut all_198 = true;
        let mut all_117 = true;

        for y in ry..(ry + rh) {
            let row_start = (y as usize) * stride;
            for x in rx..(rx + rw) {
                let pixel_start = row_start + (x as usize) * 4;
                if pixel_start + 3 < frame.len() {
                    let b = frame[pixel_start];
                    let g = frame[pixel_start + 1];
                    let r = frame[pixel_start + 2];
                    // a = frame[pixel_start + 3];

                    // Check for Open (117, 117, 117)
                    if !Self::color_matches(r, 117, 5) || !Self::color_matches(g, 117, 5) || !Self::color_matches(b, 117, 5) {
                        all_198 = false;
                    }

                    // Check for CommandEntered (198, 198, 198)
                    if !Self::color_matches(r, 198, 5) || !Self::color_matches(g, 198, 5) || !Self::color_matches(b, 198, 5) {
                        all_117 = false;
                    }

                    // Check for Closed (217, 61, 41) and (148, 235, 58)
                    if Self::color_matches(r, 217, 5) && Self::color_matches(g, 61, 5) && Self::color_matches(b, 41, 5) {
                        has_heart = true;
                    } else if Self::color_matches(r, 148, 5) && Self::color_matches(g, 235, 5) && Self::color_matches(b, 58, 5) {
                        has_health = true;
                    }
                }
            }
        }

        if all_198 {
            return ChatState::Open;
        }
        if all_117 {
            return ChatState::CommandEntered;
        }
        if has_heart && has_health {
            return ChatState::Closed;
        }

        ChatState::Undefined
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
