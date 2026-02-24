use anyhow::{anyhow, Result};
use image::{DynamicImage, ImageFormat, RgbaImage};
use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Cursor, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

#[derive(Serialize)]
struct OcrRequest {
    image_base64: String,
}

#[derive(Deserialize, Debug)]
struct OcrResponse {
    code: i32,
    data: Option<Vec<OcrTextData>>,
}

#[derive(Deserialize, Debug)]
struct OcrTextData {
    #[serde(rename = "box")]
    box_pts: [[i32; 2]; 4], // PaddleOCR-JSON returns this shape
    score: f32,
    text: String,
}

pub struct OcrEngine {
    process: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

impl OcrEngine {
    pub fn new(_lang: &str) -> Result<Self> {
        // ocr_worker.py 를 파이썬으로 백그라운드 구동합니다.
        // Windows MS Store stub이 PATH에 올라와있어 직접 경로를 지정합니다.
        let python_paths = [
            r"C:\Users\ski00\AppData\Local\Programs\Python\Python310\python.exe",
            r"C:\Python310\python.exe",
            "python3",
            "python",
        ];

        // 존재하는 첫 번째 python 경로 사용
        let python_exe = python_paths
            .iter()
            .find(|p| std::path::Path::new(p).exists() || !p.contains('\\'))
            .copied()
            .unwrap_or("python");

        // ocr_worker.py의 절대 경로: Flutter 앱 실행 디렉토리 기준으로 찾습니다
        // 일반적으로 caption_extractor/ 폴더에 있습니다
        let worker_paths = [
            r"ocr_worker.py",
            r"..\ocr_worker.py",
            r"..\..\ocr_worker.py",
        ];

        let worker_py = worker_paths
            .iter()
            .find(|p| std::path::Path::new(p).exists())
            .copied()
            .unwrap_or("ocr_worker.py");

        let mut process_cmd = Command::new(python_exe);
        process_cmd.arg("-u"); // Unbuffered output (flush=True 없어도 즉시 전달)
        process_cmd.arg(worker_py);
        process_cmd.env("PYTHONIOENCODING", "utf-8");
        process_cmd.env("PYTHONUNBUFFERED", "1");

        let mut process = process_cmd
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            // Python stderr 는 콘솔에 출력되게 둡니다 (에러 확인용)
            .spawn()
            .map_err(|e| anyhow!("Failed to start python ocr_worker.py: {}", e))?;

        let stdin = process
            .stdin
            .take()
            .ok_or_else(|| anyhow!("Failed to open python stdin"))?;
        let stdout = process
            .stdout
            .take()
            .ok_or_else(|| anyhow!("Failed to open python stdout"))?;

        let mut reader = BufReader::new(stdout);
        let mut line = String::new();

        // 파이썬 워커가 GPU 모델을 메모리에 올리고 "WORKER_READY"를 보낼 때까지 대기
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => return Err(anyhow!("Python worker stopped unexpectedly during init")),
                Ok(_) => {
                    let trimmed = line.trim();
                    println!("[Python Worker Init] {}", trimmed);
                    if trimmed == "WORKER_READY" {
                        break;
                    } else if trimmed.starts_with("INIT_ERROR") {
                        return Err(anyhow!("Python worker initialization failed: {}", trimmed));
                    }
                }
                Err(e) => return Err(anyhow!("Failed to read from python worker: {}", e)),
            }
        }

