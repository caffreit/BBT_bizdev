import json,glob,re
from urllib.parse import urlparse
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
def dom(u):
    h=urlparse(u if '://' in (u or '') else 'http://'+(u or '')).netloc.lower()
    return h[4:] if h.startswith('www.') else h
def norm(n): return re.sub(r'[^a-z0-9]','',(n or '').lower())
new=sorted(glob.glob('data/*2026-10-28.json'))
known_n,known_d={},{}
for f in glob.glob('data/*_????-??-??.json'):
    if f in new: continue
    try: d=json.load(open(f))
    except Exception: continue
    recs=d.get('records',[]) if isinstance(d,dict) else d
    for r in recs:
        if not isinstance(r,dict): continue
        c=r.get('company') or r.get('company_name') or ''
        if c: known_n.setdefault(norm(c),set()).add(r.get('source_name') or f)
        w=dom(r.get('website',''))
        if w: known_d.setdefault(w,set()).add(r.get('source_name') or f)
cols=['company','source_name','source_type','geography','website','category_or_track','cohort_label','cohort_year','product_type','company_description','discovery_url','matched_terms']
wb=Workbook(); summ=wb.active; summ.title='Summary'
allrows=[];S=[]
for f in new:
    d=json.load(open(f)); recs=d['records']
    ws=wb.create_sheet(d['source']['name'][:31].replace('/',' '))
    ws.append(cols+['already_known','known_in_sources'])
    nn=0
    for r in recs:
        k=known_n.get(norm(r['company']),set())|known_d.get(dom(r.get('website','')),set())
        row=[r.get(c,'') for c in cols]+['yes' if k else 'NEW','; '.join(sorted(k))]
        ws.append(row); allrows.append(row); nn+= (not k)
    S.append([d['source']['name'],d['source']['source_type'],d['result'],len(recs),nn,len(recs)-nn,d['source']['url']])
a=wb.create_sheet('All records',1); a.append(cols+['already_known','known_in_sources'])
for r in allrows: a.append(r)
summ.append(['Source','Type','Run result','Records','Net-new','Already known','URL'])
for s in S: summ.append(s)
summ.append(['TOTAL','','',sum(s[3] for s in S),sum(s[4] for s in S),sum(s[5] for s in S)])
uniq={}
for r in allrows: uniq.setdefault(norm(r[0]),r)
summ.append(['Unique companies across sources','','',len(uniq)])
for ws in wb:
    for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='1F3864')
    ws.freeze_panes='A2'
    for i in range(1,ws.max_column+1):
        ws.column_dimensions[get_column_letter(i)].width=45 if ws.title=='Summary' and i in(3,7) else 28
    for row in ws.iter_rows(min_row=2):
        for c in row: c.alignment=Alignment(wrap_text=False,vertical='top')
from bbt_bizdev.adapters.canada_ai_institutes import INSTITUTE_UNCONFIRMED_LEADS
u=wb.create_sheet('Unconfirmed leads',2); u.append(['company','institute','why unconfirmed (not in pipeline data)'])
for r in INSTITUTE_UNCONFIRMED_LEADS: u.append(list(r))
wb.save('outputs/canada_ai_institutes_startups_2026-10-28.xlsx')
for s in S: print(s[:6])
print(len(allrows),len(uniq))
