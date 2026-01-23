use eframe::egui;
use std::sync::{Arc, Mutex};
use std::thread;

use crate::clear::execute_clear;
use crate::commands::{apply_offset, find_bounding_box, load_from_file};
use crate::config::{Config, CoordinatesConfig, ExecutionConfig, Offset};
use crate::executor::CommandExecutor;
use crate::staircase;
use crate::url_handler;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Clone, PartialEq)]
enum ExecutionMode {
    FromFile,
    Staircase,
}

#[derive(Clone)]
enum ExecutionState {
    Idle,
    Running,
    Completed,
    Failed,
}

pub struct McCommanderApp {
    execution_mode: ExecutionMode,
    execution_url: String,
    skip_commands: String,
    material_filter: String,

    offset_x: String,
    offset_y: String,
    offset_z: String,

    logs: Arc<Mutex<Vec<String>>>,
    execution_state: Arc<Mutex<ExecutionState>>,
    scroll_to_bottom: bool,
}

impl Default for McCommanderApp {
    fn default() -> Self {
        let config = match Config::from_file("config.toml") {
            Ok(config) => config,
            Err(_) => {
                let default_config = Config::default();
                let _ = Self::save_config_to_file(&default_config);
                default_config
            }
        };

        Self {
            execution_mode: ExecutionMode::FromFile,
            execution_url: config.execution.url,
            skip_commands: config.execution.skip.to_string(),
            material_filter: config.execution.material.unwrap_or_default(),
            offset_x: config.coordinates.offset_x.to_string(),
            offset_y: config.coordinates.offset_y.to_string(),
            offset_z: config.coordinates.offset_z.to_string(),
            logs: Arc::new(Mutex::new(Vec::new())),
            execution_state: Arc::new(Mutex::new(ExecutionState::Idle)),
            scroll_to_bottom: false,
        }
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            execution: ExecutionConfig::default(),
            coordinates: CoordinatesConfig::default(),
        }
    }
}

impl McCommanderApp {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        Self::default()
    }

    fn add_log(&mut self, message: String) {
        if let Ok(mut logs) = self.logs.lock() {
            logs.push(message);
            self.scroll_to_bottom = true;
        }
    }

    fn clear_logs(&mut self) {
        if let Ok(mut logs) = self.logs.lock() {
            logs.clear();
        }
    }

    fn save_config_to_file(config: &Config) -> std::result::Result<(), Box<dyn std::error::Error>> {
        let toml_string = toml::to_string_pretty(config)?;
        std::fs::write("config.toml", toml_string)?;
        Ok(())
    }

    fn auto_save(&self) {
        let config = Config {
            execution: ExecutionConfig {
                url: self.execution_url.clone(),
                skip: self.skip_commands.parse().unwrap_or(0),
                material: if self.material_filter.is_empty() {
                    None
                } else {
                    Some(self.material_filter.clone())
                },
            },
            coordinates: CoordinatesConfig {
                offset_x: self.offset_x.parse().unwrap_or(0),
                offset_y: self.offset_y.parse().unwrap_or(0),
                offset_z: self.offset_z.parse().unwrap_or(0),
            },
        };

        let _ = Self::save_config_to_file(&config);
    }

    fn start_execution(&mut self) {
        let state = self.execution_state.lock().unwrap();
        if matches!(*state, ExecutionState::Running) {
            return;
        }
        drop(state);

        *self.execution_state.lock().unwrap() = ExecutionState::Running;
        self.clear_logs();
        self.add_log("Starting execution...".to_string());

        let config = Config {
            execution: ExecutionConfig {
                url: self.execution_url.clone(),
                skip: self.skip_commands.parse().unwrap_or(0),
                material: if self.material_filter.is_empty() {
                    None
                } else {
                    Some(self.material_filter.clone())
                },
            },
            coordinates: CoordinatesConfig {
                offset_x: self.offset_x.parse().unwrap_or(0),
                offset_y: self.offset_y.parse().unwrap_or(0),
                offset_z: self.offset_z.parse().unwrap_or(0),
            },
        };

        let mode = self.execution_mode.clone();
        let logs = Arc::clone(&self.logs);
        let state = Arc::clone(&self.execution_state);

        thread::spawn(move || {
            let result = match mode {
                ExecutionMode::FromFile => execute_from_file(&config, &logs),
                ExecutionMode::Staircase => execute_staircase(&config, &logs),
            };

            let mut execution_state = state.lock().unwrap();
            match result {
                Ok(_) => {
                    logs.lock().unwrap().push("Execution completed successfully!".to_string());
                    *execution_state = ExecutionState::Completed;
                }
                Err(e) => {
                    logs.lock().unwrap().push(format!("Execution failed: {}", e));
                    *execution_state = ExecutionState::Failed;
                }
            }
        });
    }

    fn load_from_url(&mut self) {
        if self.execution_url.is_empty() {
            self.add_log("Error: URL is empty".to_string());
            return;
        }
        self.clear_logs();
        self.add_log(format!("Loading from URL: {}", self.execution_url));
        self.add_log(String::new());

        let url = self.execution_url.clone();
        let logs = Arc::clone(&self.logs);

        thread::spawn(move || {
            match url_handler::ensure_commands_exist_with_logs(&url, Some(Arc::clone(&logs)), true) {
                Ok(path) => {
                    logs.lock().unwrap().push(String::new());
                    logs.lock().unwrap().push(format!("✓ Commands loaded: {}", path.display()));
                }
                Err(e) => {
                    logs.lock().unwrap().push(String::new());
                    logs.lock().unwrap().push(format!("✗ Failed to load from URL: {}", e));
                }
            }
        });
    }

    fn show_detection_areas(&mut self) {
        self.add_log("Showing detection areas...".to_string());

        let logs = Arc::clone(&self.logs);
        thread::spawn(move || {
            match CommandExecutor::new() {
                Ok(mut executor) => {
                    logs.lock().unwrap().push("Opening detection areas preview...".to_string());
                    if let Err(e) = executor.show_detection_preview() {
                        logs.lock().unwrap().push(format!("Error showing preview: {}", e));
                    }
                }
                Err(e) => {
                    logs.lock().unwrap().push(format!("Failed to create executor: {}", e));
                }
            }
        });
    }
}

