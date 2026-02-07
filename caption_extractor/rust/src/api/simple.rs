use crate::frb_generated::StreamSink;
use gstreamer::prelude::*;
use gstreamer_pbutils::prelude::*;

#[derive(Debug, Clone, Default)]
pub struct VideoFrame {
    pub pixels: Vec<u8>,
    pub width: i32,
    pub height: i32,
    pub is_cropped: bool,
    pub timestamp_ms: u64,
}

#[derive(Debug, Clone, Default)]
pub struct Roi {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub start_time_ms: u64,
    pub end_time_ms: u64,
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

pub struct NativePlayer {
    pipeline: gstreamer::Pipeline,
    roi: std::sync::Arc<std::sync::Mutex<Option<Roi>>>,
}

pub fn create_player(path: String) -> anyhow::Result<NativePlayer> {
    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    let pipeline_str = format!(
        "uridecodebin uri=\"{}\" ! videoconvert ! tee name=t \
         t. ! queue ! videoscale ! video/x-raw,format=RGBA ! appsink name=orig_sink sync=true \
         t. ! queue ! videoscale ! video/x-raw,format=RGBA ! appsink name=roi_sink sync=true",
        uri
    );

    let pipeline = gstreamer::parse_launch(&pipeline_str)?
        .dynamic_cast::<gstreamer::Pipeline>()
        .map_err(|el| anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name()))?;

    Ok(NativePlayer {
        pipeline,
        roi: std::sync::Arc::new(std::sync::Mutex::new(None)),
    })
}

