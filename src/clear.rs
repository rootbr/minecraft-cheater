use std::sync::{Arc, Mutex};
use crate::commands::{apply_offset, BoundingBox};
use crate::config::{Offset, CHUNK_SIZE};
use crate::executor::CommandExecutor;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

pub fn generate_clear_commands(bbox: BoundingBox) -> Vec<String> {
    let mut commands = Vec::new();
    let (min_x, min_y, min_z) = bbox.min;
    let (max_x, max_y, max_z) = bbox.max;

    let mut x = min_x;
    while x <= max_x {
        let x_end = (x + CHUNK_SIZE - 1).min(max_x);

        let mut y = min_y;
        while y <= max_y {
            let y_end = (y + CHUNK_SIZE - 1).min(max_y);

            let mut z = min_z;
            while z <= max_z {
                let z_end = (z + CHUNK_SIZE - 1).min(max_z);

                commands.push(format!(
                    "/fill {} {} {} {} {} {} air",
                    x, y, z, x_end, y_end, z_end
                ));

                z = z_end + 1;
            }
            y = y_end + 1;
        }
        x = x_end + 1;
    }

    commands
}

pub fn execute_clear(
    executor: &mut CommandExecutor,
    bbox: BoundingBox,
    offset: Offset,
    logs: Option<&Arc<Mutex<Vec<String>>>>,
    stop_flag: Option<&Arc<Mutex<bool>>>,
) -> Result<()> {
    let clear_commands = generate_clear_commands(bbox);
    let size = bbox.size();

    let msg = format!(
        "=== Clearing area: {}x{}x{} ({} blocks), {} commands ===",
        size.0, size.1, size.2, bbox.total_blocks(), clear_commands.len()
    );
    
    println!("{}", msg);
    if let Some(l) = logs {
        l.lock().unwrap().push(msg);
    }

    for (i, command) in clear_commands.iter().enumerate() {
        if let Some(stop) = stop_flag {
            if *stop.lock().unwrap() {
                let stop_msg = format!("Clearing stopped at {}/{}", i, clear_commands.len());
                println!("{}", stop_msg);
                if let Some(l) = logs {
                    l.lock().unwrap().push(stop_msg);
                }
                break;
            }
        }

        let cmd = apply_offset(command, offset);
        let stats = executor.execute(&cmd, stop_flag)?;
        
        if let Some(s) = stats {
            let log_line = format!(
                "[clear {}/{}] {} ({}ms {}/{}/{} iterations)",
                i + 1,
                clear_commands.len(),
                cmd,
                s.total_time.as_millis(),
                s.iterations[0],
                s.iterations[1],
                s.iterations[2]
            );
            println!("{}", log_line);
            if let Some(l) = logs {
                l.lock().unwrap().push(log_line);
            }
        } else {
            let log_line = format!("[clear {}/{}] {} (Skipped)", i + 1, clear_commands.len(), cmd);
            println!("{}", log_line);
            if let Some(l) = logs {
                l.lock().unwrap().push(log_line);
            }
        }
    }
    
    let done_msg = "Clearing phase finished!".to_string();
    println!("{}", done_msg);
    if let Some(l) = logs {
        l.lock().unwrap().push(done_msg);
    }

    Ok(())
}
