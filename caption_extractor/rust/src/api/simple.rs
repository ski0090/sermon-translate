#[flutter_rust_bridge::frb(sync)] // Synchronous mode for simplicity of the demo
pub fn greet(name: String) -> String {
    format!("Hello, {name}!")
}

#[flutter_rust_bridge::frb(sync)]
pub fn get_gstreamer_version() -> String {
    let (major, minor, micro, nano) = gstreamer::version();
    format!("GStreamer {major}.{minor}.{micro}.{nano}")
}

#[flutter_rust_bridge::frb(init)]
pub fn init_app() {
    // Default utilities - feel free to customize
    flutter_rust_bridge::setup_default_user_utils();
    gstreamer::init().expect("Failed to initialize GStreamer");
}
