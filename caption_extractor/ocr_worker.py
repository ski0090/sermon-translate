import sys
import os
import json
import base64
import logging
import cv2
import numpy as np

# CUDA DLL을 찾을 수 있도록 PATH에 CUDA bin 폴더를 추가합니다
# (Windows에서 paddlepaddle-gpu가 요구하는 설정)
_cuda_candidate_dirs = [
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\bin",
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin",
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.6\bin",
]
for _cuda_dir in _cuda_candidate_dirs:
    if os.path.isdir(_cuda_dir) and _cuda_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _cuda_dir + os.pathsep + os.environ.get("PATH", "")
        print(f"[OCR Worker] Added CUDA path: {_cuda_dir}", file=sys.stderr, flush=True)
        break

# Suppress PaddleOCR debug logs
logging.getLogger('ppocr').setLevel(logging.ERROR)


def preprocess_image(img: np.ndarray) -> np.ndarray:
    """
    OCR 정확도 향상을 위한 이미지 전처리 파이프라인.

    1. 업스케일: 저해상도 자막 크롭 이미지를 2배 확대하여 글자 선명도 향상
    2. 그레이스케일 변환
    3. 노이즈 제거 (fastNlMeansDenoising)
    4. CLAHE(Contrast Limited Adaptive Histogram Equalization)로 대비 향상
    5. 자막 배경 밝기 기반 자동 반전 (어두운 배경인 경우)
    6. 적응형 이진화 (Adaptive Thresholding) → 3채널 RGB로 복원 후 반환
       PaddleOCR은 컬러 이미지를 기대하므로 최종적으로 BGR 3채널로 반환합니다.
    """
    # 1. 업스케일 (2배)
    h, w = img.shape[:2]
    if h < 80 or w < 200:
        # 해상도가 매우 낮은 경우 3배 확대
        scale = 3.0
    else:
        scale = 2.0
    img_up = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 2. 그레이스케일 변환
    gray = cv2.cvtColor(img_up, cv2.COLOR_BGR2GRAY)

    # 3. 노이즈 제거
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # 4. CLAHE 대비 향상
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # 5. 배경 밝기 분석 → 어두운 배경이면 반전
    mean_brightness = float(np.mean(enhanced))
    if mean_brightness < 127:
        enhanced = cv2.bitwise_not(enhanced)

    # 6. 적응형 이진화
    binary = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=8,
    )

    # 모폴로지 클로징으로 글자 내부 구멍 메우기
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # PaddleOCR은 BGR 3채널 이미지를 기대하므로 변환
    result_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    return result_bgr


# 신뢰도 최소 임계값: 이 값 미만인 인식 결과는 무시합니다
MIN_CONFIDENCE = 0.6


def main():
    try:
        import paddle
        from paddleocr import PaddleOCR

        # GPU 사용 여부 확인 및 로그 출력 (stderr로)
        if paddle.device.is_compiled_with_cuda():
            print("[OCR Worker] GPU mode (CUDA detected)", file=sys.stderr, flush=True)
        else:
            print("[OCR Worker] CPU mode (no CUDA)", file=sys.stderr, flush=True)

        # PaddleOCR 초기화 - 정확도 최적화 파라미터 적용
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='korean',
            use_gpu=True,
            show_log=False,
            # 텍스트 감지 관련
            det_db_thresh=0.3,          # 픽셀 수준 감지 임계값 (낮을수록 민감)
            det_db_box_thresh=0.5,      # 박스 신뢰도 임계값
            det_db_score_mode='slow',   # 정확한 점수 계산 방식 ('slow' > 'fast')
            use_dilation=True,          # 텍스트 영역 팽창으로 인접 글자 연결 개선
            # 텍스트 인식 관련
            rec_batch_num=6,            # 배치 인식 수
            max_batch_size=10,
        )
        print("WORKER_READY", flush=True)
    except Exception as e:
        print(f"INIT_ERROR: {str(e)}", flush=True)
        sys.exit(1)

    # Listen on stdin for JSON requests
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            b64_data = req.get("image_base64", "")
            if not b64_data:
                print(json.dumps({"code": 101, "msg": "No image_base64 provided"}), flush=True)
                continue

            # Decode base64 PNG back to image array
            img_bytes = base64.b64decode(b64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                print(json.dumps({"code": 102, "msg": "Failed to decode image"}), flush=True)
                continue

            # 전처리 적용
            preprocessed = preprocess_image(img)

            # Perform OCR extraction
            result = ocr.ocr(preprocessed, cls=True)

            data = []
            if result and result[0]:
                for line_res in result[0]:
                    box = line_res[0]
                    text = line_res[1][0]
                    score = line_res[1][1]

                    # 낮은 신뢰도 결과 필터링
                    if score < MIN_CONFIDENCE:
                        continue

                    data.append({
                        "box": [
                            [int(box[0][0]), int(box[0][1])],
                            [int(box[1][0]), int(box[1][1])],
                            [int(box[2][0]), int(box[2][1])],
                            [int(box[3][0]), int(box[3][1])]
                        ],
                        "text": text,
                        "score": float(score)
                    })

            # Respond to stdout exactly mimicking PaddleOCR-json schema
            response = {"code": 100, "data": data}
            print(json.dumps(response, ensure_ascii=False), flush=True)

        except Exception as e:
            import traceback
            print(f"WORKER_ERROR: {str(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"code": 500, "msg": str(e)}), flush=True)


if __name__ == "__main__":
    main()
