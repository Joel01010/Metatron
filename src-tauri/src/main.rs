use serde_json::{json, Value};
use std::{
    env,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, ChildStdout, Command, Stdio},
    sync::{atomic::{AtomicU64, Ordering}, Mutex},
};
use tauri::{LogicalSize, Manager, State};

struct BackendProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

impl BackendProcess {
    fn request(&mut self, id: u64, cmd: &str, params: Value) -> Result<Value, String> {
        let req = json!({"id": id, "cmd": cmd, "params": params});
        writeln!(self.stdin, "{}", req).map_err(|e| format!("backend write failed: {e}"))?;
        self.stdin.flush().map_err(|e| format!("backend flush failed: {e}"))?;
        let mut line = String::new();
        self.stdout.read_line(&mut line).map_err(|e| format!("backend read failed: {e}"))?;
        if line.trim().is_empty() { return Err("backend exited without a response".into()); }
        let value: Value = serde_json::from_str(&line).map_err(|e| format!("invalid backend JSON: {e}"))?;
        if value.get("ok").and_then(Value::as_bool) == Some(true) {
            Ok(value.get("result").cloned().unwrap_or(Value::Null))
        } else {
            let msg = value.pointer("/error/message").and_then(Value::as_str).unwrap_or("backend error");
            Err(msg.to_string())
        }
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); }
}

struct BackendState {
    process: Mutex<BackendProcess>,
    next_id: AtomicU64,
}

fn dev_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap_or_else(|| Path::new(".")).to_path_buf()
}

fn spawn_backend(app: &tauri::AppHandle) -> Result<BackendProcess, String> {
    let override_cmd = env::var("METATRON_BACKEND_CMD").ok();
    let mut command = if let Some(raw) = override_cmd {
        let mut parts = raw.split_whitespace();
        let exe = parts.next().ok_or("METATRON_BACKEND_CMD is empty")?;
        let mut c = Command::new(exe); c.args(parts); c
    } else if cfg!(debug_assertions) {
        let python = env::var("METATRON_PYTHON").unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() });
        let mut c = Command::new(python); c.args(["-m", "metatron.main"]); c.current_dir(dev_root()); c
    } else {
        let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
        let exe = if cfg!(windows) { resource_dir.join("resources/metatron-backend.exe") } else { resource_dir.join("resources/metatron-backend") };
        let mut c = Command::new(exe); c
    };
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::inherit());
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let mut child = command.spawn().map_err(|e| format!("failed to start Metatron backend: {e}"))?;
    let stdin = child.stdin.take().ok_or("backend stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("backend stdout unavailable")?;
    Ok(BackendProcess { child, stdin, stdout: BufReader::new(stdout) })
}

#[tauri::command]
fn backend_command(state: State<'_, BackendState>, cmd: String, params: Value) -> Result<Value, String> {
    let id = state.next_id.fetch_add(1, Ordering::Relaxed);
    let mut proc = state.process.lock().map_err(|_| "backend lock poisoned".to_string())?;
    proc.request(id, &cmd, params)
}


#[tauri::command]
fn window_command(app: tauri::AppHandle, action: String, value: Value) -> Result<(), String> {
    let orb = app.get_webview_window("orb").ok_or("orb window not found")?;
    match action.as_str() {
        "orb.show" => orb.show().map_err(|e| e.to_string())?,
        "orb.hide" => orb.hide().map_err(|e| e.to_string())?,
        "orb.always_on_top" => orb.set_always_on_top(value.as_bool().unwrap_or(true)).map_err(|e| e.to_string())?,
        "orb.scale" => {
            let scale = value.as_f64().unwrap_or(1.0).clamp(0.5, 2.0);
            let size = 360.0 * scale;
            orb.set_size(LogicalSize::new(size, size)).map_err(|e| e.to_string())?;
        },
        "main.show" => {
            let main = app.get_webview_window("main").ok_or("main window not found")?;
            main.show().map_err(|e| e.to_string())?;
            main.set_focus().map_err(|e| e.to_string())?;
        },
        "main.hide" => {
            let main = app.get_webview_window("main").ok_or("main window not found")?;
            main.hide().map_err(|e| e.to_string())?;
        },
        _ => return Err(format!("unknown window action {action}")),
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let backend = spawn_backend(&app.handle()).map_err(std::io::Error::other)?;
            app.manage(BackendState { process: Mutex::new(backend), next_id: AtomicU64::new(1) });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_command, window_command])
        .run(tauri::generate_context!())
        .expect("error while running Metatron");
}
