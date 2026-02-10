use anyhow::{Result, anyhow};
use leptess::{LepTess};
use image::{RgbaImage, DynamicImage, ImageFormat};
use std::io::Cursor;

pub struct OcrEngine {
    lt: LepTess,
}

impl OcrEngine {
    pub fn new(lang: &str) -> Result<Self> {
        // TESSDATA_PREFIX 자동 설정 시도
        if std::env::var("TESSDATA_PREFIX").is_err() {
            let mut paths = Vec::new();

            if let Ok(vcpkg_root) = std::env::var("VCPKG_ROOT") {
                paths.push(std::path::Path::new(&vcpkg_root).join("installed").join("x64-windows").join("share").join("tessdata"));
            }
            
            // 일반적인 설치 경로 추가
            paths.push(std::path::PathBuf::from(r"C:\Program Files\Tesseract-OCR\tessdata"));
            paths.push(std::path::PathBuf::from(r"C:\tessdata"));

            for path in paths {
                if path.exists() {
                    println!("Setting TESSDATA_PREFIX to: {:?}", path);
                    std::env::set_var("TESSDATA_PREFIX", path.to_str().unwrap());
                    break;
                }
            }
        }

        let lt = LepTess::new(None, lang)
            .map_err(|e| anyhow!("Failed to initialize Tesseract (lang: {}): {}. TESSDATA_PREFIX check required.", lang, e))?;
        
        Ok(Self { lt })
    }

    pub fn extract_text(&mut self, rgba_data: &[u8], width: i32, height: i32) -> Result<(String, f32)> {
        if rgba_data.is_empty() {
            return Ok((String::new(), 0.0));
        }

        // leptess 0.14의 set_image_from_mem은 압축된 이미지 데이터를 기대함.
        // RGBA 생데이터를 PNG로 인코딩하여 전달.
        let img = RgbaImage::from_raw(width as u32, height as u32, rgba_data.to_vec())
            .ok_or_else(|| anyhow!("Failed to create image from raw bytes"))?;
        
        let dynamic_img = DynamicImage::ImageRgba8(img);
        let mut png_data = Vec::new();
        dynamic_img.write_to(&mut Cursor::new(&mut png_data), ImageFormat::Png)
            .map_err(|e| anyhow!("Failed to encode PNG for OCR: {}", e))?;

        self.lt.set_image_from_mem(&png_data)
            .map_err(|e| anyhow!("Failed to set image for OCR: {}", e))?;
        
        let text = self.lt.get_utf8_text()
            .map_err(|e| anyhow!("Failed to get text: {}", e))?;
        
        let confidence = self.lt.mean_text_conf() as f32 / 100.0;
        
        Ok((text.trim().to_string(), confidence))
    }
}
