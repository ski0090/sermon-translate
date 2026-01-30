---
trigger: always_on
---

# caption_extractor

영상의 자막을 추출하는 프로그램입니다.

## Flutter 프로젝트

- UI는 영상을 재생하며 추출된 자막을 보여줍니다.
- 영상은 자막이 영상과 함께 디코딩된 형태입니다.
- 자막 정보는 json 형태로 저장합니다.

## Rust 프로젝트

- gstreamer로 영상을 UI서 받은 간격으로 재생합니다.
- OCR을 통해 영상에서 자막을 추출합니다.
