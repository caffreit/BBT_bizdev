"""Score saved broad research against the baseline without new API requests."""
import argparse
import hashlib
import inspect
from datetime import date
from collections import Counter
import json
from pathlib import Path
from bbt_bizdev.canada_executive_broad import report
from bbt_bizdev.canada_executive_investigation import VERSION, _save, assess_claim
from bbt_bizdev.adapters.linkedin import canonicalize_linkedin_url
from research_canada_executives import OUT, SOURCE, read_csv, read_rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    parser.add_argument('--sync-identity', action='store_true', help='Attach source-workbook alias metadata before an offline gate replay')
    parser.add_argument('--reassess',action='store_true',help='Replay the current gate on retained evidence; makes no network calls')
    args=parser.parse_args(); root=args.directory
    companies=json.loads((root/'company_inputs.json').read_text())
    truth=json.loads((root/'truth.json').read_text())
    records=[json.loads((root/c['row_id']/'record.json').read_text()) for c in companies
             if (root/c['row_id']/'record.json').exists()]
    source_by_id = {c['row_id']:c for c in read_rows(SOURCE)} if args.sync_identity else {}
    metadata_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest() if args.sync_identity else ''
    gate_hash = hashlib.sha256(Path(inspect.getfile(assess_claim)).read_bytes()).hexdigest()
    if args.reassess:
        for record in records:
            same_metadata = not args.sync_identity or all(record['company'].get(key) == source_by_id[record['company']['row_id']][key]
                for key in ('identity_issue','identity_reviews','source_website'))
            if not record.get('completed') or (record.get('gate_version') == VERSION and record.get('gate_source_sha256') == gate_hash and same_metadata):
                continue
            record.setdefault('gate_history', []).append({'version':record.get('gate_version','legacy'),
                'company':dict(record['company']), 'decisions':record['decisions'], 'assessments':record.get('assessments',[])})
            if args.sync_identity:
                source = source_by_id[record['company']['row_id']]
                record['company'].update({key:source[key] for key in ('identity_issue','identity_reviews','source_website')})
                record['identity_metadata_source'] = {'path':str(SOURCE),'sha256':metadata_hash}
            record['decisions'] = [dict(row) for row in record['decisions']]
            record['assessments'] = [dict(a) for a in record.get('assessments',[])]
            assert len(record['decisions']) == len(record['assessments'])
            for row,a in zip(record['decisions'],record['assessments']):
                ok,reason,refs=assess_claim(record['company'],a['claim'],record['sources'],
                    company_verdict=record['claims']['company_verdict'],company_status=record['claims']['company_status'],
                    conflict_checked=a['conflict_checked'],today=date.fromisoformat(record['started_at'][:10]))
                row.update(decision='accept' if ok else 'pending',reason=reason,
                    identity_verified='yes' if ok else '',employment_verified='yes' if ok else '',linkedin_verified='yes' if ok else '')
                a.update(reason=reason,evidence_ids=refs)
            record['gate_version']=VERSION
            record['gate_source_sha256']=gate_hash
            _save(root/record['company']['row_id']/'record.json',record)
    summary=report(companies,truth,records,root)
    summary['attempted']=len(records)
    summary['unknown_cost_requests'] = sum(e.get('response',{}).get('usage',{}).get('cost') is None for r in records for e in r['requests'])
    summary['companies_with_unknown_cost'] = [r['company']['company'] for r in records if any(e.get('response',{}).get('usage',{}).get('cost') is None for e in r['requests'])]
    summary['not_started']=[c['company'] for c in companies if not (root/c['row_id']/'record.json').exists()]
    summary['pending_reasons']=dict(Counter(d['reason'] for r in records for d in r['decisions'] if d['decision']=='pending'))
    summary['model_supported']=sum(a['claim']['verdict']=='supported' for r in records for a in r.get('assessments',[]))
    summary['cost_overshoot_usd']=sum(r.get('cost_overshoot_usd',0) for r in records)
    summary['average_company_cost_usd']=summary['cost_usd']/len(records) if records else 0
    all_baseline={(d['row_id'],canonicalize_linkedin_url(d['linkedin_url'],'person')) for d in read_csv(OUT/'decisions.csv') if d['decision']=='accept'}
    selected=json.loads((root/'selected.json').read_text())
    summary['accepted_outside_all_historical_accepts']=sum((d['row_id'],d['linkedin_url']) not in all_baseline for d in selected)
    _save(root/'summary.json',summary)
    comparisons=json.loads((root/'comparison.json').read_text())
    lines=['# Broad Luna investigation: 25-company benchmark','',
           'The historical list contains 37 selected contacts. It was used only for scoring, after company research. All decisions below were made programmatically.','',
           f"Companies completed: {summary['completed']}/{summary['companies']}. Candidate claims: {summary['candidates']}. Selected: {summary['selected']}. Pending: {summary['pending']}.",'',
           f"Known-good exact profiles proposed: {summary['known_good_proposed']}/37. Known-good profiles selected: {summary['known_good_recovered']}/37. Matching uses company row and canonical personal LinkedIn URL; name variants do not count as separate people.",'',
           f"Reported cost: ${summary['cost_usd']:.6f}. Average per attempted company: ${summary['average_company_cost_usd']:.4f}. Maximum: ${summary['max_company_cost_usd']:.4f}. Overshoot: ${summary['cost_overshoot_usd']:.6f}.",'',
           f"Requests with unreported cost: {summary['unknown_cost_requests']}. Reported spend excludes these requests.",'',
           '| Company | Historical selected | Candidates | Selected now | Recovered |',
           '| --- | ---: | ---: | ---: | ---: |']
    for c in comparisons:
        lines.append(f"| {c['company']} | {c['baseline']} | {c['proposed']} | {c['selected']} | {c['recovered']} |")
    lines+=['','## Pending reasons','']+[f'- {reason}: {count}' for reason,count in summary['pending_reasons'].items()]
    lines+=['','## Interpretation','',
        'Proposed means Luna returned the exact historical profile in a candidate claim. Selected means the claim also passed company identity, current role, profile identity and conflict checks, then the three-person company cap. Pending is not a finding that the person is wrong.', '',
        ('Two research calls allow up to six server searches each. A draft structured call lets Python diagnose missing evidence before round two; a final structured call packages the findings.' if any(r.get('research_feedback') for r in records) else 'The two research calls allow up to six server searches each. A third call structures the evidence.') + ' Python fetches official pages and runs explicit conflict searches for supported candidates. Server citations are retained as indexed excerpts; the full internal search trace may not be exposed.', '',
        'A new directory is required for a fresh experiment. Completed records replay without paid calls. Interrupted records require billing reconciliation and do not silently restart. The $1 per-company control reserves an allowance before a request; any final-request overshoot is reported because actual cost arrives afterward. Historical baseline files are unchanged.']
    if any(r.get('repackaged') for r in records):
        lines += ['', '## Experiment corrections', '',
            'The corrected structured-output pass uses retained research and preserves initial claims and decisions. The conflicts field now contains only unresolved contradictory evidence. An offline gate replay also fixes the generic closed-financing/closed-company confusion. No manual per-contact decisions were made. Reported spend includes both extraction passes; do not add the original run subtotal again.']
    (root/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
