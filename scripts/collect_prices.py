import json,os,urllib.request,urllib.parse,re,datetime,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parent.parent
products=json.loads((ROOT/'data/products.json').read_text())['products']
key=os.getenv('SCRAPPA_API_KEY','')
if not key: raise SystemExit('No SCRAPPA_API_KEY: Live-Erfassung ausgesetzt')
trusted={'galaxus','mindfactory','alternate','notebooksbilliger','computeruniverse','cyberport','alza','proshop','caseking','jacob','voelkner','reichelt','mediamarkt','saturn','x-kom','expert'}
bad=re.compile('ebay|amazon|marketplace|gebraucht|refurb|b-ware',re.I)
def clean_shop(s):
 s=re.sub(r'^(DE|Deutschland)\\s+','',str(s).strip(),flags=re.I).lower()
 return (not bad.search(s)) and any(s==k or s.startswith(k+'.') or s.startswith(k+' ') for k in trusted)
def available(x):
 if x is True:return True
 if not x:return False
 s=str(x).lower()
 if re.search('nicht|kein|out of stock|sold out|unavailable|vorbestellung|ab mitte|lieferbar ab|auf lager ab|4-6 wochen',s):return False
 return bool(re.search('lagernd|auf lager|sofort|lieferbar|verfügbar|available|in stock|1-2 werktage|2-3 werktage',s))
def price(x):
 if isinstance(x,dict):
  if x.get('currency','EUR') not in ('EUR','€'):return None
  x=x.get('eur_value',x.get('value',x.get('amount')))
 try:
  if isinstance(x,str):
   x=re.sub('[^0-9,.]','',x)
   if ',' in x:x=x.replace('.','').replace(',','.')
  return float(x)
 except (ValueError,TypeError):return None
now=datetime.datetime.now(datetime.timezone.utc)
today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))).date().isoformat()
try:
 from zoneinfo import ZoneInfo
 today=datetime.datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat()
except ImportError: pass
good=[];errors=[]
for product in products:
 try:
  url='https://scrappa.co/api/geizhals/product?'+urllib.parse.urlencode({'product_id':product['geizhals_id'],'loc':'de','offers':100,'merchant_details':'true'})
  req=urllib.request.Request(url,headers={'x-api-key':key,'Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=30) as f: data=json.load(f)
  if data.get('success') is not True or str(data.get('product_id'))!=str(product['geizhals_id']) or data.get('loc','de')!='de':raise ValueError('Product identity/schema not verified')
  offers=(data.get('product') or {}).get('offers') or []
  valid=[]
  for o in offers:
   seller=o.get('shop',o.get('merchant',o.get('seller','')))
   if isinstance(seller,dict):seller=seller.get('name','')
   p=price(o.get('price_eur',o.get('price')))
   if not clean_shop(seller) or not available(o.get('avl',o.get('availability',o.get('stock_status')))):continue
   if o.get('condition','new') not in ('new','Neu','neu','Neuware',None) or o.get('currency','EUR') not in ('EUR','€'):continue
   if p is None or p<.25*product['reference_eur'] or p>12*product['reference_eur']:continue
   valid.append((p,str(seller)))
  if not valid:raise ValueError('No eligible new in-stock retail offer')
  p,s=min(valid)
  good.append({'id':product['id'],'price_eur':round(p,2),'merchant':s,'source_url':product['geizhals_url'],'sku':product['sku'],'checked_date':today,'in_stock':True,'new_condition':True,'api_retrieved_at':now.isoformat()})
 except Exception as exc:
  errors.append({'id':product['id'],'reason':str(exc)[:160]})
 time.sleep(.2)
folder=ROOT/'data'/'observations';folder.mkdir(exist_ok=True,parents=True)
out={'date':today,'provider':'scrappa_geizhals_product','retrieved_at':now.isoformat(),'offers':good,'problems':errors}
(folder/(today+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Observed',len(good),'of',len(products),'products. Problems:',len(errors))
