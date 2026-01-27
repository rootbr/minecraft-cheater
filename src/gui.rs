use eframe::egui;
use std::sync::{Arc, Mutex};
use std::thread;

use crate::clear::execute_clear;
use crate::commands::{apply_offset, find_bounding_box, load_from_file};
use crate::config::{Config, CoordinatesConfig, ExecutionConfig, Offset, ScreenRegionsConfig};
use crate::executor::CommandExecutor;
use crate::staircase;
use crate::url_handler;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Clone, PartialEq)]
enum ExecutionMode {
    FromFile,
    Staircase,
    DetectionAreas,
}

#[derive(Clone)]
enum ExecutionState {
    Idle,
    Running,
    Completed,
    Failed,
    Stopped,
}

pub struct McCommanderApp {
    execution_mode: ExecutionMode,
    execution_url: String,
    skip_commands: String,
    material_filter: String,

    offset_x: String,
    offset_y: String,
    offset_z: String,

    screen_regions: ScreenRegionsConfig,

    // String representations for UI editing
    panel_x: String,
    panel_y: String,
    panel_width: String,
    panel_height: String,

    health_x: String,
    health_y: String,
    health_width: String,
    health_height: String,

    command_x: String,
    command_y: String,
    command_width: String,
    command_height: String,

    logs: Arc<Mutex<Vec<String>>>,
    execution_state: Arc<Mutex<ExecutionState>>,
    stop_flag: Arc<Mutex<bool>>,
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

            panel_x: config.screen_regions.panel_region.x.to_string(),
            panel_y: config.screen_regions.panel_region.y.to_string(),
            panel_width: config.screen_regions.panel_region.width.to_string(),
            panel_height: config.screen_regions.panel_region.height.to_string(),

            health_x: config.screen_regions.health_region.x.to_string(),
            health_y: config.screen_regions.health_region.y.to_string(),
            health_width: config.screen_regions.health_region.width.to_string(),
            health_height: config.screen_regions.health_region.height.to_string(),

            command_x: config.screen_regions.command_region.x.to_string(),
            command_y: config.screen_regions.command_region.y.to_string(),
            command_width: config.screen_regions.command_region.width.to_string(),
            command_height: config.screen_regions.command_region.height.to_string(),

            screen_regions: config.screen_regions,
            logs: Arc::new(Mutex::new(Vec::new())),
            execution_state: Arc::new(Mutex::new(ExecutionState::Idle)),
            stop_flag: Arc::new(Mutex::new(false)),
            scroll_to_bottom: false,
        }
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            execution: ExecutionConfig::default(),
            coordinates: CoordinatesConfig::default(),
            screen_regions: ScreenRegionsConfig::default(),
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

    fn update_screen_regions(&mut self) {
        use crate::config::ScreenRegion;

        self.screen_regions.panel_region = ScreenRegion {
            x: self.panel_x.parse().unwrap_or(75),
            y: self.panel_y.parse().unwrap_or(645),
            width: self.panel_width.parse().unwrap_or(75),
            height: self.panel_height.parse().unwrap_or(30),
        };

        self.screen_regions.health_region = ScreenRegion {
            x: self.health_x.parse().unwrap_or(450),
            y: self.health_y.parse().unwrap_or(1360),
            width: self.health_width.parse().unwrap_or(200),
            height: self.health_height.parse().unwrap_or(20),
        };

        self.screen_regions.command_region = ScreenRegion {
            x: self.command_x.parse().unwrap_or(1250),
            y: self.command_y.parse().unwrap_or(1392),
            width: self.command_width.parse().unwrap_or(15),
            height: self.command_height.parse().unwrap_or(40),
        };
    }

    fn auto_save(&mut self) {
        self.update_screen_regions();

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
            screen_regions: self.screen_regions.clone(),
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
        *self.stop_flag.lock().unwrap() = false;
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
            screen_regions: self.screen_regions.clone(),
        };

        let mode = self.execution_mode.clone();
        let logs = Arc::clone(&self.logs);
        let state = Arc::clone(&self.execution_state);
        let stop_flag = Arc::clone(&self.stop_flag);

        thread::spawn(move || {
            let result = match mode {
                ExecutionMode::FromFile => execute_from_file(&config, &logs, &stop_flag),
                ExecutionMode::Staircase => execute_staircase(&config, &logs, &stop_flag),
                ExecutionMode::DetectionAreas => {
                    logs.lock()
                        .unwrap()
                        .push("Detection Areas mode does not execute commands.".to_string());
                    logs.lock()
                        .unwrap()
                        .push("Use 'Show Detection Areas' button to preview regions.".to_string());
                    Ok(())
                }
            };

            let mut execution_state = state.lock().unwrap();
            match result {
                Ok(_) => {
                    if *stop_flag.lock().unwrap() {
                        logs.lock()
                            .unwrap()
                            .push("Execution stopped by user.".to_string());
                        *execution_state = ExecutionState::Stopped;
                    } else {
                        logs.lock()
                            .unwrap()
                            .push("Execution completed successfully!".to_string());
                        *execution_state = ExecutionState::Completed;
                    }
                }
                Err(e) => {
                    logs.lock()
                        .unwrap()
                        .push(format!("Execution failed: {}", e));
                    *execution_state = ExecutionState::Failed;
                }
            }
        });
    }

    fn stop_execution(&mut self) {
        *self.stop_flag.lock().unwrap() = true;
        self.add_log("Stop requested, waiting for current command to finish...".to_string());
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
            match url_handler::ensure_commands_exist_with_logs(&url, Some(Arc::clone(&logs)), true)
            {
                Ok(path) => {
                    logs.lock().unwrap().push(String::new());
                    logs.lock()
                        .unwrap()
                        .push(format!("✓ Commands loaded: {}", path.display()));
                }
                Err(e) => {
                    logs.lock().unwrap().push(String::new());
                    logs.lock()
                        .unwrap()
                        .push(format!("✗ Failed to load from URL: {}", e));
                }
            }
        });
    }

    fn show_detection_areas(&mut self) {
        self.add_log("Showing detection areas...".to_string());

        let logs = Arc::clone(&self.logs);
        let screen_regions = self.screen_regions.clone();
        thread::spawn(
            move || match CommandExecutor::with_config(&screen_regions) {
                Ok(mut executor) => {
                    logs.lock()
                        .unwrap()
                        .push("Opening detection areas preview...".to_string());
                    if let Err(e) = executor.show_detection_preview() {
                        logs.lock()
                            .unwrap()
                            .push(format!("Error showing preview: {}", e));
                    }
                }
                Err(e) => {
                    logs.lock()
                        .unwrap()
                        .push(format!("Failed to create executor: {}", e));
                }
            },
        );
    }
}

