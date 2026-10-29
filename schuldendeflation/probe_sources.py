from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
urls = {
"goldprice_public":"https://api.goldprice.dev/v1/public/xau-history",
"xaus_history":"https://xaus.com/api/v1/history",
"corgano_history":"https://goldprice.corgano.com/api/v1/history?year=2026",
"vnq_yahoo":"https://query1.finance.yahoo.com/v8/finance/chart/VNQ?range=1y&interval=1d",
"fred_hy":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2&cosd=2026-04-01"
}
def check(name,url):
 try:
  req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json,text/csv,*/*"})
  with urlopen(req,timeout=16) as r:
   raw=r.read(650)
   return f"{name}: status={r.status}, type={r.headers.get('content-type')}, sample={raw.decode('utf-8-sig','replace')[:500]!r}"
 except Exception as e:return f"{name}: ERROR={str(e)[:250]}"
with ThreadPoolExecutor(max_workers=5) as pool:
 for result in pool.map(lambda pair:check(*pair),urls.items()):print(result)
