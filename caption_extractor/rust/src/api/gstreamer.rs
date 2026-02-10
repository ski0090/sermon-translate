use crate::api::models::{CaptionResult, PlayerEvent, Roi, VideoFrame, VideoInfo};
use crate::frb_generated::StreamSink;
use crate::gstreamer::utils;
use crate::ocr::OcrEngine;
use anyhow::Result;
use gstreamer::prelude::*;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub struct NativePlayer {
    pipeline: gstreamer::Pipeline,
    roi: Arc<Mutex<Option<Roi>>>,
    ocr_engine: Arc<Mutex<OcrEngine>>,
    last_ocr_time: Arc<Mutex<Instant>>,
}

#[flutter_rust_bridge::frb(sync)]
pub fn greet(name: String) -> String {
    format!("Hello, {name}!")
}

#[flutter_rust_bridge::frb(sync)]
pub fn get_gstreamer_version() -> String {
    utils::get_version()
}

pub fn create_player(path: String) -> Result<NativePlayer> {
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
        .map_err(|el: gstreamer::Element| {
            anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name())
        })?;

    Ok(NativePlayer {
        pipeline,
        roi: Arc::new(Mutex::new(None)),
        ocr_engine: Arc::new(Mutex::new(OcrEngine::new("kor+eng")?)),
        last_ocr_time: Arc::new(Mutex::new(Instant::now())),
    })
}

pub fn get_video_info(path: String) -> Result<VideoInfo> {
    utils::get_video_info(path)
}

pub fn get_frame(path: String, roi: Option<Roi>, time_ms: Option<u64>) -> Result<VideoFrame> {
    utils::get_frame(path, roi, time_ms)
}

pub fn init_gstreamer() -> Result<()> {
    utils::init()
}

#[flutter_rust_bridge::frb(init)]
pub fn init_app() {
    flutter_rust_bridge::setup_default_user_utils();
    let _ = utils::init();
}

fn process_sample(
    sample: &gstreamer::Sample,
    roi_arc: &Arc<Mutex<Option<Roi>>>,
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
        sink: StreamSink<PlayerEvent>,
    ) -> Result<()> {
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
        let sink_arc = Arc::new(sink);

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
                        let _ = sink_clone.add(PlayerEvent::Video(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: false,
                            timestamp_ms: pts,
                        }));
                        Ok(gstreamer::FlowSuccess::Ok)
                    })
                    .new_preroll(move |appsink| {
                        let sample = appsink
                            .pull_preroll()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) = process_sample_no_roi(&sample)?;
                        let _ = sink_clone_preroll.add(PlayerEvent::Video(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: false,
                            timestamp_ms: pts,
                        }));
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
            
            let ocr_engine_clone = self.ocr_engine.clone();
            let last_ocr_time_clone = self.last_ocr_time.clone();

            roi_sink.set_callbacks(
                gstreamer_app::AppSinkCallbacks::builder()
                    .new_sample(move |appsink| {
                        let sample = appsink
                            .pull_sample()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) = process_sample(&sample, &roi_clone)?;
                        
                        let _ = sink_clone.add(PlayerEvent::Video(VideoFrame {
                            pixels: pixels.clone(),
                            width,
                            height,
                            is_cropped: true,
                            timestamp_ms: pts,
                        }));

                        // OCR 처리 (500ms 간격)
                        let mut last_time = last_ocr_time_clone.lock().unwrap();
                        if last_time.elapsed() >= Duration::from_millis(500) {
                            let mut ocr = ocr_engine_clone.lock().unwrap();
                            if let Ok((text, conf)) = ocr.extract_text(&pixels, width, height) {
                                if !text.is_empty() {
                                    let _ = sink_clone.add(PlayerEvent::Caption(CaptionResult {
                                        text,
                                        confidence: conf,
                                        timestamp_ms: pts,
                                    }));
                                }
                            }
                            *last_time = Instant::now();
                        }

                        Ok(gstreamer::FlowSuccess::Ok)
                    })
                    .new_preroll(move |appsink| {
                        let sample = appsink
                            .pull_preroll()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) =
                            process_sample(&sample, &roi_clone_preroll)?;
                        let _ = sink_clone_preroll.add(PlayerEvent::Video(VideoFrame {
                            pixels,
                            width,
                            height,
                            is_cropped: true,
                            timestamp_ms: pts,
                        }));
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
                gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::ACCURATE,
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

    pub fn pause(&self) -> Result<()> {
        self.pipeline.set_state(gstreamer::State::Paused)?;
        Ok(())
    }

    pub fn resume(&self) -> Result<()> {
        self.pipeline.set_state(gstreamer::State::Playing)?;
        Ok(())
    }

    pub fn seek(&self, time_ms: u64) -> Result<()> {
        self.pipeline.seek_simple(
            gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::ACCURATE,
            gstreamer::ClockTime::from_mseconds(time_ms),
        )?;
        Ok(())
    }

    pub fn set_roi(&self, roi: Option<Roi>) {
        let mut r = self.roi.lock().unwrap();
        *r = roi;
    }

    pub fn stop(&self) -> Result<()> {
        self.pipeline.set_state(gstreamer::State::Null)?;
        Ok(())
    }
}
