//! Spike: a Tauri 2 shell that runs the packaged Scheduling Core (`tkb-core`) as a child process.
//!
//! Core is bundled as a resource under `core/` (PyInstaller onedir folder or onefile exe) and is
//! called exactly like the CLI: JSON file in, JSON file out. Nothing here knows Core's contracts.
//!
//! Measurement mode (used by measure.ps1): `app --auto <result.json> [--cancel-after <s>] -- <core args>`
//! runs Core once with the window open, writes a RunResult JSON and exits.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Read;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Manager};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[derive(Default)]
struct Running {
    pid: Mutex<Option<u32>>,
    cancelled: AtomicBool,
}

#[derive(Serialize, Clone)]
struct RunResult {
    exit_code: Option<i32>,
    wall_ms: u128,
    cancelled: bool,
    core_path: String,
    stderr_tail: String,
}

fn core_path(app: &AppHandle) -> Result<PathBuf, String> {
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let exe = if cfg!(windows) { "tkb-core.exe" } else { "tkb-core" };
    let path = resources.join("core").join(exe);
    if path.exists() {
        Ok(path)
    } else {
        Err(format!("Core not found at {}", path.display()))
    }
}

fn run_blocking(app: &AppHandle, args: Vec<String>) -> Result<RunResult, String> {
    let exe = core_path(app)?;
    let state = app.state::<Running>();
    let mut cmd = Command::new(&exe);
    cmd.args(&args).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let started = Instant::now();
    let mut child = {
        let mut pid = state.pid.lock().unwrap();
        if pid.is_some() {
            return Err("Core is already running".into());
        }
        state.cancelled.store(false, Ordering::SeqCst);
        let child = cmd.spawn().map_err(|e| format!("cannot start {}: {e}", exe.display()))?;
        *pid = Some(child.id());
        child
    };
    // Drain stderr on a thread so a full pipe never blocks Core.
    let mut stderr = child.stderr.take().expect("stderr is piped");
    let reader = std::thread::spawn(move || {
        let mut text = String::new();
        let _ = stderr.read_to_string(&mut text);
        text
    });
    let status = child.wait().map_err(|e| e.to_string());
    *state.pid.lock().unwrap() = None;
    let text = reader.join().unwrap_or_default();
    let tail: String = text.chars().rev().take(2000).collect::<Vec<_>>().into_iter().rev().collect();
    Ok(RunResult {
        exit_code: status?.code(),
        wall_ms: started.elapsed().as_millis(),
        cancelled: state.cancelled.load(Ordering::SeqCst),
        core_path: exe.display().to_string(),
        stderr_tail: tail,
    })
}

/// Kill Core and every process it started (a onefile build runs Core in a child of the bootloader).
fn cancel(app: &AppHandle) -> bool {
    let state = app.state::<Running>();
    let Some(pid) = *state.pid.lock().unwrap() else { return false };
    state.cancelled.store(true, Ordering::SeqCst);
    let mut kill = if cfg!(windows) {
        let mut c = Command::new("taskkill");
        c.args(["/PID", &pid.to_string(), "/T", "/F"]);
        c
    } else {
        let mut c = Command::new("kill");
        c.args(["-9", &pid.to_string()]);
        c
    };
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        kill.creation_flags(CREATE_NO_WINDOW);
    }
    kill.status().map(|s| s.success()).unwrap_or(false)
}

#[tauri::command]
async fn run_core(app: AppHandle, args: Vec<String>) -> Result<RunResult, String> {
    tauri::async_runtime::spawn_blocking(move || run_blocking(&app, args))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
fn cancel_core(app: AppHandle) -> bool {
    cancel(&app)
}

#[tauri::command]
fn core_info(app: AppHandle) -> Result<String, String> {
    core_path(&app).map(|p| p.display().to_string())
}

struct AutoRun {
    result: PathBuf,
    cancel_after: Option<u64>,
    args: Vec<String>,
}

fn parse_auto() -> Option<AutoRun> {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let pos = argv.iter().position(|a| a == "--auto")?;
    let result = PathBuf::from(argv.get(pos + 1)?);
    let cancel_after = argv
        .iter()
        .position(|a| a == "--cancel-after")
        .and_then(|i| argv.get(i + 1))
        .and_then(|v| v.parse().ok());
    let sep = argv.iter().position(|a| a == "--")?;
    Some(AutoRun { result, cancel_after, args: argv[sep + 1..].to_vec() })
}

fn main() {
    tauri::Builder::default()
        .manage(Running::default())
        .invoke_handler(tauri::generate_handler![run_core, cancel_core, core_info])
        .setup(|app| {
            if let Some(auto) = parse_auto() {
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    if let Some(seconds) = auto.cancel_after {
                        let h = handle.clone();
                        std::thread::spawn(move || {
                            std::thread::sleep(Duration::from_secs(seconds));
                            cancel(&h);
                        });
                    }
                    let outcome = match run_blocking(&handle, auto.args) {
                        Ok(r) => serde_json::to_value(r).unwrap(),
                        Err(e) => serde_json::json!({ "error": e }),
                    };
                    let _ = std::fs::write(&auto.result, serde_json::to_vec_pretty(&outcome).unwrap());
                    handle.exit(0);
                });
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the spike app");
}
