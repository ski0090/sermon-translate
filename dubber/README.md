# 설교 영상 한국어 더빙 (dubber)

외국어 설교 영상에 입혀진 한국어 자막을 읽어 한국어 음성으로 만들고, 그 음성을 입힌 영상을 만드는 프로그램입니다.
기획 문서는 `reports/issue-0-1.md`에 있습니다.

## 처리 흐름

1. 영상 불러오기: 영상 파일을 고르면 프로젝트가 만들어집니다.
2. 자막 읽기: 자막 영역의 그림이 바뀌는 순간을 PC 안에서 찾고(ffmpeg + numpy), 자막 그림을 25장씩 이어 붙여 AI 명령줄 도구(claude)에 읽힙니다. 영상 자체는 외부로 보내지 않습니다.
3. 정리와 검수: 자막을 문장으로 합치고 AI가 글자를 교정합니다. 자막 그림과 읽은 글을 나란히 보며 고치고, 잘라낼 구간(찬양, 제목 화면 등)을 타임라인에서 지정합니다.
4. 음성: Supertonic(CPU, ONNX)으로 문장마다 한국어 음성을 만듭니다. 목소리 F1~F5, M1~M5.
5. 내보내기: 잘라내기 구간을 뺀 영상에 음성을 입힙니다. 영상(mp4), 오디오(mp3), 자막(srt), 텍스트(txt).

## 필요한 것

- Windows, Python 3.13 (`python` 명령), ffmpeg/ffprobe (PATH)
- Claude Code CLI (`claude`) 로그인 상태. 설정에서 `codex`로 바꿀 수 있습니다.
- Python 패키지: `pip install pillow numpy onnxruntime supertonic`
  첫 실행 때 Supertonic 모델(약 300MB)을 내려받습니다.
- GPU는 필요 없습니다. 음성 합성은 CPU에서 문장당 약 5초가 걸립니다(설교 한 편 700문장에 약 1시간, 설정의 "빠름" 품질은 약 절반).
  자막 읽기는 25장 묶음당 약 30초이고 4묶음을 동시에 보내므로 1,000장에 약 6분입니다.

## 실행

```bash
python dubber/server.py
```

브라우저에서 http://127.0.0.1:8765 가 열립니다. 프로젝트는 `dubber/projects/<영상 이름>/`에 저장되고, 결과 파일은 그 아래 `out/`에 만들어집니다.

## 명령줄로 단계 실행

```bash
python dubber/project.py new "<영상 경로>"
python dubber/project.py scan "<프로젝트 폴더>"
python dubber/project.py read "<프로젝트 폴더>"
python dubber/project.py sentences "<프로젝트 폴더>"
python dubber/project.py correct "<프로젝트 폴더>"
```

## 모듈

| 파일 | 역할 |
|---|---|
| `captions.py` | 자막 영역 자동 감지, 자막 바뀜 감지, 가사(노란 글씨) 판정, 자막 없음 구간 |
| `ai.py` | 자막 그림 묶음 만들기, AI 읽기(캐시, 반으로 나눠 재시도), 글자 교정 |
| `sentences.py` | 문장 합치기 규칙, 성경 약어 풀어 읽기, 읽기 사전 |
| `tts.py` | Supertonic 합성, 캐시, 목소리 예시 |
| `export.py` | 음성 배치(1.2배속 한도, 밀림, 고정 지점), 더빙 트랙, ffmpeg 내보내기 |
| `project.py` | 프로젝트 저장소와 문장 편집, 잘라내기 구간 |
| `server.py` | 로컬 웹 서버와 API (표준 라이브러리) |
| `static/index.html` | 화면 |

`caption_extractor/`는 이전 구현(Flutter + Rust + PaddleOCR)이며 더 이상 쓰지 않습니다.
