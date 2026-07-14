import hmac
import os

import requests
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import pytz
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
JOB_TOKEN = os.environ.get("JOB_TOKEN")

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')


## 1단계: F&G 지수 가져오기 (오늘 + 어제 모두 CNN에서)
def get_fng_scores():
    data_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }
    response = requests.get(data_url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    today_score = int(round(data.get('fear_and_greed', {}).get('score', 0)))
    previous_score = None

    prev_close = data.get('fear_and_greed_historical', {}).get('previousClose')
    if prev_close is not None:
        previous_score = int(round(prev_close))
    else:
        prev_week = data.get('fear_and_greed', {}).get('previous_1_week')
        if prev_week is not None:
            previous_score = int(round(prev_week))

    return today_score, previous_score


## 2단계: 지수 구간 및 레벨 분석
def get_fng_zone_and_level(score):
    if score is None:
        return ("Unknown", 0)
    if score >= 92: return ("Extreme Greed 구간", 3)
    if score >= 84: return ("Extreme Greed 구간", 2)
    if score >= 76: return ("Extreme Greed 구간", 1)
    if score >= 55: return ("Greed 구간", 0)
    if score >= 46: return ("Neutral 구간", 0)
    if score >= 25: return ("Fear 구간", 0)
    if score >= 17: return ("Extreme Fear 구간", 1)
    if score >= 9: return ("Extreme Fear 구간", 2)
    if score >= 0: return ("Extreme Fear 구간", 3)
    return ("Unknown", 0)


## 3단계: 전략 메시지 생성
def generate_strategy_message(today_score, previous_score):
    today_zone, today_level = get_fng_zone_and_level(today_score)

    if previous_score is not None:
        prev_zone, prev_level = get_fng_zone_and_level(previous_score)
    else:
        prev_zone, prev_level = ("None", 0)

    now_kst = datetime.now(KST)
    message_lines = []

    message_lines.append("**Fear&Gread 알림봇**")

    if "Extreme" in today_zone:
        today_display_text = f"{today_zone} Lvl {today_level}"
    else:
        today_display_text = f"{today_zone}"
    message_lines.append(f"📊 오늘의 F&G 지수: {today_score}")

    if previous_score is None:
        message_lines.append(f"(현재 상태: {today_display_text})")
    elif today_zone == prev_zone:
        message_lines.append(f"(현재 상태: {today_display_text})")
    else:
        if "Extreme" in prev_zone:
            prev_display_text = f"{prev_zone} Lvl {prev_level}"
        else:
            prev_display_text = f"{prev_zone}"
        message_lines.append(f"(변동: {prev_display_text} → {today_display_text})")

    if now_kst.day == 1:
        message_lines.append(f"\n🔔 **월초 정기 매수 알림**")
        message_lines.append(f"이번 달 납입금의 일괄 매수를 실행할 날입니다.")

    if today_level == 2 and prev_level < 2:
        message_lines.append(f"\n🚨 **F&G 공포 레버리지 (Lvl 2) 진입!**")
        message_lines.append(f"'ISA F&G' 전략: **월 납입금 만큼**의 추가 매수 고려.")
    elif today_level == 3 and prev_level < 3:
        message_lines.append(f"\n🚨🚨 **F&G 공포 레버리지 (Lvl 3) 진입!!**")
        message_lines.append(f"'ISA F&G' 전략: **월 납입금 ｘ ２**의 추가 매수 고려.")

    return "\n".join(message_lines)


## 4단계: 시장 데이터 가져오기
def get_market_data():
    data = {}
    now = datetime.now()
    start_date = (now - timedelta(days=14)).strftime('%Y-%m-%d')

    def get_price_and_change(df):
        if df is None or df.empty:
            return None, None
        df = df.dropna(subset=['Close'])
        if len(df) < 2:
            return None, None
        curr = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        if prev == 0:
            return curr, None
        change = ((curr - prev) / prev) * 100
        return curr, change

    def safe_format(price, change):
        if price is None:
            return None
        if change is None or str(change) == 'nan':
            return f"{price:,.2f}"
        return f"{price:,.2f} ({change:+.2f}%)"

    # 1. 원달러 환율
    try:
        krw_df = fdr.DataReader('USD/KRW', start=start_date)
        price, change = get_price_and_change(krw_df)
        fmt = safe_format(price, change)
        if fmt:
            data['USD_KRW'] = f"{fmt} 원"
    except Exception as e:
        print(f"환율 로드 실패: {e}")

    # 2. 비트코인 (BTC/USD)
    try:
        btc_df = fdr.DataReader('BTC/USD', start=start_date)
        price, change = get_price_and_change(btc_df)
        if price is not None:
            if change is not None and str(change) != 'nan':
                data['BTC_USD'] = f"${price:,.2f} ({change:+.2f}%)"
            else:
                data['BTC_USD'] = f"${price:,.2f}"
    except Exception as e:
        print(f"비트코인 로드 실패: {e}")

    # 3. 코스피 (네이버 금융 API)
    try:
        kospi_data = get_kospi_from_naver()
        if kospi_data:
            data['KOSPI_Close'] = kospi_data
    except Exception as e:
        print(f"코스피 로드 실패: {e}")

    # 4. 나스닥 (현물)
    try:
        nasdaq_df = fdr.DataReader('IXIC', start=start_date)
        price, change = get_price_and_change(nasdaq_df)
        fmt = safe_format(price, change)
        if fmt:
            data['NASDAQ_Close'] = fmt
    except Exception as e:
        print(f"나스닥 로드 실패: {e}")

    # 5. 나스닥 (선물)
    try:
        nq_df = fdr.DataReader('NQ=F', start=start_date)
        price, change = get_price_and_change(nq_df)
        fmt = safe_format(price, change)
        if fmt:
            data['NASDAQ_Futures'] = fmt
    except Exception as e:
        print(f"나스닥 선물 로드 실패: {e}")

    # 6. S&P 500 (현물)
    try:
        sp500_df = fdr.DataReader('S&P500', start=start_date)
        price, change = get_price_and_change(sp500_df)
        fmt = safe_format(price, change)
        if fmt:
            data['SP500_Close'] = fmt
    except Exception as e:
        print(f"S&P500 로드 실패: {e}")

    # 7. S&P 500 (선물)
    try:
        es_df = fdr.DataReader('ES=F', start=start_date)
        price, change = get_price_and_change(es_df)
        fmt = safe_format(price, change)
        if fmt:
            data['SP500_Futures'] = fmt
    except Exception as e:
        print(f"S&P500 선물 로드 실패: {e}")

    return data


## 코스피 지수 네이버 금융에서 가져오기
def get_kospi_from_naver():
    """네이버 금융 API로 코스피 지수 조회"""
    try:
        url = "https://m.stock.naver.com/api/index/KOSPI/basic"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer': 'https://m.stock.naver.com/index/KOSPI/total',
            'Accept': 'application/json, text/plain, */*'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()

        close_price = data.get('closePrice', '')
        compare_price = data.get('compareToPreviousClosePrice', '')
        fluctuation = data.get('fluctuationsRatio', '')

        if close_price:
            price = float(close_price.replace(',', ''))
            result = f"{price:,.2f}"
            if fluctuation:
                fluc = float(fluctuation)
                result += f" ({fluc:+.2f}%)"
            return result
    except Exception as e:
        print(f"네이버 코스피 API 실패: {e}")
    return None


## 5단계: 코스피 투자자별 매매 동향 (네이버 금융 API)
def get_kospi_investor_data():
    """네이버 금융 API로 투자자별 순매수 조회"""
    try:
        url = "https://m.stock.naver.com/api/index/KOSPI/investorTrendDaily?page=1&pageSize=3"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer': 'https://m.stock.naver.com/index/KOSPI/investor',
            'Accept': 'application/json, text/plain, */*'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data or len(data) == 0:
            return None

        latest = data[0]
        trade_date = latest.get('tradeDate', '')
        if trade_date and len(trade_date) >= 8:
            trade_date = f"{trade_date[4:6]}/{trade_date[6:8]}"

        def to_eok(val):
            if val is None:
                return 'N/A'
            try:
                eok = float(val) / 100000000
                return f"{eok:+,.0f}억"
            except:
                return 'N/A'

        return {
            'date': trade_date,
            'individual': to_eok(latest.get('individualNetBuyVolume', 0)),
            'institution': to_eok(latest.get('institutionNetBuyVolume', 0)),
            'foreign': to_eok(latest.get('foreignerNetBuyVolume', 0)),
        }
    except Exception as e:
        print(f"투자자별 매매 동향 로드 실패: {e}")
        return None


## 6단계: 시장 데이터 메시지 포맷팅
def format_market_data_message(data, investor_data=None):
    if not data:
        return ""
    lines = ["\n--- 🌏 주요 시장 현황 (전일 대비) ---"]

    if data.get('USD_KRW'):
        lines.append(f"· 💹 원/달러: {data['USD_KRW']}")
    if data.get('BTC_USD'):
        lines.append(f"· 🪙 비트코인/달러 : {data['BTC_USD']}")

    lines.append("\n전일 종가")
    if data.get('KOSPI_Close'):
        lines.append(f"· 🇰🇷 코스피: {data['KOSPI_Close']}")
    if data.get('NASDAQ_Close'):
        lines.append(f"· 🇺🇸 나스닥: {data['NASDAQ_Close']}")
    if data.get('SP500_Close'):
        lines.append(f"· 🇺🇸 S&P500: {data['SP500_Close']}")

    # 투자자별 매매 동향 (데이터 있을 때만 표시)
    if investor_data:
        lines.append(f"\n🇰🇷 코스피 투자자별 순매수 ({investor_data['date']})")
        lines.append(f"· 👤 개인: {investor_data.get('individual', 'N/A')}")
        lines.append(f"· 🏢 기관: {investor_data.get('institution', 'N/A')}")
        lines.append(f"· 🌍 외국인: {investor_data.get('foreign', 'N/A')}")

    if data.get('NASDAQ_Futures') or data.get('SP500_Futures'):
        lines.append("\n현재 선물")
        if data.get('NASDAQ_Futures'):
            lines.append(f"· 🇺🇸 나스닥 선물 : {data['NASDAQ_Futures']}")
        if data.get('SP500_Futures'):
            lines.append(f"· 🇺🇸 S&P500 선물 : {data['SP500_Futures']}")

    return "\n".join(lines)


## HTTP 엔드포인트
@app.get("/")
def index():
    """부작용 없는 기본 상태 확인."""
    return "fng-chatbot is running", 200


@app.get("/healthz")
def healthz():
    """배포 플랫폼과 모니터링 서비스용 상태 확인."""
    return "ok", 200


@app.post("/send")
def send_fear_and_greed():
    supplied_token = request.headers.get("X-JOB-TOKEN", "")
    if not JOB_TOKEN or not hmac.compare_digest(supplied_token, JOB_TOKEN):
        return "unauthorized", 401

    bot_token = BOT_TOKEN
    chat_id = CHAT_ID
    if not bot_token or not chat_id:
        return "service unavailable", 503

    try:
        today_score, previous_score = get_fng_scores()
        strategy_message = generate_strategy_message(today_score, previous_score)
        market_data = get_market_data()
        investor_data = get_kospi_investor_data()
        market_message = format_market_data_message(market_data, investor_data)

        final_message = strategy_message + "\n" + market_message

        send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': final_message,
            'parse_mode': 'Markdown'
        }

        resp = requests.post(send_url, json=payload, timeout=10)
        resp.raise_for_status()
        telegram_result = resp.json()
        if telegram_result.get("ok") is not True:
            raise RuntimeError("Telegram API returned ok=false")

        return "전송 성공", 200
    except Exception as exc:
        # 예외 메시지에는 Telegram Bot API URL과 토큰이 포함될 수 있으므로
        # 외부 응답과 로그에는 예외 종류만 남긴다.
        app.logger.error("message delivery failed (%s)", type(exc).__name__)
        return "message delivery failed", 502


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
