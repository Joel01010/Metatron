use serde_json::{json, Value};
use std::{
    collections::HashMap,
    env,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        atomic::{AtomicU64, Ordering},
        mpsc,
        Arc, Mutex,
    },
    thread,
    time::Duration,
};
use tauri::{Emitter, LogicalSize, Manager, PhysicalPosition, State, WebviewWindow};


#[cfg(windows)]
struct BackendJob {
    handle: usize,
}

#[cfg(windows)]
impl BackendJob {
    fn create_and_assign(child: &Child) -> Result<Self, String> {
        use std::mem::{size_of, zeroed};
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Foundation::CloseHandle;
        use windows_sys::Win32::System::JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
            SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        };

        unsafe {
            let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if job.is_null() {
                return Err("CreateJobObjectW failed".into());
            }
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            ) == 0
            {
                CloseHandle(job);
                return Err("SetInformationJobObject failed".into());
            }
            let process = child.as_raw_handle() as windows_sys::Win32::Foundation::HANDLE;
            if AssignProcessToJobObject(job, process) == 0 {
                CloseHandle(job);
                return Err("AssignProcessToJobObject failed".into());
            }
            Ok(Self { handle: job as usize })
        }
    }
}

#[cfg(windows)]
impl Drop for BackendJob {
    fn drop(&mut self) {
        unsafe {
            if self.handle != 0 {
                let _ = windows_sys::Win32::Foundation::CloseHandle(self.handle as windows_sys::Win32::Foundation::HANDLE);
            }
        }
    }
}

struct BackendProcess {
    child: Mutex<Child>,
    stdin: Mutex<ChildStdin>,
    pending: Arc<Mutex<HashMap<u64, mpsc::Sender<Value>>>>,
    #[cfg(windows)]
    _job: BackendJob,
}

impl BackendProcess {
    fn request(&self, id: u64, cmd: &str, params: Value, timeout: Duration) -> Result<Value, String> {
        let (tx, rx) = mpsc::channel();
        self.pending
            .lock()
            .map_err(|_| "backend pending map poisoned".to_string())?
            .insert(id, tx);

        let req = json!({"id": id, "cmd": cmd, "params": params});
        let write_result = (|| {
            let mut stdin = self.stdin.lock().map_err(|_| "backend stdin poisoned".to_string())?;
            writeln!(stdin, "{}", req).map_err(|e| format!("backend write failed: {e}"))?;
            stdin.flush().map_err(|e| format!("backend flush failed: {e}"))
        })();
        if let Err(err) = write_result {
            let _ = self.pending.lock().map(|mut p| p.remove(&id));
            return Err(err);
        }

        let value = rx.recv_timeout(timeout).map_err(|_| {
            let _ = self.pending.lock().map(|mut p| p.remove(&id));
            format!("backend request timed out: {cmd}")
        })?;
        if value.get("ok").and_then(Value::as_bool) == Some(true) {
            Ok(value.get("result").cloned().unwrap_or(Value::Null))
        } else {
            let msg = value
                .pointer("/error/message")
                .and_then(Value::as_str)
                .unwrap_or("backend error");
            Err(msg.to_string())
        }
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        if let Ok(mut child) = self.child.lock() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

struct BackendState {
    process: BackendProcess,
    next_id: AtomicU64,
}

fn dev_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf()
}

fn backend_override() -> Result<Option<(String, Vec<String>)>, String> {
    let exe = match env::var("METATRON_BACKEND_EXE") {
        Ok(v) if !v.trim().is_empty() => v,
        _ => return Ok(None),
    };
    let args = match env::var("METATRON_BACKEND_ARGS_JSON") {
        Ok(raw) if !raw.trim().is_empty() => serde_json::from_str::<Vec<String>>(&raw)
            .map_err(|e| format!("METATRON_BACKEND_ARGS_JSON must be a JSON string array: {e}"))?,
        _ => Vec::new(),
    };
    Ok(Some((exe, args)))
}

fn spawn_backend(app: &tauri::AppHandle) -> Result<BackendProcess, String> {
    let mut command = if let Some((exe, args)) = backend_override()? {
        let mut c = Command::new(exe);
        c.args(args);
        c
    } else if cfg!(debug_assertions) {
        let python = env::var("METATRON_PYTHON")
            .unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() });
        let mut c = Command::new(python);
        c.args(["-X", "utf8", "-m", "metatron.main"]);
        c.current_dir(dev_root());
        c
    } else {
        let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
        let exe = if cfg!(windows) {
            resource_dir.join("resources/metatron-backend/metatron-backend.exe")
        } else {
            resource_dir.join("resources/metatron-backend/metatron-backend")
        };
        Command::new(exe)
    };

    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }

    let mut child = command
        .spawn()
        .map_err(|e| format!("failed to start Metatron backend: {e}"))?;
    #[cfg(windows)]
    let backend_job = match BackendJob::create_and_assign(&child) {
        Ok(job) => job,
        Err(err) => {
            // Never leave an unowned backend running when job assignment fails.
            let _ = child.kill();
            let _ = child.wait();
            return Err(err);
        }
    };
    let stdin = child.stdin.take().ok_or("backend stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("backend stdout unavailable")?;
    let stderr = child.stderr.take().ok_or("backend stderr unavailable")?;
    let pending: Arc<Mutex<HashMap<u64, mpsc::Sender<Value>>>> = Arc::new(Mutex::new(HashMap::new()));

    let app_handle = app.clone();
    let reader_pending = pending.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else { break };
            let Ok(value) = serde_json::from_str::<Value>(&line) else { continue };
            if let Some(id) = value.get("id").and_then(Value::as_u64) {
                let tx = reader_pending.lock().ok().and_then(|mut p| p.remove(&id));
                if let Some(tx) = tx {
                    let _ = tx.send(value);
                }
                continue;
            }
            if value.get("method").and_then(Value::as_str) == Some("metatron.event") {
                if let Some(params) = value.get("params") {
                    let _ = app_handle.emit("metatron-event", params.clone());
                }
            }
        }
        if let Ok(mut p) = reader_pending.lock() {
            for (_, tx) in p.drain() {
                let _ = tx.send(json!({"ok":false,"error":{"message":"backend exited"}}));
            }
        }
    });

    thread::spawn(move || {
        let mut reader = BufReader::new(stderr);
        let mut buf = String::new();
        loop {
            buf.clear();
            match reader.read_line(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(_) => eprint!("[metatron-backend] {}", buf),
            }
        }
    });

    Ok(BackendProcess {
        child: Mutex::new(child),
        stdin: Mutex::new(stdin),
        pending,
        #[cfg(windows)]
        _job: backend_job,
    })
}

