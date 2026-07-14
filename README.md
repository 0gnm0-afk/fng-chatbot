# fng-chatbot

CNN Fear & Greed 지수와 주요 시장 데이터를 조회해 Telegram 채널로 알림을 보내는 봇입니다.

- 스택: Python (Flask, requests, FinanceDataReader), `Procfile` 기반 배포
- 데이터 소스: `production.dataviz.cnn.io` F&G API

## 환경변수

실행 전에 아래 환경변수를 설정해야 합니다.

- `TELEGRAM_BOT_TOKEN`: Telegram BotFather에서 발급받은 봇 토큰
- `TELEGRAM_CHAT_ID`: 메시지를 보낼 Telegram 채팅 또는 채널 ID
- `JOB_TOKEN`: 외부 스케줄러의 발송 요청을 인증하는 긴 임의 문자열

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
