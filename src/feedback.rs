use image::{DynamicImage, GenericImageView, Rgba};
use scrap::{Capturer, Display};
use std::thread;
use std::time::{Duration, Instant};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum FeedbackError {
    #[error("Screen capture failed: {0}")]
    CaptureFailed(String),

    #[error("Detection timeout after {0} attempts")]
    DetectionTimeout(u32),

    #[error("OCR failed: {0}")]
    OcrFailed(String),

    #[error("Chat state detection failed: {0}")]
    ChatDetectionFailed(String),

    #[error("Command execution error: {0}")]
    CommandError(String),
}

pub type Result<T> = std::result::Result<T, FeedbackError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChatState {
    Closed,
    Opening,
    Open,
    Closing,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CommandResult {
    Success,
    Error(String),
    Unknown,
}

#[derive(Clone)]
pub struct RetryConfig {
    pub max_attempts_open: u32,     // For chat open (longer)
    pub max_attempts_close: u32,    // For chat close (shorter)
    pub initial_delay_ms: u64,
    pub poll_interval_ms: u64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts_open: 50,      // ~1000ms total for opening
            max_attempts_close: 20,     // ~200ms total for closing
            initial_delay_ms: 5,        // Shorter initial delay
            poll_interval_ms: 15,       // Poll every 15ms
        }
    }
}

pub struct FeedbackDetector {
    capturer: Option<Capturer>,
    width: usize,
    height: usize,
    retry_config: RetryConfig,
    chat_region: (u32, u32, u32, u32), // (x, y, width, height)
    response_region: (u32, u32, u32, u32),
}

impl FeedbackDetector {
    pub fn new() -> Result<Self> {
        Self::with_config(RetryConfig::default())
    }

    pub fn with_config(retry_config: RetryConfig) -> Result<Self> {
        // Initialize screen capturer
        let (capturer, width, height) = match Self::init_capturer() {
            Ok((c, w, h)) => (Some(c), w, h),
            Err(e) => {
                eprintln!("Warning: Failed to initialize screen capturer: {}", e);
                eprintln!("Feedback detection will be disabled");
                (None, 1920, 1080)
            }
        };

        // Calculate regions based on actual screen height
        // Chat region: bottom-left 600x300px (adjusted for higher resolution)
        let chat_y = if height > 1600 {
            height as u32 - 400  // For higher res screens (like 3024x1890)
        } else {
            height as u32 - 250  // For standard 1920x1080
        };
        let chat_region = (0, chat_y, 800, 350);

        // Response region: slightly higher to catch command responses
        let response_y = if height > 1600 {
            height as u32 - 500
        } else {
            height as u32 - 350
        };
        let response_region = (0, response_y, 800, 450);

        Ok(Self {
            capturer,
            width,
            height,
            retry_config,
            chat_region,
            response_region,
        })
    }

    fn init_capturer() -> Result<(Capturer, usize, usize)> {
        let display = Display::primary()
            .map_err(|e| FeedbackError::CaptureFailed(format!("Failed to get display: {:?}", e)))?;

        let width = display.width();
        let height = display.height();

        let capturer = Capturer::new(display)
            .map_err(|e| FeedbackError::CaptureFailed(format!("Failed to create capturer: {:?}", e)))?;

        Ok((capturer, width, height))
    }

    pub fn is_enabled(&self) -> bool {
        self.capturer.is_some()
    }

    fn capture_screen(&mut self) -> Result<DynamicImage> {
        let capturer = self
            .capturer
            .as_mut()
            .ok_or_else(|| FeedbackError::CaptureFailed("Capturer not initialized".to_string()))?;

        // Wait for frame
        let frame = loop {
            match capturer.frame() {
                Ok(frame) => break frame,
                Err(e) => {
                    // Check if it's a would-block error (wait and retry)
                    let err_str = format!("{:?}", e);
                    if err_str.contains("WouldBlock") || err_str.contains("would block") {
                        thread::sleep(Duration::from_millis(1));
                        continue;
                    } else {
                        return Err(FeedbackError::CaptureFailed(format!(
                            "Failed to capture frame: {:?}",
                            e
                        )));
                    }
                }
            }
        };

        // scrap returns BGRA format, convert to RGBA
        let mut rgba_data = Vec::with_capacity(frame.len());
        for chunk in frame.chunks(4) {
            if chunk.len() == 4 {
                rgba_data.push(chunk[2]); // R
                rgba_data.push(chunk[1]); // G
                rgba_data.push(chunk[0]); // B
                rgba_data.push(chunk[3]); // A
            }
        }

        let img = image::RgbaImage::from_raw(self.width as u32, self.height as u32, rgba_data)
            .ok_or_else(|| FeedbackError::CaptureFailed("Failed to create image".to_string()))?;

        Ok(DynamicImage::ImageRgba8(img))
    }

