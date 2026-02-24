use crate::api::models::{Roi, VideoFrame, VideoInfo};
use anyhow::Result;
use gstreamer::prelude::*;
use gstreamer_pbutils::prelude::*;

pub fn get_video_info(path: String) -> Result<VideoInfo> {
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

pub fn get_frame(path: String, roi: Option<Roi>, time_ms: Option<u64>) -> Result<VideoFrame> {
    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    let pipeline_str = format!(
        "uridecodebin uri=\"{}\" ! videoconvert ! videoscale ! video/x-raw,format=RGBA ! appsink name=sink sync=true max-buffers=1 drop=true",
        uri
    );

    let pipeline = gstreamer::parse::launch(&pipeline_str)?
        .dynamic_cast::<gstreamer::Pipeline>()
        .map_err(|el| anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name()))?;

    let appsink = pipeline
        .by_name("sink")
        .ok_or_else(|| anyhow::anyhow!("Sink not found"))?
        .dynamic_cast::<gstreamer_app::AppSink>()
        .map_err(|_| anyhow::anyhow!("Failed to cast to AppSink"))?;

    pipeline.set_state(gstreamer::State::Paused)?;
    let _ = pipeline.state(Some(gstreamer::ClockTime::from_seconds(5)));

    if let Some(ms) = time_ms {
        let _ = pipeline.seek_simple(
            gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::ACCURATE,
            gstreamer::ClockTime::from_mseconds(ms),
        );
    }

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

    if let Some(ref roi) = roi {
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

    let pts = buffer.pts().map(|p| p.mseconds()).unwrap_or(0);

    let frame = VideoFrame {
        pixels,
        width,
        height,
        is_cropped: roi.is_some(),
        timestamp_ms: pts,
    };

    let _ = pipeline.set_state(gstreamer::State::Null);

    Ok(frame)
}

pub fn init() -> Result<()> {
    gstreamer::init().map_err(|e| anyhow::anyhow!("Failed to initialize GStreamer: {}", e))
}

pub fn get_version() -> String {
    let (major, minor, micro, nano) = gstreamer::version();
    format!("GStreamer {major}.{minor}.{micro}.{nano}")
}
