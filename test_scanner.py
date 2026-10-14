import unittest
from datetime import datetime, timezone
from scanner import parse_feed, classify, market_rows, date

class Integrity(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 14, 13, 0, tzinfo=timezone.utc)
    def test_html_error_is_not_empty_success(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<html><body>blocked</body></html>')
    def test_atom(self):
        rows = parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>8-K Company</title><link href="https://sec.gov/a"/><updated>2026-10-14T12:50:00Z</updated><summary>Offering</summary></entry></feed>')
        r = classify(rows[0], 'SEC 8-K', self.now)
        self.assertEqual(r['status'], 'RISIKO PRÜFEN')
        self.assertFalse(r['signal'])
        self.assertEqual(r['age_minutes'], 10)
    def test_future_not_fresh(self):
        r = classify({'title':'FDA approval','summary':'','published_utc':'2026-10-15T00:00:00Z'}, 'FDA', self.now)
        self.assertEqual(r['freshness'], 'älter/zeitlich ungeklärt')
    def test_timezone_required(self):
        self.assertIsNone(date('2026-10-14T12:00:00'))
    def quote(self):
        return dict(symbol='TEST', regularMarketPrice=10, regularMarketChangePercent=3, regularMarketTime=self.now.timestamp()-20, regularMarketVolume=200, averageDailyVolume3Month=100, currency='USD')
    def test_stale_quote_no_momentum(self):
        q = self.quote(); q['regularMarketTime'] -= 3600
        self.assertNotEqual(market_rows([q], {}, self.now)[0]['status'], 'MOMENTUM PRÜFEN')
    def test_currency_mismatch_no_comparison(self):
        old={'TEST':{'price':9, 'currency':'EUR', 'seen_utc':'2026-10-14T12:45:00Z','market_timestamp':self.now.timestamp()-900}}
        self.assertIsNone(market_rows([self.quote()],old,self.now)[0]['change_since_previous_scan_pct'])
    def test_scan_delta(self):
        old={'TEST':{'price':8, 'currency':'USD', 'seen_utc':'2026-10-14T12:45:00Z','market_timestamp':self.now.timestamp()-900}}
        r=market_rows([self.quote()],old,self.now)[0]
        self.assertEqual(r['change_since_previous_scan_pct'],25)
        self.assertFalse(r['signal'])
    def test_invalid_numeric(self):
        q=self.quote(); q['regularMarketPrice']=float('nan')
        self.assertEqual(market_rows([q], {}, self.now), [])

if __name__=='__main__': unittest.main()
