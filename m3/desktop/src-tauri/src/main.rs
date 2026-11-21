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
        .invoke_handler(tauri::generate_handler![studio_call])
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
