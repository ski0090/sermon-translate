use crate::api::models::{CaptionResult, ExtractorEvent, PlayerEvent, Roi, VideoFrame, VideoInfo};
use crate::frb_generated::StreamSink;
use crate::gstreamer::utils;
use crate::ocr::OcrEngine;
use anyhow::Result;
use gstreamer::prelude::*;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub struct NativePlayer {
    pipeline: gstreamer::Pipeline,
    roi: Arc<Mutex<Option<Roi>>>,
    ocr_engine: Arc<Mutex<OcrEngine>>,
    last_ocr_time: Arc<Mutex<Instant>>,
    auto_roi_tracking: Arc<Mutex<bool>>,
    last_auto_roi_time: Arc<Mutex<Instant>>,
}

pub struct CaptionExtractor {
    pipeline: gstreamer::Pipeline,
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

    // d3d11 요소를 활용한 Windows 하드웨어 가속 파이프라인 구성
    let pipeline_str = format!(
        "uridecodebin uri=\"{}\" ! d3d11download ! videoconvert ! tee name=t \
         t. ! queue ! videoscale ! video/x-raw,format=RGBA ! appsink name=orig_sink sync=true \
         t. ! queue ! videoscale ! video/x-raw,format=RGBA ! appsink name=roi_sink sync=true",
        uri
    );

    let pipeline = gstreamer::parse::launch(&pipeline_str)?
        .dynamic_cast::<gstreamer::Pipeline>()
        .map_err(|el: gstreamer::Element| {
            anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name())
        })?;

    Ok(NativePlayer {
        pipeline,
        roi: Arc::new(Mutex::new(None)),
        ocr_engine: Arc::new(Mutex::new(OcrEngine::new("kor+eng")?)),
        last_ocr_time: Arc::new(Mutex::new(Instant::now())),
        auto_roi_tracking: Arc::new(Mutex::new(false)),
        last_auto_roi_time: Arc::new(Mutex::new(Instant::now())),
    })
}

pub fn create_extractor(path: String) -> Result<CaptionExtractor> {
    let uri = if path.starts_with("http") {
        path
    } else {
        format!("file:///{}", path.replace("\\", "/"))
    };

    // d3d11download를 통해 GPU 메모리에서 CPU 메모리로 빠르게 내리기 + videorate로 2fps 강제
    let pipeline_str = format!(
        "uridecodebin uri=\"{}\" ! d3d11download ! videoconvert ! videoscale ! videorate ! video/x-raw,framerate=2/1,format=RGBA ! appsink name=extractor_sink sync=false drop=false",
        uri
    );

    let pipeline = gstreamer::parse::launch(&pipeline_str)?
        .dynamic_cast::<gstreamer::Pipeline>()
        .map_err(|el: gstreamer::Element| {
            anyhow::anyhow!("Failed to cast to Pipeline. Type: {}", el.type_().name())
        })?;

    Ok(CaptionExtractor { pipeline })
}

pub fn get_video_info(path: String) -> Result<VideoInfo> {
    utils::get_video_info(path)
}

pub fn get_frame(path: String, roi: Option<Roi>, time_ms: Option<u64>) -> Result<VideoFrame> {
    utils::get_frame(path, roi, time_ms)
}

