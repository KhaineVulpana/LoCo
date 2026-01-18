#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::menu::{Menu, MenuItem, Submenu};
use tauri::{Emitter, Runtime};

fn build_menu<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<Menu<R>> {
    let export_menu = Submenu::with_items(
        app,
        "Export",
        true,
        &[
            &MenuItem::with_id(app, "menu_export_glb", "GLB", true, None::<&str>)?,
            &MenuItem::with_id(app, "menu_export_stl", "STL", true, None::<&str>)?,
        ],
    )?;

    let file_menu = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &MenuItem::with_id(app, "menu_settings", "Settings", true, None::<&str>)?,
            &MenuItem::with_id(app, "menu_logs", "Logs", true, None::<&str>)?,
            &MenuItem::with_id(app, "menu_import", "Import", true, None::<&str>)?,
            &export_menu,
        ],
    )?;

    Menu::with_items(app, &[&file_menu])
}

fn emit_menu_action<R: Runtime>(app: &tauri::AppHandle<R>, action: &str) {
    let _ = app.emit("menu-action", action);
}

fn main() {
    tauri::Builder::default()
        .menu(|app| build_menu(app))
        .on_menu_event(|app, event| match event.id().as_ref() {
            "menu_settings" => emit_menu_action(app, "menu_settings"),
            "menu_logs" => emit_menu_action(app, "menu_logs"),
            "menu_import" => emit_menu_action(app, "menu_import"),
            "menu_export_glb" => emit_menu_action(app, "menu_export_glb"),
            "menu_export_stl" => emit_menu_action(app, "menu_export_stl"),
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running 3d-gen desktop app");
}
