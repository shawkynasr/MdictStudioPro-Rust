#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::sync::{Arc, atomic::{AtomicU8, Ordering}};
use studio_native_adapter::{Adapter, ApiCode, ApiError};
use tauri::{Emitter, Manager};

struct Desktop {
    adapter: Arc<Adapter>,
    // 0=active, 1=joining, 2=joined, 3=cleanup error (stay open for inspection).
    lifecycle: Arc<AtomicU8>,
}

#[tauri::command]
async fn studio_call(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Desktop>,
    request: String,
) -> Result<serde_json::Value, ApiError> {
    if window.label() != "main" {
        return Err(ApiError { code: ApiCode::InvalidInput, message: "Only the main app webview may call this adapter".into() });
    }
    if state.lifecycle.load(Ordering::Acquire) != 0 {
        return Err(ApiError { code: ApiCode::Closed, message: "Application is closing".into() });
    }
    let adapter = state.adapter.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut reply = adapter.call_json(&request)?;
        if let Some(object) = reply.as_object_mut() {
            if object.get("adapter").is_some() {
                object.insert("platform".into(), std::env::consts::OS.into());
            }
        }
        Ok::<_, ApiError>(reply)
    }).await.map_err(|e| ApiError { code: ApiCode::Internal, message: format!("Command task failed: {e}") })?
}

// Deliberately no caller-supplied URL, file path, executable or arguments.
fn project_url(target: &str) -> Result<&'static str, String> {
    match target {
        "repository" => Ok("https://github.com/shawkynasr/MdictStudioPro-Rust"),
        "releases" => Ok("https://github.com/shawkynasr/MdictStudioPro-Rust/releases"),
        _ => Err("Unknown project link".into()),
    }
}

#[tauri::command]
fn studio_open_project(window: tauri::WebviewWindow, target: String) -> Result<(), String> {
    if window.label() != "main" { return Err("Only the main app webview may open project links".into()); }
    let url = project_url(&target)?;
    #[cfg(target_os = "macos")]
    let mut command = std::process::Command::new("/usr/bin/open");
    #[cfg(target_os = "linux")]
    let mut command = std::process::Command::new("xdg-open");
    #[cfg(target_os = "windows")]
    let mut command = {
        let system = std::env::var_os("SYSTEMROOT").ok_or("SYSTEMROOT unavailable")?;
        let mut command = std::process::Command::new(std::path::PathBuf::from(system).join("System32/rundll32.exe"));
        command.arg("url.dll,FileProtocolHandler");
        command
    };
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    return Err("Project links are unavailable on this platform".into());
    #[cfg(any(target_os = "macos", target_os = "linux", target_os = "windows"))]
    {
        let mut child = command.arg(url).stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null()).stderr(std::process::Stdio::null())
            .spawn().map_err(|error| format!("Could not open project link: {error}"))?;
        // Reap without blocking the UI while a platform opener is running.
        std::thread::spawn(move || { let _ = child.wait(); });
        Ok(())
    }
}

#[cfg(test)]
mod project_link_tests {
    use super::project_url;
    #[test]
    fn only_fixed_official_targets_are_admitted() {
        assert_eq!(project_url("repository").unwrap(), "https://github.com/shawkynasr/MdictStudioPro-Rust");
        assert_eq!(project_url("releases").unwrap(), "https://github.com/shawkynasr/MdictStudioPro-Rust/releases");
        for value in ["", "https://example.org", "file:///tmp/a", "../releases", "releases;bad"] {
            assert!(project_url(value).is_err());
        }
    }
}

fn request_exit(app: &tauri::AppHandle) {
    let desktop = app.state::<Desktop>();
    if desktop.lifecycle.compare_exchange(0, 1, Ordering::AcqRel, Ordering::Acquire).is_err() { return; }
    let adapter = desktop.adapter.clone();
    let lifecycle = desktop.lifecycle.clone();
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        match adapter.shutdown() {
            Ok(()) => { lifecycle.store(2, Ordering::Release); handle.exit(0); }
            Err(error) => {
                lifecycle.store(3, Ordering::Release);
                // Native ApiError deliberately has no Clone implementation.
                // Tauri events require Serialize + Clone: use an owned wire DTO.
                let payload = serde_json::json!({ "code": error.code, "message": error.message });
                let _ = handle.emit_to("main", "studio-shutdown-error", payload);
            }
        }
    });
}

fn main() {
    let adapter = Adapter::new().expect("Native runtime initialization failed");
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Desktop { adapter: Arc::new(adapter), lifecycle: Arc::new(AtomicU8::new(0)) })
        .setup(|app| {
            // Includes standard platform application, Edit and Window menus.
            app.set_menu(tauri::menu::Menu::default(app.handle())?)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![studio_call, studio_open_project])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.state::<Desktop>().lifecycle.load(Ordering::Acquire) != 2 {
                    api.prevent_close();
                    request_exit(window.app_handle());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Tauri shell startup failed");
    app.run(|handle, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            if handle.state::<Desktop>().lifecycle.load(Ordering::Acquire) != 2 {
                api.prevent_exit(); request_exit(handle);
            }
        }
    });
}
