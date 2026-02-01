use crate::frb_generated::StreamSink;
use gstreamer::prelude::*;
use gstreamer_pbutils::prelude::*;

#[derive(Debug, Clone, Default)]
pub struct VideoFrame {
    pub pixels: Vec<u8>,
    pub width: i32,
    pub height: i32,
}

#[derive(Debug, Clone, Default)]
pub struct Roi {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

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

pub fn stream_video(
    path: String,
    roi: Option<Roi>,
    sink: StreamSink<VideoFrame>,
) -> anyhow::Result<()> {
    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    let pipeline_str = format!(
        "uridecodebin uri=\"{}\" ! videoconvert ! videoscale ! video/x-raw,format=RGBA ! appsink name=sink sync=true",
        uri
    );

    let pipeline = gstreamer::parse_launch(&pipeline_str)?
        .dynamic_cast::<gstreamer::Pipeline>()
        .map_err(|el| anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name()))?;

    let appsink = pipeline
        .by_name("sink")
        .ok_or_else(|| anyhow::anyhow!("Sink not found"))?
        .dynamic_cast::<gstreamer_app::AppSink>()
        .map_err(|_| anyhow::anyhow!("Failed to cast to AppSink"))?;

    appsink.set_callbacks(
        gstreamer_app::AppSinkCallbacks::builder()
            .new_sample(move |appsink| {
                let sample = appsink
                    .pull_sample()
                    .map_err(|_| gstreamer::FlowError::Error)?;
                let buffer = sample.buffer().ok_or(gstreamer::FlowError::Error)?;
                let caps = sample.caps().ok_or(gstreamer::FlowError::Error)?;
                let info = gstreamer_video::VideoInfo::from_caps(caps)
                    .map_err(|_| gstreamer::FlowError::Error)?;

                let map = buffer
                    .map_readable()
                    .map_err(|_| gstreamer::FlowError::Error)?;

                let mut pixels = map.to_vec();
                let mut width = info.width() as i32;
                let mut height = info.height() as i32;

                if let Some(ref roi) = roi {
                    // ROI 적용 (수동 크롭)
                    let roi_x = roi.x.clamp(0, width);
                    let roi_y = roi.y.clamp(0, height);
                    let roi_w = roi.width.clamp(0, width - roi_x);
                    let roi_h = roi.height.clamp(0, height - roi_y);

                    if roi_w > 0 && roi_h > 0 {
                        let mut cropped = Vec::with_capacity((roi_w * roi_h * 4) as usize);
                        for y in 0..roi_h {
                            let start = (((roi_y + y) * width + roi_x) * 4) as usize;
                            let end = start + (roi_w * 4) as usize;
                            cropped.extend_from_slice(&pixels[start..end]);
                        }
                        pixels = cropped;
                        width = roi_w;
                        height = roi_h;
                    }
                }

                if sink
                    .add(VideoFrame {
                        pixels,
                        width,
                        height,
                    })
                    .is_err()
                {
                    return Err(gstreamer::FlowError::Eos);
                }

                Ok(gstreamer::FlowSuccess::Ok)
            })
            .build(),
    );

    pipeline.set_state(gstreamer::State::Playing)?;

    std::thread::spawn(move || {
        let bus = pipeline.bus().unwrap();
        for msg in bus.iter_timed(gstreamer::ClockTime::NONE) {
            use gstreamer::MessageView;
            match msg.view() {
                MessageView::Eos(..) | MessageView::Error(..) => break,
                _ => (),
            }
        }
        let _ = pipeline.set_state(gstreamer::State::Null);
    });

    Ok(())
}

pub fn get_first_frame(path: String, roi: Option<Roi>) -> anyhow::Result<VideoFrame> {
    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    let pipeline_str = format!(
        "uridecodebin uri=\"{}\" ! videoconvert ! videoscale ! video/x-raw,format=RGBA ! appsink name=sink sync=true max-buffers=1 drop=true",
        uri
    );

    let pipeline = gstreamer::parse_launch(&pipeline_str)?
        .dynamic_cast::<gstreamer::Pipeline>()
        .map_err(|el| anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name()))?;

    let appsink = pipeline
        .by_name("sink")
        .ok_or_else(|| anyhow::anyhow!("Sink not found"))?
        .dynamic_cast::<gstreamer_app::AppSink>()
        .map_err(|_| anyhow::anyhow!("Failed to cast to AppSink"))?;

    pipeline.set_state(gstreamer::State::Playing)?;

    let sample = appsink
        .pull_sample()
        .map_err(|_| anyhow::anyhow!("Failed to pull sample"))?;
    let buffer = sample
        .buffer()
        .ok_or_else(|| anyhow::anyhow!("No buffer in sample"))?;
    let caps = sample
        .caps()
        .ok_or_else(|| anyhow::anyhow!("No caps in sample"))?;
    let info = gstreamer_video::VideoInfo::from_caps(caps)
        .map_err(|_| anyhow::anyhow!("Failed to parse caps"))?;
    let map = buffer
        .map_readable()
        .map_err(|_| anyhow::anyhow!("Failed to map buffer"))?;

    let mut pixels = map.to_vec();
    let mut width = info.width() as i32;
    let mut height = info.height() as i32;

    if let Some(roi) = roi {
        let roi_x = roi.x.clamp(0, width);
        let roi_y = roi.y.clamp(0, height);
        let roi_w = roi.width.clamp(0, width - roi_x);
        let roi_h = roi.height.clamp(0, height - roi_y);

        if roi_w > 0 && roi_h > 0 {
            let mut cropped = Vec::with_capacity((roi_w * roi_h * 4) as usize);
            for y in 0..roi_h {
                let start = (((roi_y + y) * width + roi_x) * 4) as usize;
                let end = start + (roi_w * 4) as usize;
                cropped.extend_from_slice(&pixels[start..end]);
            }
            pixels = cropped;
            width = roi_w;
            height = roi_h;
        }
    }

    let frame = VideoFrame {
        pixels,
        width,
        height,
    };

    let _ = pipeline.set_state(gstreamer::State::Null);

    Ok(frame)
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
