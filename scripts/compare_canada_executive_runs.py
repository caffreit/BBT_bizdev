"""Compare fresh investigations under a common acceptance gate, without API calls."""
import argparse
import json
from pathlib import Path
from bbt_bizdev.adapters.linkedin import canonicalize_linkedin_url
from bbt_bizdev.canada_executive_investigation import _save
from research_canada_executives import read_csv, write_csv


def load(root):
    return {p.parent.name:json.loads(p.read_text()) for p in root.glob('wp*/record.json')}


def key(row):
    return row['row_id'],canonicalize_linkedin_url(row['linkedin_url'],'person')


def compare(before, after):
    old,new=load(before),load(after)
    provenance=json.loads((after/'provenance/sha256.json').read_text())
    gate_hash=provenance['bbt_bizdev/canada_executive_investigation.py']
    assert all(r.get('gate_source_sha256')==gate_hash for r in old.values() if r.get('completed')), 'Acceptance policy differs'
    truth={key(r) for r in json.loads((before/'truth.json').read_text())}
    assert truth=={key(r) for r in json.loads((after/'truth.json').read_text())}, 'Benchmark labels changed'
    old_selected={key(r) for r in json.loads((before/'selected.json').read_text())}
    new_selected={key(r) for r in json.loads((after/'selected.json').read_text())}
    prior_conflicts = {}
    for rid,record in old.items():
        for assessment in record.get('assessments',[]):
            claim=assessment['claim']
            profile=canonicalize_linkedin_url(claim['linkedin_url'],'person')
            if profile and claim['conflicts']:
                prior_conflicts[(rid,profile)] = claim
    flags=[{'row_id':rid,'linkedin_url':profile,'previous_claim':prior_conflicts[(rid,profile)],
            'reason':'Prior unresolved conflict requires reconciliation with the fresh evidence.'}
           for rid,profile in sorted(new_selected & prior_conflicts.keys())]
    _save(after/'cross_run_conflict_flags.json',flags)
    raw_selected=json.loads((after/'selected.json').read_text())
    flagged={(r['row_id'],r['linkedin_url']) for r in flags}
    _save(after/'review_safe_selected.json',[r for r in raw_selected if key(r) not in flagged])
    safe_decisions=read_csv(after/'decisions.csv')
    for row in safe_decisions:
        if key(row) in flagged:
            row.update(decision='pending', reason='prior_run_conflict_requires_reconciliation', employment_verified='')
    write_csv(after/'review_safe_decisions.csv',safe_decisions)
    rows=[]
    for company in json.loads((after/'company_inputs.json').read_text()):
        rid=company['row_id'];a=old.get(rid,{});b=new.get(rid,{})
        aa={s['url'] for s in a.get('sources',[]) if s.get('url') and not s.get('error')}
        bb={s['url'] for s in b.get('sources',[]) if s.get('url') and not s.get('error')}
        rows.append({'company':company['company'],'row_id':rid,
            'previous_selected':sum(k[0]==rid for k in old_selected),
            'fresh_selected':sum(k[0]==rid for k in new_selected),
            'fresh_candidates':len(b.get('decisions',[])),
            'previous_known_recovered':sum(k[0]==rid for k in truth & old_selected),
            'fresh_known_recovered':sum(k[0]==rid for k in truth & new_selected),
            'new_source_urls':len(bb-aa),'retained_source_urls':len(bb & aa),
            'feedback_used':bool(b.get('research_feedback')),'completed':bool(b.get('completed'))})
    summary={'previous_selected':len(old_selected),'fresh_selected':len(new_selected),
        'previous_known_recovered':len(truth & old_selected),'fresh_known_recovered':len(truth & new_selected),
        'newly_selected_vs_previous':len(new_selected-old_selected),
        'previously_selected_not_recovered':len(old_selected-new_selected),
        'companies_with_additional_source_urls':sum(r['new_source_urls']>0 for r in rows),
        'additional_source_urls':sum(r['new_source_urls'] for r in rows),
        'companies_using_feedback':sum(r['feedback_used'] for r in rows),
        'prior_conflict_flags':len(flags), 'unflagged_selected':len(new_selected-flagged),
        'same_truth_labels':True, 'same_gate_source_sha256':gate_hash}
    _save(after/'fresh_comparison.json',{'summary':summary,'companies':rows})
    lines=['# Fresh investigation compared with evidence replay','',
        f"Selected contacts: {summary['previous_selected']} → {summary['fresh_selected']}. Historical exact profiles accepted: {summary['previous_known_recovered']} → {summary['fresh_known_recovered']} of {len(truth)}.",'',
        f"The fresh run retrieved {summary['additional_source_urls']} additional distinct source URLs across {summary['companies_with_additional_source_urls']} companies. A new URL alone does not establish better evidence.",'',
        f"Prior unresolved conflicts require review for {len(flags)} fresh acceptances. Excluding these automatically flagged contacts leaves {len(new_selected-flagged)} in review_safe_selected.json. The raw run decisions remain unchanged for comparison.",'',
        'The same historical labels are used for scoring only. Both results use the same acceptance policy. A single fresh run is directional evidence, not a controlled estimate of improvement: web indexing, model variation and retrieval errors also affect results.','',
        '| Company | Previous selected | Fresh selected | Previous known recovered | Fresh known recovered | New source URLs |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['company']} | {r['previous_selected']} | {r['fresh_selected']} | {r['previous_known_recovered']} | {r['fresh_known_recovered']} | {r['new_source_urls']} |")
    (after/'FRESH_COMPARISON.md').write_text('\n'.join(lines)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('before',type=Path);parser.add_argument('after',type=Path)
    args=parser.parse_args();print(json.dumps(compare(args.before,args.after)))

if __name__=='__main__':main()
