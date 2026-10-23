import json,pathlib,sys,datetime,math
root=pathlib.Path(__file__).resolve().parent.parent
products=json.loads((root/'data/products.json').read_text())['products']
mapping={p['id']:p for p in products}
groups={x:[] for x in ['ram','ssd','gpu','hdd']}
weights={'ram':.4,'ssd':.3,'gpu':.2,'hdd':.1}
obs=json.loads(pathlib.Path(sys.argv[1]).read_text())
date=obs['date']
if date!=datetime.datetime.now(datetime.timezone.utc).date().isoformat() and date!=datetime.datetime.now().date().isoformat():
 # A Europe/Berlin date can be one day ahead of UTC around midnight.
 from zoneinfo import ZoneInfo
 if date!=datetime.datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat():raise SystemExit('Observation not from current date')
seen=set(); offers=[]
for row in obs['offers']:
 id=row['id']
 if id not in mapping or id in seen:raise SystemExit('Unknown or duplicate product')
 seen.add(id);p=mapping[id]
 value=float(row['price_eur'])
 if not math.isfinite(value) or value<=0 or row['sku']!=p['sku'] or row['source_url']!=p['geizhals_url'] or row['checked_date']!=date or row['in_stock'] is not True or row['new_condition'] is not True:raise SystemExit('Invalid quote')
 groups[p['group']].append(value/p['reference_eur'])
 offers.append(row)
coverage={g:{'observed':len(groups[g]),'required':sum(p['group']==g for p in products)//2} for g in groups}
complete=all(v['observed']>=v['required'] for v in coverage.values())
rel={g:sum(groups[g])/len(groups[g]) if groups[g] else None for g in groups}
hki=round(331.6*sum(weights[g]*rel[g] for g in groups),2) if complete else None
file=root/'data/daily.json';data=json.loads(file.read_text())
entry={'date':date,'hki':hki,'complete':complete,'coverage':coverage,'relative_groups':rel,'offers':offers,'quality':'api_filtered' if complete else 'insufficient_quotes','note':'Drittanbieter-API, keine unabhängige Händlerbestätigung; Produktklassenpreisbasis und SKU-Mix sind verschieden.'}
data['entries']=sorted([e for e in data.get('entries',[]) if e['date']!=date]+[entry],key=lambda x:x['date'])
data['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'date':date,'hki':hki,'coverage':coverage},ensure_ascii=False))
