# 코드와 모듈 설명

외국어 설교 영상에 입혀진 한국어 자막을 읽어 한국어 음성으로 만들고, 그 음성을 입힌 영상을 만드는 프로그램입니다.
기획 문서는 `reports/issue-0-1.md`에 있습니다.

## 처리 흐름

1. 영상 불러오기: 구글 드라이브(rclone)에서 영상을 고르면 PC로 내려받아 프로젝트가 만들어집니다.
2. 자막 읽기: 자막 영역의 그림이 바뀌는 순간을 PC 안에서 찾고(ffmpeg + numpy), 자막 그림을 25장씩 이어 붙여 AI 명령줄 도구(claude)에 읽힙니다. 영상 자체는 외부로 보내지 않습니다.
3. 정리와 검수: AI가 자막을 문장으로 묶고 글자를 고치고 읽는 글과 확인 필요를 붙입니다. 시간은 자막 번호로만 정하므로 AI가 틀려도 싱크는 깨지지 않습니다. 자막 그림과 읽은 글을 나란히 보며 고치고, 잘라낼 구간(찬양, 제목 화면 등)을 타임라인에서 지정합니다.
4. 음성: Supertonic(CPU, ONNX)으로 문장마다 한국어 음성을 만듭니다. 목소리 F1~F5, M1~M5.
5. 내보내기: 잘라내기 구간을 뺀 영상에 음성을 입힙니다. 영상(mp4), 오디오(mp3), 자막(srt), 텍스트(txt). 만든 파일은 구글 드라이브에 올립니다.
6. 쇼츠: Claude가 고른 30~60초 구간을 세로 영상으로 만듭니다. 더빙 음성에 맞춰 큰 자막을 새로 박고 강조 구절에 효과를 줍니다.

## 설치와 실행

설치, 실행(`python run.py`), 화면 사용 순서는 [README.md](README.md)에 있습니다.
프로젝트는 `projects/<영상 이름>/`에 저장되고, 결과 파일은 그 아래 `<영상 이름> 한국어 더빙/`에 만든 뒤 구글 드라이브의 원본 영상 폴더 아래 같은 이름의 폴더에 올립니다. 내보내기 중간 파일은 `work/`에 둡니다.

## 구조

```text
run.py      API 서버와 화면 서버를 함께 띄운다(python run.py)
backend/    API 서버: 작업과 데이터를 맡고 /api의 JSON과 파일만 내준다(헥사고날, 127.0.0.1:8766)
frontend/   화면: Vue 화면 파일을 내주고 /api는 API 서버로 넘긴다(FSD, 8765)
projects/   작업 데이터(프로젝트마다 project.json과 자막 그림·음성·결과 파일, _batch.json 같은 상태 파일)
```

브라우저는 화면 서버 하나(8765)에만 접속합니다. 화면은 받은 JSON으로 그리기만 하고, 일은 모두 API 서버가 합니다. API의 경로와 응답 모양이 둘 사이의 약속이며 `backend/dubber/adapters/inbound/http/api.py`에 모여 있습니다.

## API 서버 (backend/, 헥사고날)

```text
            입구(inbound)                       바깥(outbound)
  HTTP API ─┐                              ┌─ 파일(project.json, 상태 JSON)
  명령줄   ─┼─> application ──(ports)──> ─┼─ ffmpeg(영상 분석, 더빙, 쇼츠, 음성 영상)
            │        │                     ├─ claude·codex·agy 명령줄
            │        v                     ├─ Supertonic(음성 합성)
            │      domain                  ├─ rclone(구글 드라이브)
            │                              └─ 유튜브 API
  bootstrap.py: 어댑터를 만들어 유스케이스에 끼운다
```

- 의존은 안쪽으로만 향합니다: `domain` <- `ports` <- `application` <- `adapters` <- `bootstrap`. `domain`과 `application`은 바깥 라이브러리(numpy, PIL, 음성 엔진)와 프로세스·네트워크를 쓰지 않습니다. 이 규칙은 `backend/tests/test_layers.py`가 시험합니다.
- 바깥(ffmpeg, AI 도구, 드라이브 등)을 바꾸거나 시험용 가짜로 바꾸려면 포트를 구현한 어댑터를 만들어 `bootstrap.py`에서 끼웁니다.
- 환경 변수는 `config.py` 한곳에서 읽습니다.
- 진입점: `backend/main.py`(API 서버), `backend/cli.py`(명령줄 단계 실행). 시험: `python -m unittest discover -s backend/tests -t backend`

