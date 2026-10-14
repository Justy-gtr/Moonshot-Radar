"""Public-source research inbox. Observations are NOT validated trading signals."""
import hashlib
import html
import json
import math
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).parent
UA = 'MoonshotRadar/2.0 (+https://github.com/Justy-gtr/Moonshot-Radar)'
SOURCES = {
    'FDA': 'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml',
    'SEC 8-K': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&owner=exclude&count=100&output=atom',
    'SEC 6-K': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=6-K&owner=exclude&count=100&output=atom',
    'SEC Finanzierung': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=424B&owner=exclude&count=100&output=atom',
    'Yahoo Tagesgewinner': 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers&count=100',
}

def utc():
    return datetime.now(timezone.utc)

def date(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        try:
            d = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    return d.astimezone(timezone.utc) if d.tzinfo else None

def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]*>', ' ', value or ''))).strip()

def parse_feed(raw):
    root = ET.fromstring(raw)
    if root.tag.split('}')[-1] not in ('rss', 'feed', 'RDF'):
        raise ValueError('Response is not RSS/Atom')
    rows = []
    for item in root.iter():
        if item.tag.split('}')[-1] not in ('item', 'entry'):
            continue
        fields, link = {}, ''
        for e in item:
            key = e.tag.split('}')[-1]
            if key == 'link' and e.get('rel', 'alternate') == 'alternate':
                link = e.get('href') or e.text or link
            fields[key] = ''.join(e.itertext())
        link = link.strip()
        if not link.startswith('https://') and not link.startswith('http://'):
            continue
        published = date(fields.get('published') or fields.get('pubDate') or fields.get('updated'))
        rows.append({'title': clean(fields.get('title')), 'url': link,
                     'published_utc': published.isoformat() if published else None,
                     'timestamp_kind': 'feed published/pubDate' if ('published' in fields or 'pubDate' in fields) else 'feed updated (not necessarily first publication)',
                     'summary': clean(fields.get('summary') or fields.get('description'))[:3000]})
    return rows

def fetch(name, url):
    try:
        agent = os.getenv('SEC_USER_AGENT') or UA if name.startswith('SEC') else UA
        req = urllib.request.Request(url, headers={'User-Agent': agent, 'Accept': '*/*'})
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError('Response exceeds safety size limit')
        if name.startswith('Yahoo'):
            rows = json.loads(raw)['finance']['result'][0]['quotes']
            if not isinstance(rows, list):
                raise ValueError('Missing quotes')
        else:
            rows = parse_feed(raw)
        return name, {'status': 'ok', 'fetched_utc': utc().isoformat(), 'url': url, 'rows': rows}
    except Exception as exc:
        # Do not log headers or secrets.
        return name, {'status': 'error', 'fetched_utc': utc().isoformat(), 'url': url,
                      'error': f'{type(exc).__name__}: {str(exc)[:180]}', 'rows': []}

def classify(row, source, now):
    pub = date(row['published_utc'])
    age = (now - pub).total_seconds() / 60 if pub else None
    text = (row['title'] + ' ' + row['summary']).lower()
    risks = [word for word in ('offering', 'bankruptcy', 'going concern', 'delisting', 'recall', 'withdrawal', 'termination') if word in text]
    if source == 'SEC Finanzierung':
        risks.append('Prospekt: Finanzierung/Altaktionärsverkauf prüfen; keine vollzogene Verwässerung behaupten')
    fresh = age is not None and 0 <= age <= 60
    return dict(row, source=source, age_minutes=round(age, 1) if age is not None else None,
                freshness='Zeitstempel ≤60 min; Erstveröffentlichung prüfen' if fresh else 'älter/zeitlich ungeklärt',
                status='RISIKO PRÜFEN' if risks else 'ORIGINALMELDUNG PRÜFEN', risk_terms=risks,
                trade_republic='offen', probability=None,
                signal=False, reason='Inhalt, wirtschaftliche Bedeutung, Zuordnung und Kursreaktion noch zu verifizieren')

