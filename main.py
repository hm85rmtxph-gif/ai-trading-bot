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
        for entry in feed.entries[:3]:
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
    msg = MIMEText(message)
    msg["Subject"] = "📊 Daily AI Stock Signals"
    msg["From"] = SENDER
    msg["To"] = EMAIL

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(SENDER, PASSWORD)
    server.send_message(msg)
    server.quit()

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

print("\nKLART\n")
print(email_text)

send_email(email_text)