| 계층              | 파일                                                | 역할                                                                                                       |
| ----------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| domain            | `project.py`                                        | 프로젝트 엔티티: 자막·문장 편집(나누기, 합치기, 지우기), 잘라내기 구간, 설정, 출력 시간                    |
|                   | `sentences.py`                                      | 문장 합치기 규칙, 성경 약어 풀어 읽기, 읽기 사전                                                           |
|                   | `captions.py`                                       | 자막 영역 좌표 맞추기, 자막 없음 구간, 찬양(노란 가사) 후보                                                |
|                   | `placement.py`                                      | 음성 배치(1.2배속 한도, 밀림, 고정 지점), 싱크 없는 음성의 쉼, 자막 파일(srt, txt) 내용                    |
|                   | `tidy.py`                                           | AI 답 다루기: JSON 배열 꺼내기, 자막 읽기 답 검사, 문장 정리 묶음 나누기와 결과 검증                       |
|                   | `shorts.py`                                         | 쇼츠 구간 계산, AI 후보 검사, 직접 추가·고치기, 세로 화면 배치, 자막(ASS)                                  |
|                   | `schedule.py`                                       | 날마다 자동 작업이 쓸 Claude 사용량과 AI 도구, 자동 작업이 쉬어야 하는지                                   |
|                   | `youtube.py`, `library.py`                          | 유튜브 제목·설명·태그와 이미 있는 영상 찾기, 드라이브 영상 목록에 진행 상태 붙이기                         |
|                   | `ai_tools.py`, `outputs.py`                         | 모델마다 쓸 수 있는지와 한도, 결과 파일 이름                                                               |
|                   | `errors.py`                                         | 없음(404), 지금 할 수 없음(409), AI 사용량 한도, 도구 실행 실패, 유튜브 할당량                             |
| ports             | `storage.py`                                        | 프로젝트 저장소와 작업 파일 자리(Workspace), 작은 상태 파일(StateStore)                                    |
|                   | `media.py`, `speech.py`                             | 영상 분석, 더빙 결과·쇼츠·음성 영상 만들기, 음성 합성                                                      |
|                   | `ai.py`, `drive.py`, `video_platform.py`            | AI 도구 부르기와 상태 알아보기, 자막 그림 묶음, 구글 드라이브, 유튜브                                      |
| application       | `jobs.py`, `pipeline.py`                            | 작업 판(프로젝트마다 하나), 단계 작업(자막 찾기 -> 읽기 -> 정리, 음성 -> 내보내기 -> 드라이브)과 이어 하기 |
|                   | `projects.py`                                       | 프로젝트 불러오기(메모리, 잠금), 만들기, 문장·설정·자막 영역·잘라내기 고치기                               |
|                   | `reading.py`, `voice.py`                            | AI 자막 읽기(캐시, 반으로 나눠 재시도)와 문장 정리, 문장 음성 만들기(캐시)                                 |
|                   | `batch.py`                                          | 자동 진행(자막 읽기 줄)과 음성 대기열(음성 줄 여럿) (`projects/_batch.json`)                               |
|                   | `drive_import.py`, `library.py`                     | 드라이브 영상 받기, 드라이브 목록 폴더의 영상 목록                                                         |
|                   | `youtube.py`                                        | 유튜브 올리기 대기열(할당량을 다 쓰면 다음 날 이어 감), 설명·해시태그 설정 (`projects/_youtube.json`)      |
|                   | `shorts.py`, `sleep.py`                             | 쇼츠 후보 고르기·만들기 대기열(`<프로젝트>/shorts.json`), 음성 영상 대기열(`<프로젝트>/sleep.json`)        |
|                   | `schedule.py`, `ai_tools.py`                        | 스케줄(`projects/_schedule.json`), AI 도구 설정·상태·로그인·연결 시험·사용량(`projects/_tools.json`)       |
| adapters/inbound  | `http/server.py`, `http/api.py`                     | 표준 라이브러리 HTTP 서버(경로표, 파일 이어 받기), `/api` 경로를 유스케이스에 잇기                         |
|                   | `cli.py`                                            | 명령줄 단계 실행                                                                                           |
| adapters/outbound | `project_files.py`, `json_store.py`                 | project.json 저장소, 상태 JSON 파일                                                                        |
|                   | `ffmpeg_video.py`                                   | 영상 정보, 자막 영역 자동 감지, 자막 바뀜 감지(ffmpeg + numpy), 장면 그림                                  |
|                   | `ffmpeg_dub.py`, `wav.py`                           | 더빙 트랙, 영상·오디오·자막 내보내기                                                                       |
|                   | `ffmpeg_shorts.py`, `ffmpeg_sleep.py`               | 쇼츠 세로 영상(흐린 배경 + 자막 띠 위 영상 + ASS 자막)과 미리 보기, 자면서 듣는 설교 영상(이퀄라이저)      |
|                   | `ai_cli.py`, `strip_images.py`, `cli_tool_probe.py` | claude·codex·agy 부르기(사용량·호출 기록), 자막 그림 묶음, 도구 설치·로그인·모델 알아보기                  |
|                   | `supertonic_speech.py`                              | Supertonic 음성 합성                                                                                       |
|                   | `rclone_drive.py`, `youtube_api.py`                 | 구글 드라이브(rclone), 유튜브 로그인(OAuth)·이어 올리기·재생목록·자막                                      |
|                   | `process_guard.py`                                  | 한 프로젝트 폴더에 서버 하나만, 꺼진 서버가 남긴 ffmpeg 정리                                               |

