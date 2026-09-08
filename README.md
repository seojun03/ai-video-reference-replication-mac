# 영상 생성 자동화 — Mac 자동 업데이트 설치

[INSTALL-MAC.zip 다운로드](https://github.com/seojun03/ai-video-reference-replication-mac/releases/latest/download/INSTALL-MAC.zip)

1. ZIP을 받아 압축을 풉니다.
2. `INSTALL-MAC.command`를 실행합니다. Python 3와 플러그인을 지원하는 Codex CLI가 필요합니다.
3. 설치 완료 후 Codex에서 새 작업을 시작합니다.

한 번 설치하면 로그인할 때와 6시간마다 검증된 최신 GitHub Release를 확인합니다. 새 버전은 전용 폴더에 설치하고, Codex 등록이 실패하면 기존 버전으로 되돌립니다. 진행 중인 작업은 강제 종료하지 않으며 새 버전은 새 Codex 작업에서 사용합니다.

제품 자료, 서비스 계정, API 키, CapCut 프로젝트는 배포·업데이트하지 않습니다. Higgsfield와 TTS는 각자의 계정으로 연결합니다. 기본 편집은 macOS 기준이며 별도 스타일 편집 엔진은 별도로 필요합니다.

설치 위치: `~/Library/Application Support/IncoreVideoPlugin`
자동 업데이트: `~/Library/LaunchAgents/com.incore.video-reference-plugin-update.plist`

이 저장소는 소유자가 수정하는 플러그인 원본에서 만들어지는 배포 사본입니다. 원본 변경 → 로컬 검증 → macOS CI → 완성된 릴리스 공개 → 수신자 자동 갱신 순서로 운영합니다. 브랜치 ZIP이나 검증되지 않은 커밋을 설치하지 않습니다.
