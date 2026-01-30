use gstreamer::prelude::*;
use gstreamer_pbutils::prelude::*;

#[derive(Debug, Clone, Default)]
pub struct VideoInfo {
    pub width: i32,
    pub height: i32,
    pub duration_ms: u64,
    pub format: String,
    pub fps: f64,
}

#[flutter_rust_bridge::frb(sync)] // Synchronous mode for simplicity of the demo
pub fn greet(name: String) -> String {
    format!("Hello, {name}!")
}

#[flutter_rust_bridge::frb(sync)]
pub fn get_gstreamer_version() -> String {
    let (major, minor, micro, nano) = gstreamer::version();
    format!("GStreamer {major}.{minor}.{micro}.{nano}")
}

pub fn get_video_info(path: String) -> anyhow::Result<VideoInfo> {
    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    let discoverer = gstreamer_pbutils::Discoverer::new(gstreamer::ClockTime::from_seconds(5))?;
    let info = discoverer.discover_uri(&uri)?;

    let mut video_info = VideoInfo::default();
    video_info.duration_ms = info.duration().map(|d| d.mseconds()).unwrap_or(0);

    if let Some(stream) = info.video_streams().first() {
        video_info.width = stream.width() as i32;
        video_info.height = stream.height() as i32;
        video_info.format = stream.caps().map(|c| c.to_string()).unwrap_or_default();
        let fps = stream.framerate();
        let fps_n = fps.numer();
        let fps_d = fps.denom();
        if fps_d != 0 {
            video_info.fps = fps_n as f64 / fps_d as f64;
        }
    }

    Ok(video_info)
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