fn main_allowed(cmd: &str) -> bool {
    matches!(cmd,
        "status" | "protocol.info" | "events.tail" | "bridge.live_events" | "diagnostics.summary" | "models.runtime_status"
        | "presence.dashboard" | "presence.quality" | "speech.start" | "speech.stop" | "hardware.refresh" | "hardware.windows_ml_catalog" | "hardware.ensure_windows_ml"
        | "settings.set" | "tts.enabled" | "tts.speak" | "tts.stop" | "tts.barge_in" | "history.list" | "history.pin" | "history.delete" | "history.clear"
        | "vocabulary.list" | "vocabulary.upsert" | "vocabulary.delete" | "app_rules.list" | "app_rules.upsert" | "app_rules.delete"
        | "tasks.list" | "tasks.create" | "tasks.move" | "agents.list" | "agent.detect" | "agent.start" | "agent.stop")
}

fn orb_allowed(cmd: &str) -> bool {
    matches!(
        cmd,
        "status"
            | "events.live"
            | "bridge.live_events"
            | "presence.snapshot"
            | "presence.renderer_state"
            | "settings.get"
            | "tts.barge_in"
    )
}

#[tauri::command]
fn backend_command(
    window: WebviewWindow,
    state: State<'_, BackendState>,
    cmd: String,
    params: Value,
    timeout_ms: Option<u64>,
) -> Result<Value, String> {
    let label = window.label();
    let allowed = match label {
        "orb" => orb_allowed(&cmd),
        "main" => main_allowed(&cmd),
        _ => false,
    };
    if !allowed { return Err(format!("window {label} is not authorized for command {cmd}")); }
    let id = state.next_id.fetch_add(1, Ordering::Relaxed);
    let timeout = Duration::from_millis(timeout_ms.unwrap_or(30_000).clamp(100, 600_000));
    state.process.request(id, &cmd, params, timeout)
}

fn position_orb_on_primary(orb: &WebviewWindow) -> Result<(), String> {
    let monitor = orb.primary_monitor().map_err(|e| e.to_string())?;
    let Some(monitor) = monitor else { return Ok(()); };
    let mon_pos = monitor.position();
    let mon_size = monitor.size();
    let orb_size = orb.outer_size().map_err(|e| e.to_string())?;
    let margin = 24i32;
    let x = mon_pos.x + mon_size.width as i32 - orb_size.width as i32 - margin;
    let y = mon_pos.y + mon_size.height as i32 - orb_size.height as i32 - margin;
    orb.set_position(PhysicalPosition::new(x, y)).map_err(|e| e.to_string())
}

#[tauri::command]
fn window_command(app: tauri::AppHandle, window: WebviewWindow, action: String, value: Value) -> Result<(), String> {
    // The orb may only reveal the main window; it cannot change global window
    // authority or persistent settings.
    if window.label() == "orb" && action != "main.show" {
        return Err(format!("orb window is not authorized for action {action}"));
    }
    let orb = app.get_webview_window("orb").ok_or("orb window not found")?;
    match action.as_str() {
        "orb.show" => orb.show().map_err(|e| e.to_string())?,
        "orb.hide" => orb.hide().map_err(|e| e.to_string())?,
        "orb.always_on_top" => orb
            .set_always_on_top(value.as_bool().unwrap_or(true))
            .map_err(|e| e.to_string())?,
        "orb.reposition" => position_orb_on_primary(&orb)?,
        "orb.scale" => {
            let scale = value.as_f64().unwrap_or(1.0).clamp(0.5, 2.0);
            let size = 360.0 * scale;
            orb.set_size(LogicalSize::new(size, size)).map_err(|e| e.to_string())?;
        }
        "main.show" => {
            let main = app.get_webview_window("main").ok_or("main window not found")?;
            main.show().map_err(|e| e.to_string())?;
            main.set_focus().map_err(|e| e.to_string())?;
        }
        "main.hide" => {
            let main = app.get_webview_window("main").ok_or("main window not found")?;
            main.hide().map_err(|e| e.to_string())?;
        }
        _ => return Err(format!("unknown window action {action}")),
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(main) = app.get_webview_window("main") {
                let _ = main.show();
                let _ = main.set_focus();
            }
        }))
        .setup(|app| {
            let backend = spawn_backend(&app.handle()).map_err(std::io::Error::other)?;
            app.manage(BackendState {
                process: backend,
                next_id: AtomicU64::new(1),
            });
            // Tauri creates the presence WebView separately. Make its initial state
            // explicit rather than depending on platform-specific default stacking.
            if let Some(orb) = app.get_webview_window("orb") {
                orb.set_always_on_top(true)?;
                position_orb_on_primary(&orb).map_err(std::io::Error::other)?;
                orb.show()?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_command, window_command])
        .run(tauri::generate_context!())
        .expect("error while running Metatron");
}