## 화면 (frontend/, FSD)

화면은 Vue 3이고 빌드 없이 `frontend/vendor/vue.esm-browser.prod.js`(3.5.13) 파일 하나를 쓰므로 Node나 빌드 단계가 필요 없습니다. `index.html`의 import map으로 `vue`와 `@/`(= `src/`)를 이름으로 부릅니다. 화면은 받은 JSON으로 그리기만 하고, `/api`를 부를 때는 `shared/api`의 `api()`만 씁니다. 주소의 `#` 뒤가 화면입니다(`#/projects/<단계>`, `#/p/<프로젝트>`, `#/shorts/<상태>/<프로젝트>`, `#/sleep/<상태>`, `#/usage`, `#/schedule`, `#/tools`).

`frontend/serve.py`(표준 라이브러리)는 `index.html`, `src/`, `vendor/`만 내주고 `/api/...`는 API 서버로 그대로 넘깁니다(영상 넘겨 보기의 Range와 내려받기 이름도 그대로). `--port`(기본 8765, `DUBBER_PORT`), `--api`(기본 http://127.0.0.1:8766, `DUBBER_API`), `--lan`을 받습니다.

코드는 Feature-Sliced Design으로 나눕니다. 층은 `app → pages → widgets → features → entities → shared`이고 아래 층만 가져옵니다. 같은 층의 다른 조각은 가져오지 않으며(entities끼리는 `@x/<조각>.js`로만), 조각은 `index.js`(공개 API)로만 가져옵니다. 조각 안은 `ui/`(화면 조각), `model/`(상태), `api/`(API 부르기), `lib/`(계산), `config/`(이름표)로 나눕니다. 이 규칙은 `python frontend/check_fsd.py`로 검사합니다.

| 층       | 조각                                                                                                          | 역할                                                                                                                 |
| -------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| app      | `index.js`, `router`, `ui/App.js`, `ui/NavMenu.js`, `styles`                                                  | 시작, 주소(`#`) 읽기, 화면 틀과 왼쪽 메뉴(단계별 거르기와 숫자), 모양(CSS)                                           |
| pages    | `project-list`, `work`, `shorts`, `sleep`, `usage`, `tools`, `schedule`                                       | 화면 하나씩. 아래 조각을 늘어놓고 몇 초마다 새로 받는다. 작업 화면의 공용 상태(W)는 `work/model/session.js`가 만든다 |
| widgets  | `new-project`, `batch-panel`, `library-list`                                                                  | 프로젝트 목록: 새 프로젝트 카드, 자동 진행 카드, 드라이브 영상 목록                                                  |
|          | `work-video`, `work-timeline`, `work-steps`                                                                   | 프로젝트 작업: 영상, 타임라인(구간 고르기, 잘라내기), 단계 단추와 단계 패널(자막 읽기, 정리와 검수, 음성, 내보내기)  |
|          | `shorts-list`, `shorts-editor`, `sleep-list`                                                                  | 쇼츠 화면의 영상 목록과 편집, 음성 영상 목록                                                                         |
|          | `usage-card`, `usage-history`, `tool-card`, `schedule-settings`, `schedule-calendar`                          | 사용량, AI 도구, 스케줄 카드와 달력                                                                                  |
| features | `drive-import`, `youtube-upload`, `youtube-meta`, `youtube-connect`, `batch-control`                          | 드라이브에서 받기, 유튜브 올리기·설명·연결, 자동 진행 시작·멈추기                                                    |
|          | `project-settings`, `job-cancel`, `cut-edit`, `caption-area`, `sentence-edit`, `voice-settings`               | 프로젝트 설정, 작업 중단, 잘라내기, 자막 영역, 문장 고치기, 목소리와 속도                                            |
|          | `short-edit`, `shorts-create`, `sleep-render`, `sleep-upload`                                                 | 쇼츠 고치기·만들기, 음성 영상 만들기·올리기                                                                          |
|          | `usage-check`, `tool-setup`, `tool-connection`, `schedule-edit`                                               | 사용량 묻기, AI 도구 설정과 연결, 스케줄 바꾸기                                                                      |
| entities | `project`, `sentence`, `library`, `batch`, `shorts`, `sleep-video`, `youtube`, `ai-tool`, `usage`, `schedule` | 업무 대상마다 이름표, 단계 계산, 읽기 API, 목록 상태, 작은 화면 조각(진행 막대 등)                                   |
| shared   | `api`, `lib`, `router`, `ui`                                                                                  | API 부르기, 글 형식과 되풀이 부르기, 지금 화면 상태와 화면 옮기기, 업무를 모르는 화면 조각(창 틀, 진행 줄)           |

코드 모양은 Prettier로 맞춥니다. 개발할 때만 Node가 필요하며, 저장소 루트에서 `npm install` 한 번 뒤 `npm run format`(고치기) 또는 `npm run format:check`(검사만)를 실행합니다.

## 소요 시간 (GPU 없는 노트북 기준)

- 자막 바뀜 찾기: 1시간 영상에 약 30초
- AI 자막 읽기: 25장 묶음당 약 30초, 4묶음 동시 호출로 1,000장에 약 6분
- 음성 합성: 문장당 약 5초, 700문장에 약 1시간 (설정의 "빠름" 품질은 약 절반)
- 내보내기: 1시간 영상에 약 5분

## 음성 엔진으로 Supertonic을 쓰는 이유

GPU 없는 개인 PC에서 사용료 없이 한국어 음성을 쉽게 만들 수 있기 때문입니다.

- GPU가 필요 없습니다. ONNX Runtime으로 CPU에서 돌아갑니다. 이전 구현은 PaddleOCR GPU를 쓰느라 CUDA 설치와 DLL 경로 설정이 필요했는데, 새 구현에서는 GPU 의존을 뺐습니다.
- 설치가 간단합니다. `pip install onnxruntime supertonic`만으로 Windows와 Ubuntu에 설치되고 Python 3.13, 3.14에서도 돌아갑니다. PyTorch 기반 TTS처럼 무겁지 않고, 새 Python 버전을 기다릴 일도 적습니다.
- 사용료가 없고 오프라인으로 돌아갑니다. 첫 실행 때 모델(약 300MB)을 받은 뒤로는 인터넷이 필요 없습니다. 영상 한 편이 700문장쯤이고 자동 진행으로 여러 편을 날마다 만들기 때문에 클라우드 TTS는 비용이 계속 나옵니다.
- 한국어를 바로 지원하고 기본 목소리가 있습니다. `lang="ko"`로 합성하고 목소리 10종(F1~F5, M1~M5) 가운데 고르기만 하면 됩니다. 목소리를 복제하는 엔진처럼 참고 음성을 따로 준비하지 않아도 됩니다.
- 속도를 조절할 수 있습니다. 합성 단계 수(`total_steps`)로 품질과 속도를 맞춥니다. 표준은 8단계, 설정의 "빠름"은 4단계이며 시간이 약 절반입니다.