        Ok(Self {
            process,
            stdin,
            stdout: reader,
        })
    }

    pub fn extract_text(
        &mut self,
        rgba_data: &[u8],
        width: i32,
        height: i32,
    ) -> Result<(String, f32)> {
        if rgba_data.is_empty() {
            return Ok((String::new(), 0.0));
        }

        let img = RgbaImage::from_raw(width as u32, height as u32, rgba_data.to_vec())
            .ok_or_else(|| anyhow!("Failed to create image from raw bytes"))?;

        let b64 = Self::image_to_base64(&img)?;

        let req = OcrRequest { image_base64: b64 };
        let req_json = serde_json::to_string(&req)?;

        if let Err(e) = writeln!(self.stdin, "{}", req_json) {
            return Err(anyhow!("Failed to write to PaddleOCR stdin: {}", e));
        }

        // 계속해서 stdout 라인을 읽으면서 올바른 JSON 응답이 나올 때까지 대기합니다.
        // PaddleOCR-json은 추론 초기화 시 여러 줄의 로그를 stdout으로 출력할 수 있습니다.
        loop {
            let mut chunk = String::new();
            match self.stdout.read_line(&mut chunk) {
                Ok(0) => break, // EOF
                Ok(_) => {
                    let trimmed = chunk.trim();
                    if trimmed.is_empty() {
                        continue;
                    }

                    // JSON 파싱 시도
                    if let Ok(res) = serde_json::from_str::<OcrResponse>(trimmed) {
                        if res.code == 100 && res.data.is_some() {
                            let texts = res.data.unwrap();
                            let mut full_text = String::new();
                            let mut sum_conf = 0.0;
                            let mut count = 0;

                            for item in texts {
                                full_text.push_str(&item.text);
                                full_text.push(' ');
                                sum_conf += item.score;
                                count += 1;
                            }

                            let avg_conf = if count > 0 {
                                (sum_conf / count as f32) as f32
                            } else {
                                0.0
                            };
                            return Ok((full_text.trim().to_string(), avg_conf));
                        }
                        return Ok((String::new(), 0.0));
                    }
                }
                Err(e) => {
                    return Err(anyhow!("Failed to read stdout from PaddleOCR: {}", e));
                }
            }
        }

        Ok((String::new(), 0.0))
    }

    pub fn auto_detect_roi(
        &mut self,
        rgba_data: &[u8],
        width: i32,
        height: i32,
    ) -> Result<Option<crate::api::models::Roi>> {
        if rgba_data.is_empty() {
            return Ok(None);
        }

        let img = RgbaImage::from_raw(width as u32, height as u32, rgba_data.to_vec())
            .ok_or_else(|| anyhow!("Failed to create image from raw bytes"))?;

        let b64 = Self::image_to_base64(&img)?;

        let req = OcrRequest { image_base64: b64 };
        let req_json = serde_json::to_string(&req)?;

        if let Err(e) = writeln!(self.stdin, "{}", req_json) {
            return Err(anyhow!("Failed to write to PaddleOCR stdin: {}", e));
        }

        loop {
            let mut chunk = String::new();
            match self.stdout.read_line(&mut chunk) {
                Ok(0) => break, // EOF
                Ok(_) => {
                    let trimmed = chunk.trim();
                    if trimmed.is_empty() {
                        continue;
                    }

                    if let Ok(res) = serde_json::from_str::<OcrResponse>(trimmed) {
                        if res.code == 100 && res.data.is_some() {
                            let texts = res.data.unwrap();
                            if texts.is_empty() {
                                return Ok(None);
                            }

                            let mut min_x = i32::MAX;
                            let mut min_y = i32::MAX;
                            let mut max_x = 0;
                            let mut max_y = 0;

                            for item in texts {
                                let box_pts = item.box_pts;
                                for pt in box_pts {
                                    let x = pt[0];
                                    let y = pt[1];

                                    if y < (height as f64 * 0.40).round() as i32 {
                                        continue;
                                    }

                                    let h_approx = box_pts[3][1] - box_pts[0][1];
                                    if h_approx > (height as f64 * 0.20).round() as i32 {
                                        continue;
                                    }

                                    if x < min_x {
                                        min_x = x;
                                    }
                                    if y < min_y {
                                        min_y = y;
                                    }
                                    if x > max_x {
                                        max_x = x;
                                    }
                                    if y > max_y {
                                        max_y = y;
                                    }
                                }
                            }

                            if min_x == i32::MAX {
                                return Ok(None);
                            }

                            let padding = 10;
                            let mut final_x = min_x - padding;
                            let mut final_y = min_y - padding;
                            let mut final_w = (max_x - min_x) + padding * 2;
                            let mut final_h = (max_y - min_y) + padding * 2;

                            final_x = final_x.clamp(0, width);
                            final_y = final_y.clamp(0, height);
                            final_w = final_w.clamp(1, width - final_x);
                            final_h = final_h.clamp(1, height - final_y);

                            return Ok(Some(crate::api::models::Roi {
                                x: final_x,
                                y: final_y,
                                width: final_w,
                                height: final_h,
                                start_time_ms: 0,
                                end_time_ms: 0,
                            }));
                        }
                        return Ok(None);
                    }
                }
                Err(e) => {
                    return Err(anyhow!(
                        "Failed to read stdout from PaddleOCR in ROI detect: {}",
                        e
                    ));
                }
            }
        }

        Ok(None)
    }

    fn image_to_base64(img: &RgbaImage) -> Result<String> {
        use base64::{engine::general_purpose, Engine as _};
        let dynamic_img = DynamicImage::ImageRgba8(img.clone());
        let mut png_data = Vec::new();
        dynamic_img
            .write_to(&mut Cursor::new(&mut png_data), ImageFormat::Png)
            .map_err(|e| anyhow!("Failed to encode PNG for OCR: {}", e))?;

        Ok(general_purpose::STANDARD.encode(&png_data))
    }
}

impl Drop for OcrEngine {
    fn drop(&mut self) {
        let _ = self.process.kill();
        let _ = self.process.wait();
    }
}