impl eframe::App for McCommanderApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        ctx.request_repaint();

        egui::CentralPanel::default().show(ctx, |ui| {
            let mut changed = false;

            ui.horizontal(|ui| {
                ui.label("Execution Mode:");
                ui.selectable_value(&mut self.execution_mode, ExecutionMode::FromFile, "From File");
                ui.selectable_value(&mut self.execution_mode, ExecutionMode::Staircase, "Staircase Generator");
            });

            ui.add_space(10.0);
            ui.separator();
            ui.add_space(10.0);

            ui.horizontal(|ui| {
                ui.label("URL:");
                let available_width = ui.available_width() - 110.0;
                let text_edit = egui::TextEdit::singleline(&mut self.execution_url)
                    .desired_width(available_width);
                changed |= ui.add(text_edit).changed();
                if ui.button("Load").clicked() {
                    self.load_from_url();
                }
                if ui.button("Open").clicked() {
                    let url = self.execution_url.trim();
                    if !url.is_empty() {
                        ctx.open_url(egui::OpenUrl::new_tab(url));
                    }
                }
            });

            ui.add_space(10.0);
            ui.separator();
            ui.add_space(10.0);

            ui.horizontal(|ui| {
                if self.execution_mode == ExecutionMode::FromFile {
                    ui.group(|ui| {
                        ui.horizontal(|ui| {
                            ui.label("Skip commands:");
                            changed |= ui.add(egui::TextEdit::singleline(&mut self.skip_commands)
                                .desired_width(50.0)).changed();
                        });
                        ui.horizontal(|ui| {
                            ui.label("Material filter:");
                            changed |= ui.add(egui::TextEdit::singleline(&mut self.material_filter)
                                .desired_width(100.0)).changed();
                        });
                    });

                    ui.add_space(10.0);
                }

                ui.group(|ui| {
                    ui.horizontal(|ui| {
                        ui.label("X:");
                        changed |= ui.add(egui::TextEdit::singleline(&mut self.offset_x)
                            .desired_width(50.0)).changed();
                        ui.label("Y:");
                        changed |= ui.add(egui::TextEdit::singleline(&mut self.offset_y)
                            .desired_width(50.0)).changed();
                        ui.label("Z:");
                        changed |= ui.add(egui::TextEdit::singleline(&mut self.offset_z)
                            .desired_width(50.0)).changed();
                    });
                });
            });

            ui.add_space(10.0);

            if changed {
                self.auto_save();
            }

            ui.add_space(10.0);
            ui.separator();
            ui.add_space(10.0);

            let state = self.execution_state.lock().unwrap().clone();
            let is_running = matches!(state, ExecutionState::Running);

            ui.horizontal(|ui| {
                let button = ui.add_enabled(!is_running, egui::Button::new("Start Execution"));
                if button.clicked() {
                    self.start_execution();
                }

                if ui.button("Show Detection Areas").clicked() {
                    self.show_detection_areas();
                }

                match state {
                    ExecutionState::Idle => {}
                    ExecutionState::Running => {
                        ui.spinner();
                        ui.label("Running...");
                    }
                    ExecutionState::Completed => {
                        ui.colored_label(egui::Color32::GREEN, "✓ Completed");
                    }
                    ExecutionState::Failed => {
                        ui.colored_label(egui::Color32::RED, "✗ Failed");
                    }
                }
            });

            ui.add_space(10.0);

            ui.label("Logs:");
            let text_height = ui.available_height();

            egui::ScrollArea::vertical()
                .id_salt("logs_scroll")
                .max_height(text_height)
                .stick_to_bottom(true)
                .auto_shrink([false, false])
                .show(ui, |ui| {
                    if let Ok(logs) = self.logs.lock() {
                        for log in logs.iter() {
                            ui.label(log);
                        }
                    }
                });
        });
    }
}

