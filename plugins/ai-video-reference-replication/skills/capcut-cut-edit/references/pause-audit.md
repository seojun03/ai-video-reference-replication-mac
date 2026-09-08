# 중간 쉼 검수 실행

원본 후보를 정리할 때와 저장할 최종 음성이 준비됐을 때 읽는다. 수치는 `../SKILL.md`의 `pause-audit-policy`가 소유한다. 검수기는 표준 Python만 쓰며, 실제 편집이나 앱 제어를 하지 않는다.

1. 실제 사용할 원음 전체를 PCM16 WAV로 분석용 디코드한다. 원본과 최종 음성은 별도로 검사한다. 여러 영상은 source/target 구간대로 이어 최종 음성을 만든다. 리샘플링한 검수 파일을 타임라인 원본 대신 쓰지 않는다.
2. 컷 매핑은 source 경로·SHA-256·in/out·target in/out·FPS를 포함해 해시한다. 자막 수나 논리 컷 수만 해시하지 않는다. 문맥별 저장기는 기존 `cut_hash(plan)`을 사용한다.
3. `pause_audit.py scan --audio '/절대경로/final.wav' --cut-sha256 '<컷 매핑 해시>' --fps 24 --report '/절대경로/pause-audit.json'`으로 전체 후보를 생성한다. `--boundaries-us`에 실제 영상/음성 연결부 시각을 주면 내부와 연결부가 구분된다. FPS는 현재 프로젝트 값으로 바꾼다. 보고서는 기존 파일을 덮어쓰지 않는다.
4. 원본의 모든 후보에 삭제 구간 또는 보존 이유를 기록한다. 최종 검수의 `full_audio_review`에는 전체 음성을 파형·문맥으로 검토했는지와 검토 방법을 적는다. 실제로 듣지 않았다면 청취했다고 쓰지 않는다. 배경음·숨소리 때문에 검출되지 않은 쉼도 확인한다.
5. 최종 `candidates`는 수정하지 않는다. 각 후보 ID마다 `decisions`에 정확히 한 항목을 기록한다. 공통 필드는 `candidate_id`, `audio_sha256`, `start_us`, `end_us`, `context_before`, `context_after`, `reason`, `waveform_reviewed`, `evidence: {path, sha256}`다. evidence는 그 구간의 실제 파형·스펙트럼과 앞뒤 문구를 확인한 파일이다. 구간 식별은 검수 후보와 같아야 한다.
   - `resolution: speech_protection`: 검출 구간에 보존할 실제 발음이 있으면 `protected_phoneme`에 해당 자음·끝음절을 명시한다. 단순 침묵을 발음 보호로 바꾸지 않는다.
   - `resolution: intentional_pause`: `intent_evidence`에 `kind: user_instruction | approved_reference`, 구체적인 `quote`, 원문/레퍼런스 검토 기록의 `source: {path, sha256}`를 연결한다. “순위 발표니까”, “자연스러우니까”라는 에이전트의 추정만으로는 보존할 수 없다.
   - `resolution: natural_short_pause`: 파형에서 확인한 `previous_speech_end_us`, `next_speech_start_us`를 기록한다. 실제 발음 사이의 여유가 공통 목표와 한 프레임 반올림 범위 이내인지 검증한다. 이보다 긴 침묵은 필요한 컷을 수행하고 새 최종 음성을 검사한다.
   - 삭제해야 하는 후보나 아직 불확실한 후보는 완료로 바꾸지 않는다. 컷 반영 후 다시 검사한다. 추가 사용자 승인 질문을 자동으로 만들지 않는다.
6. `pause_audit.py verify`에 동일한 음성·컷 해시·FPS·경계·보고서를 전달한다. 검수기는 현재 음성을 다시 계산하여 누락·오래된 결과·모호한 예외를 차단한다. 후보 0개 역시 전체 음성 검토가 필요하다.

저장기에 연결할 때는 `validate_audit(report, audio=..., cut_sha256=..., fps=..., boundaries_us=...)`를 실제 쓰기 전에 호출한다. 최종 WAV와 타임라인 원음 구간의 PCM 일치 검사는 호출자가 수행한다. 저장 후에도 같은 source/target 매핑인지 역검증한다. 준비·등록·저장본 확인 중 하나라도 검수 없이 성공시키지 않는다.

이 검수는 미처리 후보와 증거 누락을 막는 검사다. 에너지 검출이 모든 쉼이나 발음을 완벽하게 판정한다는 뜻이 아니며, 실제 문맥 판단을 자동 통과시키지 않는다. 제품명·순위·특정 업체의 시간을 공통 예외로 하드코딩하지 않는다.
