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

def main():
    try:
        import paddle
        from paddleocr import PaddleOCR

        # GPU 사용 여부 확인 및 로그 출력 (stderr로)
        if paddle.device.is_compiled_with_cuda():
            print("[OCR Worker] GPU mode (CUDA detected)", file=sys.stderr, flush=True)
        else:
            print("[OCR Worker] CPU mode (no CUDA)", file=sys.stderr, flush=True)

        # PaddleOCR 2.x API (paddlepaddle-gpu 2.6.2 호환)
        ocr = PaddleOCR(use_angle_cls=True, lang='korean', use_gpu=True, show_log=False)
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

            # Perform OCR extraction
            result = ocr.ocr(img, cls=True)

            data = []
            if result and result[0]:
                for line_res in result[0]:
                    box = line_res[0]
                    text = line_res[1][0]
                    score = line_res[1][1]
                    
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
            print(json.dumps(response), flush=True)

        except Exception as e:
            import traceback
            print(f"WORKER_ERROR: {str(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"code": 500, "msg": str(e)}), flush=True)

if __name__ == "__main__":
    main()
