# fng-chatbot

CNN Fear & Greed 지수를 매일 확인해 Telegram 채널로 알림을 보내는 봇.

- 스택: Python (Flask, requests, FinanceDataReader), `Procfile` 기반 배포
- 데이터 소스: `production.dataviz.cnn.io` F&G API
- 취업 자소서에 등장하는 실제 프로젝트이기도 함 (경험 카드: `../취업/10_경험/FNG-알림봇-개발.md`)

## 환경변수

실행 전에 아래 환경변수를 설정해야 합니다.

- `TELEGRAM_BOT_TOKEN`: Telegram BotFather에서 발급받은 봇 토큰
- `TELEGRAM_CHAT_ID`: 메시지를 보낼 Telegram 채팅 또는 채널 ID

예시는 `.env.example`을 참고하세요. 실제 `.env` 파일과 토큰 값은 GitHub에 올리지 않습니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python main.py
```

기본 포트는 `8080`이며, 배포 환경에서 `PORT` 환경변수가 있으면 그 값을 사용합니다.

## 파일
- `main.py` — 봇 전체 로직 (F&G 조회 + Telegram 발송 + Flask keep-alive)
- `Procfile`, `requirements.txt` — 배포 설정
