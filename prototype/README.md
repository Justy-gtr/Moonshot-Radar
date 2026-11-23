# Streaming Momentum Radar (experimental)

Prototype branch, **not deployed**. A full-world real-time scanner is NOT provided by a free data feed.

## Requirements
- Python 3.10+, `pip install websockets`
- `FINNHUB_API_KEY` (provider account)
- `NTFY_URL` e.g. `https://ntfy.sh/<random-private-topic>` (ntfy iPhone app subscription)
- `SYMBOLS` comma-separated list, e.g. NVDA,TSLA,RKLB

Run `python streaming_radar.py` on an always-on machine. Alerts at ±2%/5min and ±4%/10min; 15min cooldown per rule.

**Limitations:** Only explicitly subscribed symbols, data feed and entitlement limitations, no guaranteed push delivery, no trading functionality. Never commit API keys. Public ntfy topics are not access-controlled.
