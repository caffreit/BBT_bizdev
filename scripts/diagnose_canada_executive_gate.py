"""Compare two evidence replays and explain identity/role failures without API calls."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
from bbt_bizdev.canada_executive_investigation import (
    _current_role_mention, _recent, _same_url, company_identity_evidence, same_host, _save,
)
from bbt_bizdev.adapters.linkedin import canonicalize_linkedin_url


def diagnose(record, assessment):
    identity=company_identity_evidence(record['company'],record['sources'])
    verdict=record['claims']['company_verdict'];status=record['claims']['company_status']
    if verdict!='supported':return 'company_verdict_'+verdict
    if status!='active':return 'company_status_'+status
    if not identity['verified']:return identity['reason']
    claim=assessment['claim']
    if assessment['reason']!='role_evidence_insufficient':return assessment['reason']
    if canonicalize_linkedin_url(claim['role_url'],'person'):return 'personal_profile_is_only_role_source'
    matching=[s for s in record['sources'] if _same_url(s['url'],claim['role_url'])]
    if not matching:return 'role_url_has_no_retained_source'
    supporting=[s for s in matching if _current_role_mention(s.get('excerpt',''),claim['name'],claim['title'])]
    if not supporting:return 'source_does_not_pair_person_with_claimed_role'
    today=date.fromisoformat(record['started_at'][:10])
    if all(s.get('published_at') and not _recent(s['published_at'],today) for s in supporting):
        return 'dated_role_needs_newer_corroboration'
    if not same_host(claim['role_url'],identity['website']):return 'external_or_previous_domain_role_source_not_qualified'
    return 'role_source_type_or_attribution_unverified'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('previous',type=Path);parser.add_argument('current',type=Path)
    args=parser.parse_args(); transitions=[];remaining=Counter();targeted=0;cleared=0;fully_accepted=0
    for path in args.current.glob('wp*/record.json'):
        current=json.loads(path.read_text());old=json.loads((args.previous/path.parent.name/'record.json').read_text())
        before={a['claim']['name']:a for a in old.get('assessments',[])}
        for a in current.get('assessments',[]):
            previous=before[a['claim']['name']]
            target=previous['reason'] in {'company_identity_or_activity_unverified','role_evidence_insufficient'}
            moved=target and previous['reason']!=a['reason']
            targeted+=target;cleared+=moved
            accepted=any(d['name']==a['claim']['name'] and d['decision']=='accept' for d in current['decisions'])
            fully_accepted+=target and accepted
            detail=diagnose(current,a)
            if a['reason'] in {'company_identity_or_activity_unverified','role_evidence_insufficient'}:
                remaining[detail]+=1
            transitions.append({'company':current['company']['company'],'name':a['claim']['name'],
                'before':previous['reason'],'after':a['reason'],'diagnostic':detail,
                'original_target':target,'accepted':accepted})
    summary={'targeted_candidates':targeted,'original_blocker_cleared':cleared,
             'targeted_now_fully_accepted':fully_accepted,'remaining_identity_role_diagnostics':dict(remaining),
             'additional_api_requests':0,'additional_reported_cost_usd':0}
    _save(args.current/'bottleneck_diagnostics.json',{'summary':summary,'candidates':transitions})
    lines=['# Identity and role gate replay','',f"Original identity/role failures: {targeted}. Original blockers cleared: {cleared}. Newly accepted after all checks: {fully_accepted}.",'',
           'This replay makes no new API calls. Candidate claims and evidence are unchanged. Workbook alias metadata is read from its source and retained with the decisions. Earlier decisions remain in each record’s gate history.','',
           '## Remaining identity and role blockers','']
    lines += [f'- {reason}: {count}' for reason,count in remaining.items()]
    lines += ['','## Changed decisions','','| Company | Person | Before | After |','| --- | --- | --- | --- |']
    for row in transitions:
        if row['before']!=row['after']:lines.append(f"| {row['company']} | {row['name']} | {row['before']} | {row['after']} |")
    (args.current/'BOTTLENECK_REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