impl eframe::App for McCommanderApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        ctx.request_repaint();

        egui::CentralPanel::default().show(ctx, |ui| {
            let mut changed = false;

            ui.horizontal(|ui| {
                ui.label("Execution Mode:");
                ui.selectable_value(
                    &mut self.execution_mode,
                    ExecutionMode::FromFile,
                    "From File",
                );
                ui.selectable_value(
                    &mut self.execution_mode,
                    ExecutionMode::Staircase,
                    "Staircase Generator",
                );
                ui.selectable_value(
                    &mut self.execution_mode,
                    ExecutionMode::DetectionAreas,
                    "Detection Areas",
                );
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

            ui.horizontal(|ui| match self.execution_mode {
                ExecutionMode::FromFile => {
                    ui.group(|ui| {
                        ui.horizontal(|ui| {
                            ui.label("Skip commands:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.skip_commands)
                                        .desired_width(50.0),
                                )
                                .changed();
                        });
                        ui.horizontal(|ui| {
                            ui.label("Material filter:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.material_filter)
                                        .desired_width(100.0),
                                )
                                .changed();
                        });
                    });

                    ui.add_space(10.0);

                    ui.group(|ui| {
                        ui.horizontal(|ui| {
                            ui.label("X:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.offset_x)
                                        .desired_width(50.0),
                                )
                                .changed();
                            ui.label("Y:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.offset_y)
                                        .desired_width(50.0),
                                )
                                .changed();
                            ui.label("Z:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.offset_z)
                                        .desired_width(50.0),
                                )
                                .changed();
                        });
                    });
                }
                ExecutionMode::Staircase => {
                    ui.group(|ui| {
                        ui.horizontal(|ui| {
                            ui.label("X:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.offset_x)
                                        .desired_width(50.0),
                                )
                                .changed();
                            ui.label("Y:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.offset_y)
                                        .desired_width(50.0),
                                )
                                .changed();
                            ui.label("Z:");
                            changed |= ui
                                .add(
                                    egui::TextEdit::singleline(&mut self.offset_z)
                                        .desired_width(50.0),
                                )
                                .changed();
                        });
                    });
                }
                ExecutionMode::DetectionAreas => {
                    ui.vertical(|ui| {
                        ui.group(|ui| {
                            ui.label("Panel Region (Blue):");
                            ui.horizontal(|ui| {
                                ui.label("X:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.panel_x)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Y:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.panel_y)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Width:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.panel_width)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Height:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.panel_height)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                            });
                        });

                        ui.add_space(5.0);

                        ui.group(|ui| {
                            ui.label("Health Region (Red - Closed State):");
                            ui.horizontal(|ui| {
                                ui.label("X:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.health_x)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Y:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.health_y)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Width:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.health_width)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Height:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.health_height)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                            });
                        });

                        ui.add_space(5.0);

                        ui.group(|ui| {
                            ui.label("Command Region (Yellow - Input Area):");
                            ui.horizontal(|ui| {
                                ui.label("X:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.command_x)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Y:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.command_y)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Width:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.command_width)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                                ui.label("Height:");
                                changed |= ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.command_height)
                                            .desired_width(60.0),
                                    )
                                    .changed();
                            });
                        });
                    });
                }
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

                let stop_button = ui.add_enabled(is_running, egui::Button::new("Stop"));
                if stop_button.clicked() {
                    self.stop_execution();
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
                    ExecutionState::Stopped => {
                        ui.colored_label(egui::Color32::YELLOW, "⏹ Stopped");
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

fn execute_from_file(
    config: &Config,
    logs: &Arc<Mutex<Vec<String>>>,
    stop_flag: &Arc<Mutex<bool>>,
) -> Result<()> {
    logs.lock().unwrap().push(format!(
        "Loading commands from URL: {}",
        config.execution.url
    ));

    let file_path = url_handler::ensure_commands_exist_with_logs(
        &config.execution.url,
        Some(Arc::clone(logs)),
        false,
    )?;
    logs.lock().unwrap().push(String::new());
    logs.lock()
        .unwrap()
        .push(format!("Reading commands from: {}", file_path.display()));

    let commands = load_from_file(&file_path.to_string_lossy())?;
    execute_commands(config, commands, logs, stop_flag)
}

fn execute_staircase(
    config: &Config,
    logs: &Arc<Mutex<Vec<String>>>,
    stop_flag: &Arc<Mutex<bool>>,
) -> Result<()> {
    logs.lock()
        .unwrap()
        .push("Generating staircase commands...".to_string());
    let commands = staircase::generate_commands();
    execute_commands(config, commands, logs, stop_flag)
}

fn execute_commands(
    config: &Config,
    commands: Vec<String>,
    logs: &Arc<Mutex<Vec<String>>>,
    stop_flag: &Arc<Mutex<bool>>,
) -> Result<()> {
    let offset = config.offset();

    let clear_bbox = if config.execution.skip == 0 {
        find_bounding_box(&commands)
    } else {
        None
    };

    let commands = apply_skip(commands, config.execution.skip);
    let commands = apply_material_filter(commands, &config.execution.material);

    if commands.is_empty() {
        logs.lock()
            .unwrap()
            .push("No commands to execute after filtering".to_string());
        return Ok(());
    }

    logs.lock()
        .unwrap()
        .push(format!("Total commands to execute: {}", commands.len()));
    logs.lock()
        .unwrap()
        .push("Activating Minecraft window...".to_string());

    let mut executor = CommandExecutor::with_config(&config.screen_regions)?;
    executor.activate_minecraft_window()?;

    if config.execution.skip == 0 && config.execution.material.is_none() {
        if let Some(bbox) = clear_bbox {
            logs.lock()
                .unwrap()
                .push("Clearing build area...".to_string());
            execute_clear(&mut executor, bbox, offset)?;
            logs.lock()
                .unwrap()
                .push("Preparing for build phase...".to_string());
            std::thread::sleep(std::time::Duration::from_millis(500));
        }
    }

    execute_build_phase(
        &mut executor,
        &commands,
        offset,
        config.execution.skip,
        logs,
        stop_flag,
    )?;
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
        Some(filter) => commands
            .into_iter()
            .filter(|cmd| cmd.contains(filter))
            .collect(),
        None => commands,
    }
}

fn execute_build_phase(
    executor: &mut CommandExecutor,
    commands: &[String],
    offset: Offset,
    skip_count: usize,
    logs: &Arc<Mutex<Vec<String>>>,
    stop_flag: &Arc<Mutex<bool>>,
) -> Result<()> {
    let total = skip_count + commands.len();

    if skip_count == 0 {
        logs.lock()
            .unwrap()
            .push("Waiting for system to stabilize...".to_string());
        std::thread::sleep(std::time::Duration::from_millis(500));
    }

    for (i, command) in commands.iter().enumerate() {
        if *stop_flag.lock().unwrap() {
            logs.lock()
                .unwrap()
                .push(format!("Stopped at command {}/{}", skip_count + i, total));
            break;
        }

        let cmd = apply_offset(command, offset);
        let stats = executor.execute(&cmd)?;

        let log_msg = if let Some(s) = stats {
            format!(
                "[{}/{}] {} ({}ms {}/{}/{} iterations)",
                skip_count + i + 1,
                total,
                cmd,
                s.total_time.as_millis(),
                s.iterations[0],
                s.iterations[1],
                s.iterations[2]
            )
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