fn execute_from_file(config: &Config, logs: &Arc<Mutex<Vec<String>>>) -> Result<()> {
    logs.lock().unwrap().push(format!("Loading commands from URL: {}", config.execution.url));

    let file_path = url_handler::ensure_commands_exist_with_logs(&config.execution.url, Some(Arc::clone(logs)), false)?;
    logs.lock().unwrap().push(String::new());
    logs.lock().unwrap().push(format!("Reading commands from: {}", file_path.display()));

    let commands = load_from_file(&file_path.to_string_lossy())?;
    execute_commands(config, commands, logs)
}

fn execute_staircase(config: &Config, logs: &Arc<Mutex<Vec<String>>>) -> Result<()> {
    logs.lock().unwrap().push("Generating staircase commands...".to_string());
    let commands = staircase::generate_commands();
    execute_commands(config, commands, logs)
}

fn execute_commands(config: &Config, commands: Vec<String>, logs: &Arc<Mutex<Vec<String>>>) -> Result<()> {
    let offset = config.offset();

    let clear_bbox = if config.execution.skip == 0 {
        find_bounding_box(&commands)
    } else {
        None
    };

    let commands = apply_skip(commands, config.execution.skip);
    let commands = apply_material_filter(commands, &config.execution.material);

    if commands.is_empty() {
        logs.lock().unwrap().push("No commands to execute after filtering".to_string());
        return Ok(());
    }

    logs.lock().unwrap().push(format!("Total commands to execute: {}", commands.len()));
    logs.lock().unwrap().push("Activating Minecraft window...".to_string());

    let mut executor = CommandExecutor::new()?;
    executor.activate_minecraft_window()?;

    if config.execution.skip == 0 && config.execution.material.is_none() {
        if let Some(bbox) = clear_bbox {
            logs.lock().unwrap().push("Clearing build area...".to_string());
            execute_clear(&mut executor, bbox, offset)?;
            logs.lock().unwrap().push("Preparing for build phase...".to_string());
            std::thread::sleep(std::time::Duration::from_millis(500));
        }
    }

    execute_build_phase(&mut executor, &commands, offset, config.execution.skip, logs)?;
    Ok(())
}

fn apply_skip(commands: Vec<String>, skip: usize) -> Vec<String> {
    if skip == 0 {
        return commands;
    }
    if skip >= commands.len() {
        return Vec::new();
    }
    commands.into_iter().skip(skip).collect()
}

fn apply_material_filter(commands: Vec<String>, material: &Option<String>) -> Vec<String> {
    match material {
        Some(filter) => {
            commands
                .into_iter()
                .filter(|cmd| cmd.contains(filter))
                .collect()
        }
        None => commands,
    }
}

fn execute_build_phase(
    executor: &mut CommandExecutor,
    commands: &[String],
    offset: Offset,
    skip_count: usize,
    logs: &Arc<Mutex<Vec<String>>>,
) -> Result<()> {
    let total = skip_count + commands.len();

    if skip_count == 0 {
        logs.lock().unwrap().push("Waiting for system to stabilize...".to_string());
        std::thread::sleep(std::time::Duration::from_millis(500));
    }

    for (i, command) in commands.iter().enumerate() {
        let cmd = apply_offset(command, offset);
        let stats = executor.execute(&cmd)?;

        let log_msg = if let Some(s) = stats {
            format!("[{}/{}] {} ({}ms {}/{}/{} iterations)",
                skip_count + i + 1, total, cmd,
                s.total_time.as_millis(),
                s.iterations[0], s.iterations[1], s.iterations[2])
        } else {
            format!("[{}/{}] {}", skip_count + i + 1, total, cmd)
        };

        logs.lock().unwrap().push(log_msg);
    }
    Ok(())
}

pub fn run_gui() -> Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([800.0, 550.0])
            .with_min_inner_size([600.0, 400.0])
            .with_position([0.0, 0.0]),
        ..Default::default()
    };

    eframe::run_native(
        "MC Commander",
        options,
        Box::new(|cc| Ok(Box::new(McCommanderApp::new(cc)))),
    )
    .map_err(|e| format!("Failed to run GUI: {}", e).into())
}
