# fng-chatbot

CNN Fear & Greed 지수와 주요 시장 데이터를 조회해 Telegram 채널로 알림을 보내는 봇입니다.

- 스택: Python (Flask, requests, FinanceDataReader), `Procfile` 기반 배포
- 데이터 소스: `production.dataviz.cnn.io` F&G API

## 환경변수

실행 전에 아래 환경변수를 설정해야 합니다.

- `TELEGRAM_BOT_TOKEN`: Telegram BotFather에서 발급받은 봇 토큰
- `TELEGRAM_CHAT_ID`: 메시지를 보낼 Telegram 채팅 또는 채널 ID
- `JOB_TOKEN`: 외부 스케줄러의 발송 요청을 인증하는 32자 이상 임의 문자열. 미설정 또는 너무 짧으면 발송을 차단합니다.

`JOB_TOKEN`은 다음 명령으로 생성할 수 있습니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

예시는 `.env.example`을 참고하세요. 실제 `.env` 파일과 토큰 값은 GitHub에 올리지 않습니다.

## HTTP 엔드포인트

- `GET /`: 서비스 상태만 반환하며 Telegram 메시지를 발송하지 않습니다.
- `GET /healthz`: 배포 플랫폼과 모니터링 서비스용 상태 확인입니다.
- `POST /send`: 올바른 `X-JOB-TOKEN` 요청 헤더가 있을 때만 메시지를 발송합니다.

인증값을 URL 쿼리 문자열(예: `/send?token=...`)에 넣지 마세요. URL은 브라우저 기록, 프록시, 서버 접근 로그 등에 남을 수 있습니다.

외부 스케줄러 호출 예시:

```bash
curl -fsS -X POST \
  -H "X-JOB-TOKEN: $JOB_TOKEN" \
  https://example.com/send
```

배포 전에 동일한 `JOB_TOKEN` 값을 배포 서비스의 환경변수와 외부 스케줄러의 요청 헤더에 각각 등록해야 합니다. 헬스체크 URL은 `/healthz`로 설정하세요.

Cloud Scheduler도 기존 GET `/` 호출에서 POST `/send`와 `X-JOB-TOKEN` 헤더로 함께 변경해야 합니다. Cloud Run의 IAM 인증을 사용하는 경우 Scheduler의 OIDC 서비스 계정 설정도 유지합니다. IAM ID 토큰과 이 앱의 `JOB_TOKEN`은 서로 다른 인증값입니다. 인증값은 저장소·URL·로그에 넣지 않습니다.

한 프로세스에서는 발송을 동시에 하나만 처리하고, 성공 여부와 관계없이 발송 시도 간 60초를 둡니다. 중복·동시 요청은 429와 Retry-After를 반환합니다. 이 제한은 프로세스 재시작이나 다른 인스턴스 사이에서 공유되지 않으므로 전역 중복 방지나 정확히 한 번 전송을 보장하지 않습니다. 발송이 완료된 뒤 응답만 유실된 경우에도 재시도가 중복 전송을 만들 수 있습니다.

외부 오류 응답은 고정 문구이며 로그에는 예외 종류만 기록합니다. Telegram의 응답 본문이나 토큰 포함 URL은 출력하지 않습니다.

## 검증

```bash
python -m unittest discover -s tests -v
```

실제 Flask 요청으로 상태 확인·인증·실패·반복/동시 발송 경계를 검사하며 외부 조회와 Telegram 전송은 mock으로 대체합니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python main.py
```

기본 포트는 `8080`이며, 배포 환경에서 `PORT` 환경변수가 있으면 그 값을 사용합니다.

## 파일

- `main.py` - F&G 조회, 시장 데이터 구성, 인증된 Telegram 발송, Flask HTTP 서버
- `Procfile`, `requirements.txt` - 배포 설정
- `.env.example` - 필요한 환경변수 예시

## 저장소 이력

- 최초 저장소 생성일: 2026-07-09 (한국 시간, 기존 GitHub 메타데이터 기준)
- 재등록일: 2026-09-14 (한국 시간)
- 과거에 공개했던 저장소를 개인정보 정리를 위해 삭제한 뒤, 정리한 코드를 새 Git 이력으로 다시 공개했습니다. 기존 커밋·PR 기록은 새 저장소에 포함하지 않았습니다.
