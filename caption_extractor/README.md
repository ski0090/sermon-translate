# caption_extractor

OCR 기술을 이용한 동영상 자막 추출 프로그램입니다.  
GStreamer 기반 영상 처리 + **Python PaddleOCR GPU** 백엔드를 통해 고속 한글/영어 자막을 추출합니다.

## 주요 기능

- GStreamer 파이프라인을 통한 실시간 영상 스트리밍
- ROI(Region of Interest) 선택 및 크롭 처리 (미설정 시 하단 30% 자동 적용)
- 0.5초 간격 자막 추출 및 타임라인 표시
- JSON 형식으로 자막 저장
- **GPU 가속** CUDA 지원 (NVIDIA GPU 환경)

---

## 개발 환경 요구사항

### 1. GStreamer 설치 (Windows)

[GStreamer 공식 사이트](https://gstreamer.freedesktop.org/download/)에서 다음 두 가지를 설치합니다:
- **MSVC 64-bit runtime installer**
- **MSVC 64-bit development installer**

설치 타입은 `Complete`를 선택하거나 `gst-plugins-base`, `gst-plugins-good`, `gst-libav`가 포함되도록 선택합니다.

### 2. Python 3.10 + PaddleOCR (GPU 가속 OCR 백엔드)

OCR 엔진으로 Python 3.10 + PaddleOCR을 사용합니다. Rust 백엔드가 `ocr_worker.py`를 자동으로 실행하여 통신합니다.

#### Python 3.10 설치
[Python 3.10 공식 다운로드](https://www.python.org/downloads/release/python-31011/)에서 설치합니다.

#### 필수 Python 라이브러리 설치

```powershell
# GPU 없는 환경 (CPU 모드)
pip install paddlepaddle==2.6.2
pip install paddleocr==2.9.1

# GPU 환경 (CUDA 12.x, 권장)
pip install paddlepaddle-gpu==2.6.2.post120 --index-url https://www.paddlepaddle.org.cn/packages/stable/cu120/
pip install paddleocr==2.9.1
```

> [!IMPORTANT]
> `paddlepaddle-gpu` 버전은 반드시 설치된 CUDA 버전과 맞아야 합니다.
> - CUDA 11.8 → `paddlepaddle-gpu==2.6.2`
> - CUDA 12.x → `paddlepaddle-gpu==2.6.2.post120`
>
> 현재 CUDA 버전 확인: `nvcc --version`

#### cuDNN 설치 (GPU 모드 필수)
[NVIDIA cuDNN 다운로드](https://developer.nvidia.com/cudnn)에서 CUDA 버전에 맞는 cuDNN을 설치합니다.

### 3. NVIDIA CUDA Toolkit (GPU 모드, 선택)

GPU 가속을 사용하려면 [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)을 설치합니다.

| Component | 버전 |
|---|---|
| CUDA Toolkit | 12.x (권장) 또는 11.8 |
| cuDNN | CUDA 버전에 맞는 버전 |
| paddlepaddle-gpu | 2.6.2.post120 (CUDA 12.x) |

### 4. Rust 및 Flutter

- **Rust** (MSRV 1.70+)
- **Flutter SDK** (Channel stable)
- `flutter_rust_bridge_codegen`: `cargo install flutter_rust_bridge_codegen`

---

## 빌드 및 실행

### Backend (Rust) 빌드

```powershell
cd rust
cargo build
```

### 코드 생성 (flutter_rust_bridge)

```powershell
flutter_rust_bridge_codegen generate
```

### 앱 실행

```powershell
flutter run -d windows
```

> [!NOTE]
> 앱 실행 시 Rust 백엔드가 자동으로 `ocr_worker.py`를 찾아 Python 서브프로세스로 실행합니다.  
> `ocr_worker.py`는 프로젝트 루트(`caption_extractor/`)에 위치해야 합니다.

---

## OCR 워커 경로 탐색 순서

Rust 백엔드는 다음 순서로 Python 실행 파일을 탐색합니다:
1. `C:\Users\<사용자명>\AppData\Local\Programs\Python\Python310\python.exe`
2. `C:\Python310\python.exe`
3. `python3` (시스템 PATH)
4. `python` (시스템 PATH)

---

## 데이터 구조 (JSON 출력)

```json
[
  {
    "start_time_ms": 1000,
    "end_time_ms": 3000,
    "text": "추출된 자막 텍스트",
    "confidence": 0.95,
    "region": { "x": 0, "y": 756, "width": 1280, "height": 324 }
  }
]
```
