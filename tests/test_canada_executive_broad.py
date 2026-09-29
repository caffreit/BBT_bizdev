import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from bbt_bizdev.canada_executive_broad import company_input, investigate, report
from tests.test_canada_executive_investigation import company, claim, homepage, role_source, profile_source


def test_input_has_no_historical_contacts_or_discovered_site():
    c=company();c.update(website='https://discovered.example',candidate_leads=['secret'],accepted=['secret'])
    data=company_input(c)
    assert 'website' not in data and 'secret' not in json.dumps(data)


def test_two_research_rounds_then_structured_claims_and_replay():
    c=company();p=claim();requests=[]
    def request(payload,key):
        requests.append(payload)
        if 'tools' in payload:
            content='Research dossier'
        else:
            content=json.dumps(dict(official_website=c['website'],company_verdict='supported',company_status='active',actions=[],claims=[p]))
        return {'choices':[{'message':{'content':content}}],'usage':{'cost':.01}}
    with TemporaryDirectory() as temp,patch('bbt_bizdev.canada_executive_broad.fetch',return_value={'sources':[homepage(),role_source(),profile_source()]}),patch('bbt_bizdev.canada_executive_broad.search',return_value={'sources':[profile_source()]}):
        record=investigate(c,Path(temp),'test',requester=request)
        assert record['completed'] and len(requests)==4
        assert record['decisions'][0]['decision']=='accept'
        assert record['reported_cost_usd']==.04
        assert requests[0]['tools'][0]['parameters']['max_uses']==6
        assert 'verification_feedback' in requests[2]['messages'][0]['content']
        assert record['research_feedback']['candidates'][0]['missing']==[]
        investigate(c,Path(temp),'test',requester=lambda *a: (_ for _ in ()).throw(AssertionError('paid replay')))
        summary=report([c],[record['decisions'][0]],[record],Path(temp))
        assert summary['known_good_recovered']==1
        updated=investigate(c,Path(temp),'test',requester=request,repackage=True)
        assert len(requests)==5 and 'tools' not in requests[-1]
        assert 'ONLY for unresolved' in requests[-1]['messages'][0]['content']
        assert updated['repackaged'] and updated['reported_cost_usd']==.05
        assert updated['initial_decisions']==record['decisions']


def test_missing_cost_stops_research():
    def request(payload,key):
        return {'choices':[{'message':{'content':'unknown billing'}}]}
    with TemporaryDirectory() as temp,patch('bbt_bizdev.canada_executive_broad.fetch',return_value={'sources':[]}):
        record=investigate(company(),Path(temp),'test',requester=request)
        assert not record['completed'] and len(record['requests'])==1
        assert record['stopped_reason']=='missing_cost_data'


def test_per_company_reserve_stops_before_paid_request():
    with TemporaryDirectory() as temp,patch('bbt_bizdev.canada_executive_broad.fetch',return_value={'sources':[]}):
        record=investigate(company(),Path(temp),'test',ceiling=.04,
                           requester=lambda *a: (_ for _ in ()).throw(AssertionError('over budget')))
        assert not record['completed'] and record['requests']==[]
        assert record['stopped_reason']=='cost_reserve'


def test_incomplete_record_does_not_reset_budget():
    with TemporaryDirectory() as temp:
        root=Path(temp)
        (root/'record.json').write_text(json.dumps({'completed':False,'reported_cost_usd':.9,'requests':[{'state':'in_flight'}]}))
        record=investigate(company(),root,'test',requester=lambda *a: (_ for _ in ()).throw(AssertionError('unsafe retry')))
        assert record['reported_cost_usd']==.9
        assert record['stopped_reason']=='incomplete_run_requires_reconciliation'


def test_feedback_exposes_missing_role_without_using_historical_answers():
    from bbt_bizdev.canada_executive_broad import research_feedback
    c=company();p=claim(role='https://directory.example/person')
    feedback=research_feedback(c,{'claims':[p]},[homepage(),profile_source()])
    assert feedback['company_identity']['verified']
    assert feedback['candidates'][0]['role_check']=='role_evidence_insufficient'
    assert 'current_role' in feedback['candidates'][0]['missing']
    assert feedback['candidates'][0]['name']==p['name']
