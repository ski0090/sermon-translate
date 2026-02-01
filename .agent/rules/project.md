---
trigger: always_on
---

# caption_extractor

영상의 자막을 추출하는 프로그램입니다.

## Flutter 프로젝트

- UI는 영상을 재생하며 추출된 자막을 보여줍니다.
- 사용자가 자막 추출 영역(ROI: Region of Interest)을 설정할 수 있는 인터페이스를 제공합니다.
- 추출 진행 상태(진행률, 현재 프레임 등)를 시각적으로 표시합니다.
- 자막 정보는 JSON 형태로 저장 및 관리합니다.

## Rust 프로젝트

- **GStreamer**: 영상을 지정된 간격으로 탐색(Seek)하고 프레임을 캡처합니다.
- **OCR (Optical Character Recognition)**:
  - 라이브러리: `ocrs` 또는 `tesseract` (환경에 맞춰 선택).
  - 전처리: 영상 프레임을 Grayscale로 변환하고 이진화(Thresholding)하여 인식률을 높입니다.
- **데이터 흐름**: `flutter_rust_bridge`를 통해 Flutter와 데이터를 주고받습니다.

## 데이터 구조 (JSON)

추출된 자막은 다음과 같은 형식으로 저장됩니다:

```json
[
  {
    "start_time_ms": 1000,
    "end_time_ms": 3000,
    "text": "안녕하세요, 자막 추출 테스트입니다.",
    "confidence": 0.98,
    "region": {
      "x": 100,
      "y": 500,
      "width": 600,
      "height": 100
    }
  }
]
```

## 개발 환경 요구사항

- **Windows**: GStreamer 브런타임 및 개발 SDK 설치 필요.
- **Rust**: `cargo-expand` 및 `flutter_rust_bridge_codegen` 설치.
- **Flutter**: FFmpeg 또는 관련 코덱 플러그인 (필요 시).