fn process_sample(
    sample: &gstreamer::Sample,
    roi_arc: &std::sync::Arc<std::sync::Mutex<Option<Roi>>>,
) -> Result<(Vec<u8>, i32, i32, u64), gstreamer::FlowError> {
    let buffer = sample.buffer().ok_or(gstreamer::FlowError::Error)?;
    let caps = sample.caps().ok_or(gstreamer::FlowError::Error)?;
    let info =
        gstreamer_video::VideoInfo::from_caps(caps).map_err(|_| gstreamer::FlowError::Error)?;
    let map = buffer
        .map_readable()
        .map_err(|_| gstreamer::FlowError::Error)?;

    let mut pixels = map.to_vec();
    let mut width = info.width() as i32;
    let mut height = info.height() as i32;

    let roi_lock = roi_arc.lock().unwrap();
    if let Some(ref roi) = *roi_lock {
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
    Ok((pixels, width, height, pts))
}

fn process_sample_no_roi(
    sample: &gstreamer::Sample,
) -> Result<(Vec<u8>, i32, i32, u64), gstreamer::FlowError> {
    let buffer = sample.buffer().ok_or(gstreamer::FlowError::Error)?;
    let caps = sample.caps().ok_or(gstreamer::FlowError::Error)?;
    let info =
        gstreamer_video::VideoInfo::from_caps(caps).map_err(|_| gstreamer::FlowError::Error)?;
    let map = buffer
        .map_readable()
        .map_err(|_| gstreamer::FlowError::Error)?;

    let pixels = map.to_vec();
    let width = info.width() as i32;
    let height = info.height() as i32;
    let pts = buffer.pts().map(|p| p.mseconds()).unwrap_or(0);
    Ok((pixels, width, height, pts))
}

impl NativePlayer {
    pub fn start(
        &self,
        roi: Option<Roi>,
        start_time_ms: Option<u64>,
        sink: StreamSink<VideoFrame>,
    ) -> anyhow::Result<()> {
        let orig_sink = self
            .pipeline
            .by_name("orig_sink")
            .ok_or_else(|| anyhow::anyhow!("Original sink not found"))?
            .dynamic_cast::<gstreamer_app::AppSink>()
            .map_err(|_| anyhow::anyhow!("Failed to cast to AppSink"))?;

        let roi_sink = self
            .pipeline
            .by_name("roi_sink")
            .ok_or_else(|| anyhow::anyhow!("ROI sink not found"))?
            .dynamic_cast::<gstreamer_app::AppSink>()
            .map_err(|_| anyhow::anyhow!("Failed to cast to AppSink"))?;

        {
            let mut r = self.roi.lock().unwrap();
            *r = roi;
        }

        let roi_arc = self.roi.clone();
        let sink_arc = std::sync::Arc::new(sink);

        // 원본 스트림 콜백
        {
            let sink_clone = sink_arc.clone();
            let sink_clone_preroll = sink_arc.clone();
            orig_sink.set_callbacks(
                gstreamer_app::AppSinkCallbacks::builder()
                    .new_sample(move |appsink| {
                        let sample = appsink
                            .pull_sample()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) = process_sample_no_roi(&sample)?;
                        let _ = sink_clone.add(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: false,
                            timestamp_ms: pts,
                        });
                        Ok(gstreamer::FlowSuccess::Ok)
                    })
                    .new_preroll(move |appsink| {
                        let sample = appsink
                            .pull_preroll()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) = process_sample_no_roi(&sample)?;
                        let _ = sink_clone_preroll.add(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: false,
                            timestamp_ms: pts,
                        });
                        Ok(gstreamer::FlowSuccess::Ok)
                    })
                    .build(),
            );
        }

        // ROI 스트림 콜백
        {
            let sink_clone = sink_arc.clone();
            let sink_clone_preroll = sink_arc.clone();
            let roi_clone = roi_arc.clone();
            let roi_clone_preroll = roi_arc.clone();
            roi_sink.set_callbacks(
                gstreamer_app::AppSinkCallbacks::builder()
                    .new_sample(move |appsink| {
                        let sample = appsink
                            .pull_sample()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) = process_sample(&sample, &roi_clone)?;
                        let _ = sink_clone.add(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: true,
                            timestamp_ms: pts,
                        });
                        Ok(gstreamer::FlowSuccess::Ok)
                    })
                    .new_preroll(move |appsink| {
                        let sample = appsink
                            .pull_preroll()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) =
                            process_sample(&sample, &roi_clone_preroll)?;
                        let _ = sink_clone_preroll.add(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: true,
                            timestamp_ms: pts,
                        });
                        Ok(gstreamer::FlowSuccess::Ok)
                    })
                    .build(),
            );
        }

        self.pipeline.set_state(gstreamer::State::Paused)?;
        let _ = self
            .pipeline
            .state(Some(gstreamer::ClockTime::from_seconds(5)));

        if let Some(start_ms) = start_time_ms {
            let _ = self.pipeline.seek_simple(
                gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::KEY_UNIT,
                gstreamer::ClockTime::from_mseconds(start_ms),
            );
        }

        self.pipeline.set_state(gstreamer::State::Playing)?;

        let pipeline_clone = self.pipeline.clone();
        std::thread::spawn(move || {
            let bus = pipeline_clone.bus().unwrap();
            for msg in bus.iter_timed(gstreamer::ClockTime::NONE) {
                use gstreamer::MessageView;
                match msg.view() {
                    MessageView::Eos(..) | MessageView::Error(..) => break,
                    _ => (),
                }
            }
            let _ = pipeline_clone.set_state(gstreamer::State::Null);
        });

        Ok(())
    }

    pub fn pause(&self) -> anyhow::Result<()> {
        self.pipeline.set_state(gstreamer::State::Paused)?;
        Ok(())
    }

    pub fn resume(&self) -> anyhow::Result<()> {
        self.pipeline.set_state(gstreamer::State::Playing)?;
        Ok(())
    }

    pub fn seek(&self, time_ms: u64) -> anyhow::Result<()> {
        self.pipeline.seek_simple(
            gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::KEY_UNIT,
            gstreamer::ClockTime::from_mseconds(time_ms),
        )?;
        Ok(())
    }

    pub fn set_roi(&self, roi: Option<Roi>) {
        let mut r = self.roi.lock().unwrap();
        *r = roi;
    }

    pub fn stop(&self) -> anyhow::Result<()> {
        self.pipeline.set_state(gstreamer::State::Null)?;
        Ok(())
    }
}

pub fn get_frame(
    path: String,
    roi: Option<Roi>,
    time_ms: Option<u64>,
) -> anyhow::Result<VideoFrame> {
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

    pipeline.set_state(gstreamer::State::Paused)?;
    // Wait for the state change to complete before seeking
    let _ = pipeline.state(Some(gstreamer::ClockTime::from_seconds(5)));

    if let Some(ms) = time_ms {
        let _ = pipeline.seek_simple(
            gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::KEY_UNIT,
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
