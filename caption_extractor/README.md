# caption_extractor

OCR 기술을 이용한 동영상 자막 추출 프로그램입니다. GStreamer를 통한 영상 처리와 Tesseract OCR을 활용합니다.

## 개발 환경 요구사항

### 1. GStreamer 설치 (Windows)
- [GStreamer 공식 사이트](https://gstreamer.freedesktop.org/download/)에서 다음 두 가지를 설치해야 합니다:
  - **MSVC 64-bit runtime installer**
  - **MSVC 64-bit development installer**
- 설치 시 `Complete` 방식을 선택하거나, `gst-plugins-base`, `gst-plugins-good`, `gst-libav` 등이 포함되도록 확인하십시오.

### 2. Tesseract OCR 설치 (두 방식 중 선택)

프로그램은 실행 시 자동으로 `tessdata` 경로를 탐색합니다. 다음 중 하나의 방식을 선택하여 설치하십시오.

#### 방식 A: vcpkg를 통한 설치 (권장)
- Tesseract 설치: `.\vcpkg install tesseract:x64-windows`
- **필수 환경 변수**:
  - `VCPKG_ROOT`: vcpkg 설치 경로 (예: `C:\codes\vcpkg`)
  - `VCPKGRS_DYNAMIC`: `true`

#### 방식 B: 공식 설치 파일을 통한 설치
- [Tesseract OCR Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki)를 통해 설치합니다.
- 설치 시 `Additional language data`에서 `Korean`을 선택하는 것을 권장합니다.

#### 환경 변수 자동 탐색 (TESSDATA_PREFIX)
`OcrEngine`은 다음 순서로 `tessdata` 폴더를 탐색하여 `TESSDATA_PREFIX`를 자동으로 설정합니다:
1. `VCPKG_ROOT` 하위의 `installed\x64-windows\share\tessdata`
2. `C:\Program Files\Tesseract-OCR\tessdata` (표준 설치 경로)
3. `C:\tessdata`

> [!TIP]
> 직접 `TESSDATA_PREFIX` 환경 변수를 설정하면 자동 탐색보다 우선적으로 적용됩니다.

### 3. Rust 및 Flutter
- Rust (MSRV 1.70+)
- Flutter SDK (Channel stable)
- `flutter_rust_bridge_codegen` 설치: `cargo install flutter_rust_bridge_codegen`

## 빌드 및 실행 방법

### Backend (Rust) 빌드 확인
Windows PowerShell에서 다음과 같이 환경 변수를 설정하고 빌드합니다:

```powershell
$env:VCPKG_ROOT = "C:\codes\vcpkg"
$env:VCPKGRS_DYNAMIC = "true"
$env:VCPKG_DEFAULT_TRIPLET = "x64-windows"

cd rust
cargo build
```

### 코드 생성 (FRB)
Flutter와 Rust 간의 브릿지 코드를 생성합니다:

```powershell
flutter_rust_bridge_codegen generate
```

### 실행 (Flutter)
```powershell
flutter run
```

## 주요 기능
- GStreamer 파이프라인을 통한 실시간 영상 스트리밍
- ROI(Region of Interest) 선택 및 크롭 처리
- 500ms 간격의 실시간 자막(KOR+ENG) 추출 및 전달
