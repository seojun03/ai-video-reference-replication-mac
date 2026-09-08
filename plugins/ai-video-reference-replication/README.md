# 영상 생성 자동화 — Mac 자동 업데이트

레퍼런스 제작 주 스킬과 지원 스킬 8개를 포함합니다. 영상 모델·품질·인터뷰 기준은 유지하며, 업체 자료·계정·API 키·CapCut 프로젝트는 공유하지 않습니다.

## 받는 사람에게 줄 설치 링크

[Mac 자동 업데이트 설치 파일](https://github.com/seojun03/ai-video-reference-replication-mac/releases/latest/download/INSTALL-MAC.zip)

압축을 풀고 `INSTALL-MAC.command`를 한 번 실행합니다. Python 3와 플러그인을 지원하는 Codex CLI가 필요합니다. 설치 후 로그인할 때와 6시간마다 최신 검증 릴리스를 자동 확인합니다. 설치가 실패하면 이전 등록과 파일을 복구합니다. 기존 ZIP 수동 설치 사용자도 새 설치 파일을 한 번 실행하면 전환되며 이전 폴더와 개인 파일은 보존합니다.

업데이트는 `~/Library/Application Support/IncoreVideoPlugin` 안에서만 진행합니다. 이전 버전은 보관하며 새 버전은 Codex의 새 작업에서 사용합니다. 작업 중인 Codex와 CapCut을 강제 종료하지 않습니다. 일반 ZIP과 Codex Share만으로는 이 정기 업데이트가 설치되지 않으므로 위 설치 링크를 전달합니다.

## 소유자의 업데이트

원본은 `~/plugins/ai-video-reference-replication/`입니다. 설치 캐시와 배포 저장소의 사본은 직접 수정하지 않습니다.

```bash
python3 ~/plugins/ai-video-reference-replication/scripts/refresh_plugin.py
```

실제 내용이 바뀌면 버전 갱신 → 로컬 설치 → 테스트 → 배포 저장소 동기화 → macOS CI → 공개 릴리스까지 이어집니다. 설정은 소유자 PC의 `~/.codex/state/ai-video-reference-replication/publisher.json`에만 있으며 공유하지 않습니다. 동일 내용 재실행은 버전을 추가로 올리지 않습니다. 로컬에서만 시험할 때는 `VIDEO_REFERENCE_SKIP_AUTO_PUBLISH=1`을 해당 명령에 지정합니다.

첫 공개 전후에도 실패한 CI 결과를 최신 릴리스로 올리지 않습니다. 공개된 네 가지 설치 자산은 다시 내려받아 해시를 비교합니다. 배포 실패는 실패로 보고하며 로컬 갱신을 수신자 배포 완료로 표시하지 않습니다.

## 실행 조건

`references/recipient-runtime.md`를 참고합니다. Python 패키지는 수신자 전용 가상환경에 설치하고 FFmpeg, 내장 이미지 생성, Higgsfield, 선택한 TTS 계정과 기존 CapCut 프로젝트를 각자의 환경에서 확인합니다. 기본 의미별 편집은 macOS 코드가 포함되어 있으며 범용 스타일 편집은 별도 실행 엔진이 필요합니다.
