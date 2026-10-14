"""Prototype: public market movers; not a full-universe early-warning signal."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers&count=100"

def main():
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = json.load(response)
        quotes = raw["finance"]["result"][0]["quotes"]
        rows = []
        for q in quotes:
            change = q.get("regularMarketChangePercent")
            if not isinstance(change, (int, float)):
                continue
            volume, avg = q.get("regularMarketVolume"), q.get("averageDailyVolume3Month")
            rows.append({
                "symbol": q.get("symbol"), "name": q.get("shortName"),
                "price": q.get("regularMarketPrice"), "currency": q.get("currency"),
                "change_pct": round(change, 2), "volume": volume,
                "relative_volume": round(volume / avg, 2) if isinstance(volume, (int, float)) and isinstance(avg, (int, float)) and avg > 0 else None,
                "market_cap": q.get("marketCap"),
                "market_timestamp": q.get("regularMarketTime"),
            })
        result = {"status": "ok", "checked_utc": timestamp, "source": URL,
                  "scope": "Yahoo day_gainers sample; NOT complete TR universe",
                  "signal_quality": "observation_only_not_predictive",
                  "candidates": sorted(rows, key=lambda x: x["change_pct"], reverse=True)}
    except Exception as exc:
        result = {"status": "error", "checked_utc": timestamp, "error": str(exc),
                  "candidates": []}
    Path("output").mkdir(exist_ok=True)
    Path("output/latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['status']}: {len(result['candidates'])} candidates")
    return 0 if result["status"] == "ok" else 1

if __name__ == "__main__":
    sys.exit(main())
