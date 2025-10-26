import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
STOCKS = os.getenv('STOCKS', 'FFIE,RVSN,TGL,KXIN,ASST,CELU,ENSC,ONMD,XCUR,RGC,TSLA,HOOD').split(',')
STOCKS = [s.strip().upper() for s in STOCKS]
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', 'your_free_polygon_key')

# Track which spikes we've already alerted on
alerted_spikes = {}
alerted_deaths = {}

def get_market_status():
    """Check if market is open (9:30am - 4pm ET, Mon-Fri)"""
    et = pytz.timezone('US/Eastern')
    now = datetime.now(et)
    
    if now.weekday() >= 5:
        return False
    
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= now <= market_close

def send_discord_alert(title, message, color=3447003):
    """Send alert to Discord via webhook"""
    try:
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }
        data = {"embeds": [embed]}
        response = requests.post(WEBHOOK_URL, json=data)
        response.raise_for_status()
        logger.info(f"Alert sent: {title}")
    except Exception as e:
        logger.error(f"Failed to send Discord alert: {e}")

def get_5min_candles(ticker, limit=100):
    """Fetch 5-min candles using yfinance"""
    try:
        import yfinance as yf
        
        end = datetime.now()
        start = end - timedelta(days=1)
        
        df = yf.download(ticker, interval='5m', start=start, end=end, progress=False)
        
        if df.empty:
            return None
        
        df['volume_avg_20'] = df['Volume'].rolling(20).mean()
        df['volume_ratio'] = df['Volume'] / df['volume_avg_20']
        df['candle_move_pct'] = ((df['Close'] - df['Open']) / df['Open']) * 100
        
        return df.tail(limit)
    
    except Exception as e:
        logger.error(f"Error fetching candles for {ticker}: {e}")
        return None

def check_spike_and_death_candle(ticker):
    """Check if current setup matches: 10% spike + death candle"""
    try:
        df = get_5min_candles(ticker)
        
        if df is None or len(df) < 2:
            return None
        
        current_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]
        
        current_time = df.index[-1]
        prev_time = df.index[-2]
        
        spike_move = prev_candle['candle_move_pct']
        volume_ratio = prev_candle['volume_ratio'] if 'volume_ratio' in prev_candle else 0
        
        is_death_candle = current_candle['Close'] < current_candle['Open']
        
        if spike_move >= 10.0:
            spike_key = f"{ticker}_{prev_time}"
            
            if spike_key not in alerted_spikes:
                alert_msg = (
                    f"**{ticker}** 📊\n"
                    f"Spike: +{spike_move:.2f}%\n"
                    f"Volume Ratio: {volume_ratio:.2f}x\n"
                    f"Price: ${prev_candle['Close']:.2f}\n"
                    f"Time: {prev_time.strftime('%H:%M:%S ET')}\n"
                    f"⏳ Waiting for next candle to close..."
                )
                
                send_discord_alert(
                    f"🚨 SPIKE ALERT - {ticker}",
                    alert_msg,
                    color=16711680
                )
                
                alerted_spikes[spike_key] = current_time
            
            if is_death_candle:
                death_key = f"{ticker}_{current_time}"
                
                if death_key not in alerted_deaths:
                    hod_price = prev_candle['High']
                    risk_pct = ((hod_price - current_candle['Close']) / current_candle['Close']) * 100
                    
                    alert_msg = (
                        f"**{ticker}** ✅ ENTRY SIGNAL\n"
                        f"Death Candle Formed (Red Close)\n"
                        f"Entry: Short at ${current_candle['Open']:.2f}\n"
                        f"Stop: Above HOD ${hod_price:.2f}\n"
                        f"Risk: {risk_pct:.2f}%\n"
                        f"Target: 80 EMA\n"
                        f"Win Rate: 86.9%\n"
                        f"Expected Profit: 6.27%\n"
                        f"Time: {current_time.strftime('%H:%M:%S ET')}"
                    )
                    
                    send_discord_alert(
                        f"✅ ENTRY SIGNAL - {ticker}",
                        alert_msg,
                        color=65280
                    )
                    
                    alerted_deaths[death_key] = current_time
    
    except Exception as e:
        logger.error(f"Error checking {ticker}: {e}")

def main_loop():
    """Main monitoring loop"""
    logger.info(f"Starting monitor for stocks: {STOCKS}")
    
    if not WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL not set!")
        return
    
    while True:
        try:
            if get_market_status():
                logger.info(f"Market open - checking {len(STOCKS)} stocks at {datetime.now()}")
                
                for stock in STOCKS:
                    check_spike_and_death_candle(stock)
                    time.sleep(0.5)
            else:
                logger.info("Market closed")
            
            time.sleep(300)
        
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main_loop()
```

---

## **File 2: requirements.txt**

Copy this and save as `requirements.txt`:
```
requests==2.31.0
pandas==2.0.3
yfinance==0.2.32
polygon-api-client==1.14.0
pytz==2023.3
gunicorn==21.2.0
```

---

## **File 3: Procfile**

Copy this and save as `Procfile`:
```
worker: python app.py
```

---

## **File 4: runtime.txt**

Copy this and save as `runtime.txt`:
```
python-3.11.7
