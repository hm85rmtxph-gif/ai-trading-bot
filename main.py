print("HEDGE FUND AI BOT ⚡")

import yfinance as yf
import numpy as np
import feedparser
from textblob import TextBlob
import smtplib
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import pandas as pd

# ======================
# SETTINGS
# ======================
EMAIL = "Johan.schulzblanc@gmail.com"
SENDER = "Johan.schulzblanc@gmail.com"
import os
PASSWORD = os.getenv("ikraormzyeplfmbr")

# ======================
# HÄMTA S&P500 + NAMN
# ======================
def get_sp500_data():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "constituents"})

    data = []

    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        ticker = cols[0].text.strip()
        name = cols[1].text.strip()

        data.append({
            "ticker": ticker,
            "name": name
        })

    return data

# ======================
# PRISER
# ======================
def get_prices(ticker):
    data = yf.download(ticker, period="1y", progress=False)

    if len(data) < 100:
        return None

    prices = []
    for i in range(len(data)):
        val = data["Close"].iloc[i]
        if hasattr(val, "iloc"):
            val = val.iloc[0]
        prices.append(float(val))

    return prices

# ======================
# SENTIMENT
# ======================
def get_sentiment(ticker):
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock"
        feed = feedparser.parse(url)

        scores = []
        for entry in feed.entries[:1]:
            polarity = TextBlob(entry.title).sentiment.polarity
            scores.append(polarity)

        return np.mean(scores) if scores else 0
    except:
        return 0

# ======================
# SCORE
# ======================
def interpret_score(score):
    if score >= 80:
        return "🔥 STRONG BUY"
    elif score >= 70:
        return "✅ BUY"
    elif score >= 50:
        return "😐 HOLD"
    elif score >= 30:
        return "⚠️ WEAK"
    else:
        return "❌ SELL"

# ======================
# ANALYS
# ======================
def analyze(prices, sentiment):

    mom30 = prices[-1] / prices[-30] - 1
    mom90 = prices[-1] / prices[-90] - 1

    returns = np.diff(prices[-30:]) / prices[-30:-1]
    vol = np.std(returns)

    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = np.mean(gains[-14:])
    avg_loss = np.mean(losses[-14:])
    rsi = 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain/avg_loss))

    score = 50
    score += mom30 * 40
    score += mom90 * 30

    if rsi < 30:
        score += 10
    elif rsi > 70:
        score -= 10

    score -= vol * 50
    score += sentiment * 20

    score = max(0, min(100, score))

    return score, rsi

# ======================
# EN AKTIE (PARALLELL)
# ======================
def process_stock(stock):
    ticker = stock["ticker"]
    name = stock["name"]

    try:
        prices = get_prices(ticker)
        if prices is None:
            return None

        sentiment = get_sentiment(ticker)
        score, rsi = analyze(prices, sentiment)

        return {
            "ticker": ticker,
            "name": name,
            "score": score,
            "rsi": rsi
        }

    except:
        return None

# ======================
# EMAIL
# ======================
def send_email(message):

    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg["Subject"] = "📊 Daily AI Stock Signals"
    msg["From"] = SENDER
    msg["To"] = EMAIL

    # text
    msg.attach(MIMEText(message, "plain"))

    # 📎 bifoga CSV
    filename = "history.csv"

    try:
        with open(filename, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")

        msg.attach(part)

    except:
        print("Kunde inte bifoga CSV")

    # skicka
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(SENDER, PASSWORD)
    server.send_message(msg)
    server.quit()

def save_history(results):
    filename = "history.csv"
    today = datetime.now().strftime("%Y-%m-%d")

    with open(filename, mode="a", newline="") as file:
        writer = csv.writer(file)

        for r in results[:10]:  # sparar TOP 10 BUY
            writer.writerow([
                today,
                r["ticker"],
                r["name"],
                round(r["score"], 2)
            ])
# ======================
# MAIN
# ======================
print("Hämtar aktier + namn...\n")

stocks = get_sp500_data()

print(f"Totalt: {len(stocks)} aktier\n")

results = []

# PARALLELL
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(process_stock, s) for s in stocks]

    for i, future in enumerate(as_completed(futures)):
        result = future.result()
        if result:
            results.append(result)

        print(f"Klar: {i+1}/{len(stocks)}")

# sortera
results = sorted(results, key=lambda x: x["score"], reverse=True)

# ======================
# EMAIL TEXT
# ======================
email_text = "📊 DAILY STOCK SIGNALS\n\n"

email_text += "🔥 TOP BUY:\n\n"
for r in results[:10]:
    signal = interpret_score(r["score"])
    email_text += f"{r['ticker']} ({r['name']}) | {round(r['score'],1)} | {signal}\n"

email_text += "\n⚠️ SELL:\n\n"
for r in results[-10:]:
    signal = interpret_score(r["score"])
    email_text += f"{r['ticker']} ({r['name']}) | {round(r['score'],1)} | {signal}\n"

email_text += "\n\nScore:\nTrend + RSI + Sentiment – Risk"
email_text += "\n\n📊 SCORE-FÖRKLARING:\n"
email_text += "Score = Trend (30d + 90d momentum) + RSI + Sentiment – Risk (volatilitet)\n\n"
email_text += "80–100 = 🔥 STRONG BUY\n"
email_text += "70–80 = ✅ BUY\n"
email_text += "50–70 = 😐 HOLD\n"
email_text += "30–50 = ⚠️ WEAK\n"
email_text += "0–30 = ❌ SELL\n"
print("\nKLART\n")
print(email_text)

save_history(results)
send_email(email_text)
def analyze_performance():
    try:
        import pandas as pd

        df = pd.read_csv("history.csv", header=None)
        df.columns = ["date", "ticker", "name", "score"]

        print("\n📊 SENASTE SIGNALER:")
        print(df.tail(10))

    except:
        print("Ingen historik ännu")
analyze_performance()
def calculate_performance():
    try:
        df = pd.read_csv("history.csv", header=None)
        df.columns = ["date", "ticker", "name", "score"]

        results = []

        for i in range(len(df)):
            row = df.iloc[i]

            ticker = row["ticker"]
            date = row["date"]

            # hämta prisdata från den dagen
            data = yf.download(ticker, start=date, period="10d", progress=False)

            if len(data) < 2:
                continue

            start_price = float(data["Close"].iloc[0])
            end_price = float(data["Close"].iloc[-1])

            return_pct = (end_price - start_price) / start_price * 100

            results.append(return_pct)

        if len(results) == 0:
            print("\nIngen performance-data ännu\n")
            return

        avg_return = np.mean(results)

        print("\n📊 PERFORMANCE:\n")
        print(f"Antal trades: {len(results)}")
        print(f"Snittavkastning: {round(avg_return,2)}%")

    except Exception as e:
        print("Fel i performance:", e)
calculate_performance()
