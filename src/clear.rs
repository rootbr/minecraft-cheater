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
) -> Result<()> {
    let clear_commands = generate_clear_commands(bbox);
    let size = bbox.size();

    println!("\n=== Очистка области ===");
    println!(
        "Размер: {}x{}x{} ({} блоков), {} команд",
        size.0, size.1, size.2, bbox.total_blocks(), clear_commands.len()
    );

    for (i, command) in clear_commands.iter().enumerate() {
        let cmd = apply_offset(command, offset);
        let stats = executor.execute(&cmd)?;
        print!("[clear {}/{}] {}", i + 1, clear_commands.len(), cmd);
        if let Some(s) = stats {
            println!(" ({}ms {}/{}/{} iterations)", 
                s.total_time.as_millis(), 
                s.iterations[0], s.iterations[1], s.iterations[2]);
        } else {
            println!();
        }
    }
    println!("Очистка завершена!\n");

    Ok(())
}