def market_rows(quotes, previous, now):
    rows = []
    for q in quotes:
        symbol, price, change, stamp = (q.get(k) for k in ('symbol', 'regularMarketPrice', 'regularMarketChangePercent', 'regularMarketTime'))
        if not symbol or not number(price) or price <= 0 or not number(change):
            continue
        vol, avg = q.get('regularMarketVolume'), q.get('averageDailyVolume3Month')
        rv = vol / avg if number(vol) and number(avg) and avg > 0 else None
        age = now.timestamp() - stamp if number(stamp) else None
        fresh = age is not None and 0 <= age <= 300
        prior = previous.get(symbol, {})
        comparison = None
        prior_seen = date(prior.get('seen_utc'))
        if (prior_seen and 0 < (now-prior_seen).total_seconds() <= 3600
                and prior.get('currency') == q.get('currency') and number(prior.get('price'))
                and prior['price'] > 0 and number(stamp) and number(prior.get('market_timestamp'))
                and 0 < stamp-prior['market_timestamp'] <= 3600 and fresh):
            comparison = round((price/prior['price']-1)*100, 3)
        # Relative volume is accumulated day volume / average FULL-DAY volume.
        watch = fresh and 0 < change <= 5 and rv is not None and rv >= 1.5
        rows.append({'symbol': symbol, 'name': q.get('shortName', symbol), 'price': price,
                     'currency': q.get('currency'), 'change_pct': round(change, 3),
                     'market_timestamp': stamp, 'quote_age_seconds': age,
                     'relative_full_day_volume': round(rv, 3) if rv is not None else None,
                     'market_cap': q.get('marketCap'), 'volume': vol,
                     'change_since_previous_scan_pct': comparison,
                     'seen_utc': now.isoformat(), 'status': 'MOMENTUM PRÜFEN' if watch else 'BEREITS GESTIEGEN / DATEN PRÜFEN',
                     'signal': False, 'trade_republic': 'offen'})
    return rows

def esc(value):
    return clean(str(value)).replace('|', '\\|').replace('[', '\\[').replace(']', '\\]')

