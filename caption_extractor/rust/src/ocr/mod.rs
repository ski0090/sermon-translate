use anyhow::{anyhow, Result};
use image::{DynamicImage, ImageFormat, RgbaImage};

use leptess::{LepTess, Variable};
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
                paths.push(
                    std::path::Path::new(&vcpkg_root)
                        .join("installed")
                        .join("x64-windows")
                        .join("share")
                        .join("tessdata"),
                );
            }

            // 일반적인 설치 경로 추가
            paths.push(std::path::PathBuf::from(
                r"C:\Program Files\Tesseract-OCR\tessdata",
            ));
            paths.push(std::path::PathBuf::from(r"C:\tessdata"));

            for path in paths {
                if path.exists() {
                    println!("Setting TESSDATA_PREFIX to: {:?}", path);
                    std::env::set_var("TESSDATA_PREFIX", path.to_str().unwrap());
                    break;
                }
            }
        }

        let mut lt = LepTess::new(None, lang).map_err(|e| {
            anyhow!(
                "Failed to initialize Tesseract (lang: {}): {}. TESSDATA_PREFIX check required.",
                lang,
                e
            )
        })?;

        // PSM_SINGLE_BLOCK (6) 또는 PSM_SINGLE_LINE (7) 설정
        // 자막은 보통 한 블록이므로 6이 적성
        lt.set_variable(Variable::TesseditPagesegMode, "6").ok();

        Ok(Self { lt })
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

        // 1. 이미지 로드
        let img = RgbaImage::from_raw(width as u32, height as u32, rgba_data.to_vec())
            .ok_or_else(|| anyhow!("Failed to create image from raw bytes"))?;

        let (png_data, _) = Self::preprocess_image(&img)?;

        self.lt
            .set_image_from_mem(&png_data)
            .map_err(|e| anyhow!("Failed to set image for OCR: {}", e))?;

        // 일반 텍스트 추출 모드로 원복
        self.lt
            .set_variable(Variable::TesseditPagesegMode, "6")
            .ok();

        let text = self
            .lt
            .get_utf8_text()
            .map_err(|e| anyhow!("Failed to get text: {}", e))?;

        let confidence = self.lt.mean_text_conf() as f32 / 100.0;

        Ok((text.trim().to_string(), confidence))
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

        let (png_data, scale_factor) = Self::preprocess_image(&img)?;

        self.lt
            .set_image_from_mem(&png_data)
            .map_err(|e| anyhow!("Failed to set image for OCR: {}", e))?;

        // 텍스트 블록 전체를 잡기 위한 모드 설정 (PSM_SPARSE_TEXT)
        self.lt
            .set_variable(Variable::TesseditPagesegMode, "11")
            .ok();

        let _ = self.lt.recognize();

        let boxes = self
            .lt
            .get_component_boxes(leptess::capi::TessPageIteratorLevel_RIL_TEXTLINE, true);

        if let Some(boxa) = boxes {
            if boxa.get_n() == 0 {
                return Ok(None);
            }

            let mut min_x = i32::MAX;
            let mut min_y = i32::MAX;
            let mut max_x = 0;
            let mut max_y = 0;

            let scaled_height = height as f32 * scale_factor;

            for b in &boxa {
                let geo = b.get_geometry();
                let x = geo.x;
                let y = geo.y;
                let w = geo.w;
                let h = geo.h;

                // 휴리스틱 필터링: 자막 영역만 정확히 잡기 위함
                // 1. 텍스트 라인의 높이가 화면 높이의 20%를 초과하면 배경 노이즈나 인물 형태일 가능성이 높으므로 무시
                if h as f32 > scaled_height * 0.20 {
                    continue;
                }

                // 2. 자막은 주로 하단에 위치하므로 상단 40%에 위치한 텍스트(방송사 로고 등)는 무시
                if (y as f32) < scaled_height * 0.40 {
                    continue;
                }

                if x < min_x {
                    min_x = x;
                }
                if y < min_y {
                    min_y = y;
                }
                if x + w > max_x {
                    max_x = x + w;
                }
                if y + h > max_y {
                    max_y = y + h;
                }
            }

            if min_x == i32::MAX {
                return Ok(None);
            }

            // 스케일 역 변환
            let inv_scale = 1.0 / scale_factor;
            let padding = 10.0;

            let mut final_x = (min_x as f32 * inv_scale - padding) as i32;
            let mut final_y = (min_y as f32 * inv_scale - padding) as i32;
            let mut final_w = ((max_x - min_x) as f32 * inv_scale + padding * 2.0) as i32;
            let mut final_h = ((max_y - min_y) as f32 * inv_scale + padding * 2.0) as i32;

            // bounds check
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

        Ok(None)
    }

    fn preprocess_image(img: &RgbaImage) -> Result<(Vec<u8>, f32)> {
        let dynamic_img = DynamicImage::ImageRgba8(img.clone());

        // 2. Grayscale 변환
        let gray_img = dynamic_img.to_luma8();

        // 3. 이미지 확대 (인식률 향상을 위해 2배 확대)
        let (w, h) = gray_img.dimensions();
        let resized_img = image::imageops::resize(
            &gray_img,
            w * 2,
            h * 2,
            image::imageops::FilterType::Lanczos3,
        );

        // 4. 명암 대비 정규화(Contrast Stretching) 및 밝기 반전
        // 자막은 보통 영상 내에서 가장 밝은 색을 띠고 어두운 테두리를 가집니다.
        // 강제로 이진화(Otsu 등)를 할 경우 배경이 글자와 뭉칠 수 있으므로,
        // 전체 밝기 분포를 상위/하위 1% 기준으로 정규화한 뒤 반전하여 Tesseract 자체 이진화를 활용합니다.
        let mut histogram = [0usize; 256];
        let mut total_pixels = 0;
        for pixel in resized_img.pixels() {
            histogram[pixel.0[0] as usize] += 1;
            total_pixels += 1;
        }

        let mut sum = 0;
        let mut min_val = 0;
        for i in 0..=255 {
            sum += histogram[i];
            if sum > total_pixels / 100 {
                // 1%
                min_val = i as u8;
                break;
            }
        }

        let mut sum = 0;
        let mut max_val = 255;
        for i in (0..=255).rev() {
            sum += histogram[i];
            if sum > total_pixels / 100 {
                // 99%
                max_val = i as u8;
                break;
            }
        }

        let mut binary_img = resized_img;
        let range = (max_val.saturating_sub(min_val)).max(1) as f32;

        for pixel in binary_img.pixels_mut() {
            let p_val = pixel.0[0];
            let clamped = p_val.clamp(min_val, max_val);
            let normalized = (clamped - min_val) as f32 / range * 255.0;
            // 밝은 글씨가 Tesseract가 잘 인식하는 검은 글씨(0)가 되도록 반전
            pixel.0[0] = 255 - (normalized as u8);
        }

        let mut png_data = Vec::new();
        let final_img = DynamicImage::ImageLuma8(binary_img);
        final_img
            .write_to(&mut Cursor::new(&mut png_data), ImageFormat::Png)
            .map_err(|e| anyhow!("Failed to encode PNG for OCR: {}", e))?;

        Ok((png_data, 2.0))
    }
}
