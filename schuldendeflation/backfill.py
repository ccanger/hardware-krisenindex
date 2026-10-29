#!/usr/bin/env python3
"""Reconstruct past observations from actual dated FRED values.
This is a retrospective reconstruction, not a point-in-time investment backtest.
Gold uses independent daily XAU/USD spot closing observations.
"""
import csv,io,json,math
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed
import update as core
ROOT=Path(__file__).resolve().parent
START=date(2026,4,29)
END=date(2026,10,28)
codes=core.SERIES
def download(c):
 return core.fred(c)
def yahoo(ticker):
 import urllib.parse
 url="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(ticker,safe='')+"?range=1y&interval=1d"
 data=json.loads(core.read_url(url))['chart']['result'][0]
 arr=data['indicators']['quote'][0]['close']
 result={}
 for stamp,val in zip(data['timestamp'],arr):
  if val is not None and math.isfinite(float(val)) and float(val)>0:
   d=datetime.fromtimestamp(stamp,timezone.utc).date()
   if START<=d<=END:result[d]=round(float(val),4)
 return result,url
def nearest_on_or_before(rows,d,limit):
 eligible=[(dd,v) for dd,v in rows if dd<=d and (d-dd).days<=limit]
 return eligible[-1] if eligible else None
def main():
 hist={};errors={}
 with ThreadPoolExecutor(max_workers=6) as pool:
  fs={pool.submit(download,c):c for c in codes}
  for f in as_completed(fs):
   c=fs[f]
   try:hist[c]=f.result()
   except Exception as e:errors[c]=str(e)[:160]
 assets={}
 def gold_spot():
  url="https://api.goldprice.dev/v1/public/xau-history"
  obj=json.loads(core.read_url(url))
  if obj.get('symbol')!='XAU-USD-SPOT' or obj.get('interval')!='1d':
   raise ValueError("Unexpected XAU/USD historical source")
  samples={}
  for row in obj['series']:
   day=date.fromisoformat(row['date']);price=float(row['close'])
   if START<=day<=END and math.isfinite(price) and price>0:
    samples[day]=round(price,4)
  return samples,url
 with ThreadPoolExecutor(max_workers=2) as pool:
  fs={pool.submit(yahoo,'VNQ'):'VNQ',pool.submit(gold_spot):'XAU_SPOT'}
  for f in as_completed(fs):
   try:assets[fs[f]]=f.result()
   except Exception as e:errors[fs[f]]=str(e)[:160]
 old=json.loads((ROOT/'data.json').read_text())
 previous={r['date']:r for r in old.get('records',[])}
 rows=[]
 d=START
 while d<=END:
  # No artificial weekend observation; on holidays a valid FRED series may be absent
  if d.weekday()>=5:d+=timedelta(days=1);continue
  metrics={}; vals={}
  for c in codes:
   item=nearest_on_or_before(hist.get(c,[]),d,core.LIMITS[c])
   # daily observations must correspond to the actual session, except weekly STLFSI4 and WALCL.
   if c not in ('STLFSI4','WALCL') and (not item or item[0]!=d):item=None
   vals[c]=item[1] if item else None
   metrics[c]=({'date':item[0].isoformat(),'value':round(item[1],5),'url':core.URLS[c]} if item else None)
  funding=None
  if vals['SOFR'] is not None and vals['IORB'] is not None:
   funding=round(vals['SOFR']-vals['IORB'],5)
   metrics['SOFR_MINUS_IORB']={'date':d.isoformat(),'value':funding,'url':core.URLS['SOFR']}
  draw=None
  if vals['SP500'] is not None:
   w=[v for dt,v in hist.get('SP500',[]) if d-timedelta(days=183)<=dt<=d]
   if w and len(w)>=60:
    draw=round(100*(max(w)-vals['SP500'])/max(w),5)
    metrics['SP500_DRAWDOWN']={'date':d.isoformat(),'value':draw,'url':core.URLS['SP500']}
  inputs={'us_hy':vals['BAMLH0A0HYM2'],'eu_hy':vals['BAMLHE00EHYIOAS'],'vix':vals['VIXCLS'],'funding':funding,'drawdown':draw,'stlfsi':vals['STLFSI4']}
  points={k:core.score_part(k,v) for k,v in inputs.items()}
  cov=sum(v is not None for v in points.values())
  maxp=sum(core.MAXPOINTS[k] for k,v in points.items() if v is not None)
  score=round(sum(v for v in points.values() if v is not None)*100/maxp,1) if inputs['us_hy'] is not None and cov>=4 else None
  aset={}
  if vals['SP500'] is not None:aset['SP500']={'value':round(vals['SP500'],4),'observed_at':d.isoformat(),'url':core.URLS['SP500'],'observation_kind':'S&P 500 Schluss'}
  for ticker,alias,kind in [('VNQ','VNQ','Immobilienaktien ETF Schluss'),('XAU_SPOT','GOLD','XAU/USD Spot Tages-Schlusswert')]:
   if ticker in assets and d in assets[ticker][0]:
    aset[alias]={'value':assets[ticker][0][d],'observed_at':d.isoformat(),'url':assets[ticker][1],'observation_kind':kind}
  rows.append({'date':d.isoformat(),'collected_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
   'score':score,'coverage':cov,'inputs':inputs,'points':points,'metrics':metrics,'assets':aset,
   'errors':{},'phase':('unvollstaendig' if score is None else 'ruhig' if score<20 else 'angespannt' if score<40 else 'warnung' if score<65 else 'akute_krise'),
   'method':'RETROSPEKTIV REKONSTRUIERT, nicht historisch zeitgerecht veröffentlichte Information. Gold XAU/USD Spot Tagesschlusswerte.'})
  d+=timedelta(days=1)
 # Never replace a genuine recorded live observation
 for r in rows:
  previous[r['date']]=r
 ordered=sorted(previous.values(),key=lambda r:r['date'])
 old['records']=ordered[-500:]
 old['historical_backfill']={'start':START.isoformat(),'end':END.isoformat(),'data_type':'retrospective reconstruction, no publication-lag adjustment','gold_history':'XAU/USD spot daily close from goldprice.dev','source_errors':errors,'backfilled_at':datetime.now(timezone.utc).isoformat()}
 (ROOT/'data.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
 valid=sum(x['score'] is not None for x in rows)
 print('BACKFILL',len(rows),'valid scores',valid,'assets',list(assets),'errors',errors)
if __name__=='__main__':main()