    fn crop_region(
        img: &DynamicImage,
        region: (u32, u32, u32, u32),
    ) -> DynamicImage {
        let (x, y, width, height) = region;
        img.crop_imm(x, y, width, height)
    }

    pub fn detect_chat_state(&mut self) -> Result<ChatState> {
        if !self.is_enabled() {
            return Err(FeedbackError::ChatDetectionFailed(
                "Feedback detection is disabled".to_string(),
            ));
        }

        let screenshot = self.capture_screen()?;
        let chat_area = Self::crop_region(&screenshot, self.chat_region);

        // Calculate actual darkness percentage for debugging
        let (dark_pixels, total_pixels) = Self::count_dark_pixels(&chat_area, 80);
        let dark_ratio = dark_pixels as f32 / total_pixels as f32;

        // Check for dark overlay (chat open)
        if dark_ratio >= 0.5 {
            Ok(ChatState::Open)
        } else {
            Ok(ChatState::Closed)
        }
    }

    fn count_dark_pixels(img: &DynamicImage, threshold: u8) -> (u32, u32) {
        let mut dark_count = 0u32;
        let mut total_pixels = 0u32;

        for pixel in img.pixels() {
            let rgba = pixel.2;
            let r = rgba[0];
            let g = rgba[1];
            let b = rgba[2];

            total_pixels += 1;

            // Check if pixel is dark (below threshold)
            if r < threshold && g < threshold && b < threshold {
                dark_count += 1;
            }
        }

        (dark_count, total_pixels)
    }

    pub fn wait_for_chat_open(&mut self) -> Result<()> {
        if !self.is_enabled() {
            // Fallback to fixed delay
            thread::sleep(Duration::from_millis(700));
            return Ok(());
        }

        let start = Instant::now();
        let poll_interval = Duration::from_millis(50); // Simple 200ms polling
        let timeout = Duration::from_secs(3); // 3 second timeout

        loop {
            match self.detect_chat_state() {
                Ok(ChatState::Open) => {
                    let elapsed = start.elapsed();
                    println!("✓ Chat opened (detected in {:?})", elapsed);
                    return Ok(());
                }
                Ok(_) => {
                    // Not open yet
                }
                Err(e) => {
                    eprintln!("⚠ Detection error: {}", e);
                }
            }

            if start.elapsed() >= timeout {
                let elapsed = start.elapsed();
                return Err(FeedbackError::DetectionTimeout(
                    (elapsed.as_millis() / poll_interval.as_millis()) as u32
                ));
            }
            thread::sleep(poll_interval);
        }
    }

    pub fn wait_for_chat_close(&mut self) -> Result<()> {
        if !self.is_enabled() {
            // Fallback to fixed delay
            thread::sleep(Duration::from_millis(250));
            return Ok(());
        }

        let start = Instant::now();
        let poll_interval = Duration::from_millis(50); // Simple 200ms polling
        let timeout = Duration::from_secs(1); // 2 second timeout

        loop {
            match self.detect_chat_state() {
                Ok(ChatState::Closed) => {
                    let elapsed = start.elapsed();
                    println!("✓ Chat closed (detected in {:?})", elapsed);
                    return Ok(());
                }
                Ok(_) => {
                    // Not closed yet
                }
                Err(e) => {
                    eprintln!("⚠ Detection error: {}", e);
                }
            }

            if start.elapsed() >= timeout {
                let elapsed = start.elapsed();
                return Err(FeedbackError::DetectionTimeout(
                    (elapsed.as_millis() / poll_interval.as_millis()) as u32
                ));
            }

            // Simple polling every 200ms
            thread::sleep(poll_interval);
        }
    }

