use gstreamer::prelude::*;

#[flutter_rust_bridge::frb(sync)] // Synchronous mode for simplicity of the demo
pub fn greet(name: String) -> String {
    format!("Hello, {name}!")
}

#[flutter_rust_bridge::frb(sync)]
pub fn get_gstreamer_version() -> String {
    let (major, minor, micro, nano) = gstreamer::version();
    format!("GStreamer {major}.{minor}.{micro}.{nano}")
}

pub fn play_video(path: String) -> anyhow::Result<()> {
    let playbin = gstreamer::ElementFactory::make("playbin")
        .build()
        .map_err(|e| anyhow::anyhow!("Failed to create playbin: {}", e))?;

    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    playbin.set_property("uri", &uri);
    playbin.set_state(gstreamer::State::Playing)?;

    // 간단한 테스트를 위해 파이프라인이 생성된 것을 확인하고 바로 리턴합니다.
    // 실제로는 버스를 모니터링하거나 상태 변화를 기다려야 할 수 있습니다.
    Ok(())
}

#[flutter_rust_bridge::frb(init)]
pub fn init_app() {
    // Default utilities - feel free to customize
    flutter_rust_bridge::setup_default_user_utils();
    gstreamer::init().expect("Failed to initialize GStreamer");
}
