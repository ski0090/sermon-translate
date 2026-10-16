"""설교 영상 한국어 더빙 API 서버(헥사고날 구조).
- domain: 바깥을 모르는 규칙(프로젝트, 문장, 배치, 쇼츠, 스케줄, 유튜브 메타)
- ports: 바깥(파일, ffmpeg, AI 도구, 음성 엔진, 구글 드라이브, 유튜브)과의 약속
- application: 유스케이스(작업, 대기열, 자동 진행). 포트만 쓴다
- adapters: inbound(HTTP API, 명령줄)와 outbound(포트를 실제로 구현)
- bootstrap: 어댑터를 만들어 유스케이스에 끼우는 곳"""