def run():
    now = utc()
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    state_path = data / 'state.json'
    # A corrupt journal must fail loudly; never silently reset history.
    state = json.loads(state_path.read_text()) if state_path.exists() else {'seen': {}, 'market': {}, 'source_success': {}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        sources = dict(pool.map(lambda pair: fetch(*pair), SOURCES.items()))
    news = []
    for name, result in sources.items():
        if result['status'] != 'ok':
            continue
        if name.startswith('Yahoo'):
            continue
        rows = result['rows']
        old_success = date(state['source_success'].get(name))
        dates = [date(r['published_utc']) for r in rows if date(r['published_utc'])]
        result['coverage_warning'] = ('Feed erreicht Abruflimit; mögliche Lücke' if len(rows) >= 100 else None)
        if old_success and dates and min(dates) > old_success:
            result['coverage_warning'] = 'Feed überlappt letzten erfolgreichen Abruf nicht; mögliche Lücke'
        for row in rows:
            key = hashlib.sha256(row['url'].encode()).hexdigest()
            if key in state['seen']:
                continue
            state['seen'][key] = now.isoformat()
            item = classify(row, name, now)
            item.update(id=key, first_seen_utc=now.isoformat(), content_hash=hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest())
            news.append(item)
        state['source_success'][name] = result['fetched_utc']
    market = market_rows(sources['Yahoo Tagesgewinner']['rows'], state['market'], now)
    # Persist all observed quotes, including failures/non-winners on later runs as missing data.
    if sources['Yahoo Tagesgewinner']['status'] == 'ok':
        state['market'] = {r['symbol']: r for r in market}
        state['source_success']['Yahoo Tagesgewinner'] = sources['Yahoo Tagesgewinner']['fetched_utc']
    for result in sources.values():
        result['count'] = len(result.pop('rows'))
    ok = sum(s['status'] == 'ok' for s in sources.values())
    report = {'schema_version': 2, 'checked_utc': now.isoformat(), 'status': 'ok' if ok == len(sources) else 'partial' if ok else 'error',
              'sources': sources, 'new_items': news, 'market_observations': market,
              'coverage': 'FDA releases + latest SEC 8-K/6-K/424B samples + Yahoo day gainers; no full market/TR/crypto coverage',
              'performance': {'validated_signals': 0, 'hit_rate': None, 'reason': 'Research observations only; no validated trading signals emitted'},
              'notification': 'No direct push; existing ChatGPT radar must independently validate candidates'}
    day = now.strftime('%Y-%m-%d')
    for name, records in [('events', news), ('quotes', market), ('runs', [{k:v for k,v in report.items() if k not in ('new_items','market_observations')}])]:
        folder = data / name
        folder.mkdir(exist_ok=True)
        with (folder / f'{day}.jsonl').open('a') as f:
            for row in records:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False))
    (data/'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    # Include recent persisted events, so a later empty scan does not hide the research inbox.
    recent = []
    for p in sorted((data/'events').glob('*.jsonl'))[-3:]:
        for line in p.read_text().splitlines():
            r = json.loads(line)
            pub = date(r.get('published_utc'))
            if pub and 0 <= (now-pub).total_seconds() <= 86400:
                recent.append(r)
    recent.sort(key=lambda r: r['published_utc'], reverse=True)
    lines = ['# Moonshot Radar · Forschungs-Eingang', '', f"Stand: {now.isoformat()} · Status: **{report['status']}**", '',
             '**Keine Kaufalarme. Keine belegte Trefferquote.** Frische Meldung bedeutet nicht frühe Kurschance.', '',
             '## Quellenzustand', '', '| Quelle | Status | Einträge | Lücke/Fehler |', '|---|---|---:|---|']
    for name, s in sources.items():
        lines.append(f"| {esc(name)} | {s['status']} | {s['count']} | {esc(s.get('error') or s.get('coverage_warning') or 'keine erkannte; Vollständigkeit nicht garantiert')} |")
    lines += ['', '## Originalmeldungen · letzte 24 Stunden', '']
    for r in recent[:30]:
        lines += [f"- **{esc(r['status'])}** · [{esc(r['title'])}]({r['url']})", f"  Quelle: {esc(r['source'])} · Feedzeit: {r['published_utc']} · entdeckt: {r['first_seen_utc']}"]
    if not recent:
        lines += ['Keine zeitlich zuordenbaren Meldungen im erfassten Fenster. Quellenstatus beachten.']
    lines += ['', '## Momentum-Beobachtungen · keine Handelssignale', '', '| Symbol | Tagesänderung | Seit vorherigem Scan | Tagesvolumen / Ø ganzer Tag | Status |', '|---|---:|---:|---:|---|']
    for r in sorted(market, key=lambda r: (r['status'] != 'MOMENTUM PRÜFEN', -r['change_pct']))[:20]:
        lines.append(f"| {esc(r['symbol'])} | {r['change_pct']}% | {r['change_since_previous_scan_pct'] if r['change_since_previous_scan_pct'] is not None else 'offen'} | {r['relative_full_day_volume']} | {r['status']} |")
    lines += ['', 'Kurse in Rohdaten mit Originalwährung und Zeitstempel. EUR-Umrechnung erst mit geprüftem Wechselkurs. Tagesänderung ist nicht die Reaktion seit einer Nachricht.', '', 'Trefferquote: nicht vorhanden. Journal enthält auch Fehlabrufe und alle erfassten Marktbeobachtungen. Für +5%-Zieltreffer fehlen noch vollständig geprüfte Signale, Börsenkalender und lückenlose Folgekursdaten.']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(f"{report['status']}: {len(news)} new source items, {len(market)} market observations; {ok}/{len(sources)} sources available")
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(run())