    pub fn read_command_response(&mut self) -> Result<CommandResult> {
        // OCR functionality removed due to Xcode dependency issues
        // Currently just returns Unknown (assumes success)
        // TODO: Add OCR when Xcode is available or find alternative OCR library

        // Wait a bit for the command to execute
        thread::sleep(Duration::from_millis(100));

        Ok(CommandResult::Unknown)
    }


    pub fn set_chat_region(&mut self, x: u32, y: u32, width: u32, height: u32) {
        self.chat_region = (x, y, width, height);
    }

    pub fn set_response_region(&mut self, x: u32, y: u32, width: u32, height: u32) {
        self.response_region = (x, y, width, height);
    }

    /// Capture and save a screenshot showing the detection regions
    pub fn show_detection_regions(&mut self) -> Result<()> {

        if !self.is_enabled() {
            println!("⚠ Screen capture not available, cannot show detection regions");
            return Ok(());
        }

        let screenshot = self.capture_screen()?;
        let mut img = screenshot.to_rgba8();

        // Draw red rectangle for chat detection region
        let (chat_x, chat_y, chat_w, chat_h) = self.chat_region;
        self.draw_rectangle(&mut img, chat_x, chat_y, chat_w, chat_h, Rgba([255, 0, 0, 255]));

        // Draw blue rectangle for response detection region
        let (resp_x, resp_y, resp_w, resp_h) = self.response_region;
        self.draw_rectangle(&mut img, resp_x, resp_y, resp_w, resp_h, Rgba([0, 0, 255, 255]));

        // Save to file
        let output_path = "/tmp/mc_detection_regions.png";
        img.save(output_path)
            .map_err(|e| FeedbackError::CaptureFailed(format!("Failed to save image: {}", e)))?;

        println!("📸 Detection regions screenshot saved to: {}", output_path);
        println!("   🔴 Red box = Chat detection area (bottom-left)");
        println!("   🔵 Blue box = Response detection area");
        println!("   Open the image to verify the regions are correct for your screen");

        Ok(())
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
    pub fn show_live_preview(&mut self, seconds: u32) -> Result<()> {
        if !self.is_enabled() {
            println!("⚠ Screen capture not available");
            return Ok(());
        }

        println!("📹 Live preview: Capturing detection regions every second...");
        println!("   🔴 Red box = Chat detection area");
        println!("   🔵 Blue box = Response detection area");
        println!("   Position your Minecraft window in the bottom-left corner!");
        println!();

        for i in 0..seconds {
            // Capture and annotate
            let screenshot = self.capture_screen()?;
            let mut img = screenshot.to_rgba8();

            // Draw colored rectangles with filled semi-transparent overlay
            let (chat_x, chat_y, chat_w, chat_h) = self.chat_region;
            self.draw_filled_region(&mut img, chat_x, chat_y, chat_w, chat_h, Rgba([255, 0, 0, 60]));
            self.draw_rectangle(&mut img, chat_x, chat_y, chat_w, chat_h, Rgba([255, 0, 0, 255]));

            let (resp_x, resp_y, resp_w, resp_h) = self.response_region;
            self.draw_filled_region(&mut img, resp_x, resp_y, resp_w, resp_h, Rgba([0, 0, 255, 60]));
            self.draw_rectangle(&mut img, resp_x, resp_y, resp_w, resp_h, Rgba([0, 0, 255, 255]));

            // Save preview
            let output_path = format!("/tmp/mc_preview_{}.png", i);
            img.save(&output_path)
                .map_err(|e| FeedbackError::CaptureFailed(format!("Failed to save preview: {}", e)))?;

            println!("   [{}s] Preview saved: {}", seconds - i, output_path);

            if i < seconds - 1 {
                thread::sleep(Duration::from_secs(1));
            }
        }

        println!();
        println!("✅ Preview complete! Last capture saved to /tmp/mc_preview_{}.png", seconds - 1);
        println!("   Open this file to verify the regions are positioned correctly");
        println!();

        Ok(())
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

impl Default for FeedbackDetector {
    fn default() -> Self {
        Self::new().unwrap_or_else(|_| Self {
            capturer: None,
            width: 1920,
            height: 1080,
            retry_config: RetryConfig::default(),
            chat_region: (0, 830, 800, 250),  // Bottom-left for 1920x1080
            response_region: (0, 730, 800, 350),  // Slightly higher
        })
    }
}
