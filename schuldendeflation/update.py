#!/usr/bin/env python3
"""Schuldendeflationsradar: source-labelled daily observations, no fabricated values."""
import csv
import io
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data.json"
NOW = datetime.now(timezone.utc)
TODAY = NOW.astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
BASE_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?"
SERIES = ("BAMLH0A0HYM2", "BAMLHE00EHYIOAS", "VIXCLS", "SOFR", "IORB",
          "SP500", "STLFSI4", "DFII10", "WALCL")
LIMITS = {"BAMLH0A0HYM2": 6, "BAMLHE00EHYIOAS": 6, "VIXCLS": 6,
          "SOFR": 6, "IORB": 6, "SP500": 6, "STLFSI4": 15,
          "DFII10": 6, "WALCL": 14}
URLS = {s: BASE_FRED + urlencode({"id": s, "cosd": "2025-01-01"}) for s in SERIES}
URLS.update({"GOLD": "https://api.gold-api.com/price/XAU",
             "VNQ": "https://query1.finance.yahoo.com/v8/finance/chart/VNQ?range=1mo&interval=1d"})
MAXPOINTS = {"us_hy":30, "vix":15, "funding":15, "drawdown":15, "eu_hy":15, "stlfsi":10}

def read_url(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SchuldendeflationRadar/1.0; research)", "Accept": "text/csv,application/json,*/*"})
    with urlopen(req, timeout=20) as response:
        content = response.read(3500000)
    return content.decode("utf-8-sig")

def fred(code):
    text = read_url(URLS[code])
    rows = csv.reader(io.StringIO(text))
    head = next(rows)
    if len(head) < 2 or code not in head:
        raise ValueError("Unexpected FRED CSV header for " + code)
    index = head.index(code)
    output = []
    for row in rows:
        if len(row) <= index:
            continue
        try:
            value = float(row[index])
            day = datetime.strptime(row[0][:10], "%Y-%m-%d").date()
            if math.isfinite(value) and day <= NOW.date():
                output.append((day, value))
        except (ValueError, IndexError):
            continue
    if not output:
        raise ValueError("No numeric observations: " + code)
    return sorted(output)

def latest(series, days=6):
    day, value = series[-1]
    if (NOW.date() - day).days > days:
        return None
    return {"date":day.isoformat(), "value":round(value,5)}

def last_in_window(series, end, days=5):
    chosen = [(d,v) for d,v in series if end - timedelta(days=days) <= d <= end]
    return chosen[-1] if chosen else None

def gold():
    obj = json.loads(read_url(URLS["GOLD"]))
    value = float(obj["price"])
    assert value > 0 and math.isfinite(value)
    updated = obj.get("updatedAt") or obj.get("updated_at")
    if updated:
        age = NOW - datetime.fromisoformat(str(updated).replace("Z","+00:00")).astimezone(timezone.utc)
        if age > timedelta(days=2) or age < timedelta(days=-1):
            raise ValueError("Gold quote is not recent")
    return {"value":round(value,3), "observed_at":updated or NOW.isoformat(),
            "observation_kind":"Spot-Momentaufnahme, kein offizieller Schlusskurs",
            "url": URLS["GOLD"]}

def vnq():
    obj = json.loads(read_url(URLS["VNQ"]))
    result = obj["chart"]["result"][0]
    times = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    valid = [(datetime.fromtimestamp(t, timezone.utc).date(),float(c)) for t,c in zip(times,closes) if c is not None and c > 0 and math.isfinite(float(c))]
    if not valid:
        raise ValueError("No VNQ close")
    day,val = valid[-1]
    if (NOW.date()-day).days > 6:
        raise ValueError("VNQ quote is stale")
    return {"value":round(val,3),"observed_at":day.isoformat(),
            "observation_kind":"ETF-Tagesschlusskurs, Immobilienaktien-Proxy",
            "url": URLS["VNQ"]}

def score_part(name, value):
    if value is None: return None
    if name == "us_hy": return 0 if value <= 3.5 else 10 if value <= 5 else 20 if value <= 7 else 30
    if name == "eu_hy": return 0 if value < 4 else 5 if value < 6 else 10 if value <= 8 else 15
    if name == "vix": return 0 if value <= 20 else 5 if value <= 30 else 10 if value <= 40 else 15
    if name == "funding": return 0 if value <= .10 else 5 if value <= .25 else 10 if value <= .50 else 15
    if name == "drawdown": return 0 if value < 10 else 5 if value < 20 else 10 if value < 30 else 15
    if name == "stlfsi": return 0 if value < 0 else 5 if value < 1 else 10

def main():
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"records":[]}
    histories = {}; errors = {}
    jobs = list(SERIES) + ["GOLD","VNQ"]
    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = {pool.submit(gold if s=="GOLD" else vnq if s=="VNQ" else fred, *(()) if s in ("GOLD","VNQ") else (s,)):s for s in jobs}
        for future in as_completed(futures):
            key=futures[future]
            try: histories[key]=future.result()
            except Exception as exc: errors[key]=str(exc)[:180]
    latest_values = {s:latest(histories[s], LIMITS[s]) if s in histories else None for s in SERIES}
    metrics = {}
    for code in SERIES:
        item = latest_values[code]
        metrics[code] = ({**item,"url":URLS[code]} if item else None)
        if code in histories and item is None: errors[code]="Letzter Datenstand zu alt"
    sofr = histories.get("SOFR",[])
    iorb = histories.get("IORB",[])
    financing = None
    if sofr and iorb:
        matched = {d:(v,w) for d,v in sofr for d2,w in iorb if d==d2 and (NOW.date()-d).days<=6}
        if matched:
            day=max(matched)
            # Percentage points, not percent change.
            financing=round(matched[day][0]-matched[day][1],5)
            metrics["SOFR_MINUS_IORB"]={"value":financing,"date":day.isoformat(),"url":URLS["SOFR"]}
    drawdown=None
    sp=histories.get("SP500",[])
    if latest_values.get("SP500") and sp:
        day,value=sp[-1]
        window=[v for d,v in sp if day-timedelta(days=183)<=d<=day]
        if window:
            drawdown=round(100*(max(window)-value)/max(window),5)
            metrics["SP500_DRAWDOWN"]={"value":drawdown,"date":day.isoformat(),"url":URLS["SP500"]}
    def v(code):
        obj=latest_values.get(code)
        return obj["value"] if obj is not None else None
    inputs={"us_hy":v("BAMLH0A0HYM2"),"eu_hy":v("BAMLHE00EHYIOAS"),"vix":v("VIXCLS"),
            "funding":financing,"drawdown":drawdown,"stlfsi":v("STLFSI4")}
    points={key:score_part(key,val) for key,val in inputs.items()}
    covered=sum(x is not None for x in points.values())
    used_max=sum(MAXPOINTS[k] for k,p in points.items() if p is not None)
    score=round(sum(p for p in points.values() if p is not None)*100/used_max,1) if inputs["us_hy"] is not None and covered>=4 else None
    fed_4w=None
    walcl=histories.get("WALCL",[])
    if walcl and latest_values.get("WALCL"):
        day,val=walcl[-1]
        before=last_in_window(walcl,day-timedelta(days=28),7)
        if before:
            fed_4w=round(val-before[1],3) # WALCL is millions USD
            metrics["FED_4W_MILLION_USD"]={"value":fed_4w,"date":day.isoformat(),"url":URLS["WALCL"]}
    assets={}
    for name in ("GOLD","VNQ"):
        if name in histories: assets[name]=histories[name]
    if latest_values.get("SP500"):
        assets["SP500"]={"value":latest_values["SP500"]["value"],"observed_at":latest_values["SP500"]["date"],"observation_kind":"US-Indexschlusskurs","url":URLS["SP500"]}
    record={"date":TODAY,"collected_at":NOW.isoformat(timespec="seconds"),"score":score,
            "coverage":covered,"inputs":inputs,"points":points,"metrics":metrics,"assets":assets,
            "errors":errors,"phase":("unvollstaendig" if score is None else "ruhig" if score<20 else "angespannt" if score<40 else "warnung" if score<65 else "akute_krise"),
            "method":"Heuristischer Marktstress, keine Krisenprognose; fehlende Komponenten NICHT null."}
    rows=[r for r in old.get("records",[]) if r.get("date")!=TODAY]
    rows.append(record)
    old.update({"schema_version":1,"updated_at":NOW.isoformat(timespec="seconds"),"timezone":"Europe/Berlin",
                "source":"Automatische externe Datenabfrage; keine verifizierte Zentralbank-Interventionsklassifikation",
                "records":sorted(rows,key=lambda r:r["date"])[-500:]})
    OUTPUT.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":TODAY,"score":score,"coverage":covered,"assets":list(assets),"errors":errors},ensure_ascii=False))

if __name__=="__main__":main()