pub fn auto_detect_roi_for_time(path: String, time_ms: Option<u64>) -> Result<Option<Roi>> {
    let frame = utils::get_frame(path, None, time_ms)?;
    let mut ocr = OcrEngine::new("kor+eng")?;
    ocr.auto_detect_roi(&frame.pixels, frame.width, frame.height)
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
    pub fn set_auto_tracking(&self, enabled: bool) -> Result<()> {
        let mut tracking = self.auto_roi_tracking.lock().unwrap();
        *tracking = enabled;
        Ok(())
    }

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

            let ocr_engine_for_auto = self.ocr_engine.clone();
            let last_auto_time_clone = self.last_auto_roi_time.clone();
            let auto_tracking_clone = self.auto_roi_tracking.clone();
            let roi_arc_clone = self.roi.clone();

            orig_sink.set_callbacks(
                gstreamer_app::AppSinkCallbacks::builder()
                    .new_sample(move |appsink| {
                        let sample = appsink
                            .pull_sample()
                            .map_err(|_| gstreamer::FlowError::Error)?;
                        let (pixels, width, height, pts) = process_sample_no_roi(&sample)?;

                        let _ = sink_clone.add(PlayerEvent::Video(VideoFrame {
                            pixels: pixels.clone(),
                            width,
                            height,
                            is_cropped: false,
                            timestamp_ms: pts,
                        }));

                        // 자동 ROI 추적(Tracking) 처리 (500ms 간격)
                        let is_tracking = *auto_tracking_clone.lock().unwrap();
                        if is_tracking {
                            let mut last_time = last_auto_time_clone.lock().unwrap();
                            if last_time.elapsed() >= Duration::from_millis(500) {
                                println!("[Rust] Running continuous auto_detect_roi...");
                                let mut ocr = ocr_engine_for_auto.lock().unwrap();
                                match ocr.auto_detect_roi(&pixels, width, height) {
                                    Ok(Some(detected_roi)) => {
                                        println!("[Rust] Found auto ROI: {:?}", detected_roi);
                                        // 내부 ROI 상태 즉시 업데이트
                                        {
                                            let mut r = roi_arc_clone.lock().unwrap();
                                            *r = Some(detected_roi.clone());
                                        }

                                        // Flutter로 이벤트 전송
                                        let _ = sink_clone
                                            .add(PlayerEvent::AutoRoiUpdated(detected_roi));
                                    }
                                    Ok(None) => {
                                        // println!("[Rust] auto_detect_roi returned None");
                                    }
                                    Err(e) => {
                                        println!("[Rust] auto_detect_roi error: {:?}", e);
                                    }
                                }
                                *last_time = Instant::now();
                            }
                        }

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

impl CaptionExtractor {
    pub fn start(
        &self,
        roi: Option<Roi>,
        start_time_ms: Option<u64>,
        end_time_ms: Option<u64>,
        total_duration_ms: u64,
        sink: StreamSink<ExtractorEvent>,
    ) -> Result<()> {
        let app_sink = self
            .pipeline
            .by_name("extractor_sink")
            .ok_or_else(|| anyhow::anyhow!("extractor sink not found"))?
            .dynamic_cast::<gstreamer_app::AppSink>()
            .map_err(|_| anyhow::anyhow!("Failed to cast to AppSink"))?;

        let sink_arc = Arc::new(sink);
        let sink_clone = sink_arc.clone();

        let mut ocr_engine = OcrEngine::new("kor+eng")?;
        let initial_roi = roi.clone();

        app_sink.set_callbacks(
            gstreamer_app::AppSinkCallbacks::builder()
                .new_sample(move |appsink| {
                    let sample = match appsink.pull_sample() {
                        Ok(s) => s,
                        Err(_) => return Ok(gstreamer::FlowSuccess::Ok),
                    };

                    let buffer = match sample.buffer() {
                        Some(b) => b,
                        None => return Ok(gstreamer::FlowSuccess::Ok),
                    };
                    let caps = match sample.caps() {
                        Some(c) => c,
                        None => return Ok(gstreamer::FlowSuccess::Ok),
                    };
                    let info = match gstreamer_video::VideoInfo::from_caps(caps) {
                        Ok(i) => i,
                        Err(_) => return Ok(gstreamer::FlowSuccess::Ok),
                    };
                    let map = match buffer.map_readable() {
                        Ok(m) => m,
                        Err(_) => return Ok(gstreamer::FlowSuccess::Ok),
                    };

                    let mut pixels = map.to_vec();
                    let mut width = info.width() as i32;
                    let mut height = info.height() as i32;
                    let pts = buffer.pts().map(|p| p.mseconds()).unwrap_or(0);

                    // End time check
                    if let Some(end_ms) = end_time_ms {
                        if pts > end_ms {
                            let _ = sink_clone.add(ExtractorEvent::Finished);
                            return Err(gstreamer::FlowError::Eos);
                        }
                    }

                    // ROI 결정 로직:
                    // - 수동 ROI 설정 시 → 해당 영역으로 크롭
                    // - ROI 없음 → 자막이 주로 나오는 하단 30% 영역으로 크롭 (전체보다 3배 빠름)
                    {
                        let (crop_x, crop_y, crop_w, crop_h) = if let Some(ref r) = initial_roi {
                            let rx = r.x.clamp(0, width);
                            let ry = r.y.clamp(0, height);
                            let rw = r.width.clamp(0, width - rx);
                            let rh = r.height.clamp(0, height - ry);
                            (rx, ry, rw, rh)
                        } else {
                            // 하단 30%
                            let crop_y = (height as f32 * 0.70) as i32;
                            let crop_h = height - crop_y;
                            (0, crop_y, width, crop_h)
                        };

                        if crop_w > 0 && crop_h > 0 {
                            let mut cropped = Vec::with_capacity((crop_w * crop_h * 4) as usize);
                            for y in 0..crop_h {
                                let start = (((crop_y + y) * width + crop_x) * 4) as usize;
                                let end = start + (crop_w * 4) as usize;
                                if end <= pixels.len() {
                                    cropped.extend_from_slice(&pixels[start..end]);
                                }
                            }
                            pixels = cropped;
                            width = crop_w;
                            height = crop_h;
                        }
                    }

                    // OCR 처리 (한 프레임당 1번만 호출)
                    match ocr_engine.extract_text(&pixels, width, height) {
                        Ok((text, conf)) => {
                            println!("[OCR] ts={}ms text={:?} conf={:.2}", pts, text, conf);
                            if !text.is_empty() {
                                let result = ExtractorEvent::Caption(CaptionResult {
                                    text,
                                    confidence: conf,
                                    timestamp_ms: pts,
                                });
                                let _ = sink_clone.add(result);
                            }
                        }
                        Err(e) => {
                            eprintln!("[OCR ERROR] {}", e);
                        }
                    }

                    let percentage = if total_duration_ms > 0 {
                        (pts as f64 / total_duration_ms as f64) * 100.0
                    } else {
                        0.0
                    };
                    let _ = sink_clone.add(ExtractorEvent::Progress(percentage, pts));
                    Ok(gstreamer::FlowSuccess::Ok)
                })
                .build(),
        );

        if let Some(start_ms) = start_time_ms {
            let _ = self.pipeline.set_state(gstreamer::State::Paused);
            let _ = self
                .pipeline
                .state(Some(gstreamer::ClockTime::from_seconds(5)));
            let _ = self.pipeline.seek_simple(
                gstreamer::SeekFlags::FLUSH | gstreamer::SeekFlags::ACCURATE,
                gstreamer::ClockTime::from_mseconds(start_ms),
            );
        }

        self.pipeline.set_state(gstreamer::State::Playing)?;

        let pipeline_clone = self.pipeline.clone();
        let sink_clone_eos = sink_arc.clone();
        thread::spawn(move || {
            let bus = pipeline_clone.bus().unwrap();
            for msg in bus.iter_timed(gstreamer::ClockTime::NONE) {
                use gstreamer::MessageView;
                match msg.view() {
                    MessageView::Eos(..) => {
                        let _ = sink_clone_eos.add(ExtractorEvent::Finished);
                        break;
                    }
                    MessageView::Error(err) => {
                        let _ = sink_clone_eos.add(ExtractorEvent::Error(err.error().to_string()));
                        break;
                    }
                    _ => (),
                }
            }
            let _ = pipeline_clone.set_state(gstreamer::State::Null);
        });

        Ok(())
    }

    pub fn stop(&self) -> Result<()> {
        self.pipeline.set_state(gstreamer::State::Null)?;
        Ok(())
    }
}
