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
