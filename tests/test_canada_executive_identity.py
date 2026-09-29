from datetime import date
from bbt_bizdev.canada_executive_investigation import company_identity_evidence, _current_role_mention, assess_claim
from tests.test_canada_executive_investigation import company, homepage, claim, role_source, profile_source


def test_observed_homepage_redirect_names_same_company():
    c=company('Example Medical','https://old.example')
    s=homepage(c['company'],c['website']);s['final_url']='https://new.example/'
    result=company_identity_evidence(c,[s])
    assert result['verified'] and result['website']=='https://new.example/'
    s['url']='https://unrelated.example/'
    assert not company_identity_evidence(c,[s])['verified']
    s['url']=c['website'];s['raw_html']='<title>Example Europe</title>'
    assert not company_identity_evidence(c,[s])['verified']


def test_alias_variants_require_single_workbook_domain_and_live_name():
    c=company('Puzzle Medical Devices','https://puzzlemed.com')
    c.update(identity_issue=True,identity_reviews=[{'issue_type':'shared_domain_different_names',
        'names':['Puzzle Medical','Puzzle Medical Devices','Puzzle Medical Devices Inc.'], 'domains':['puzzlemed.com']}])
    home=homepage(c['company'],c['website'])
    assert company_identity_evidence(c,[home])['verified']
    c['identity_reviews'][0]['domains'].append('different.example')
    assert not company_identity_evidence(c,[home])['verified']
    c['identity_reviews'][0]['domains']=['puzzlemed.com']
    c['identity_reviews'][0]['names'].append('Puzzle Robotics')
    assert not company_identity_evidence(c,[home])['verified']


def test_undocumented_alias_or_wrong_name_stays_pending():
    c=company();c['identity_issue']=True
    assert not company_identity_evidence(c,[homepage()])['verified']
    c['identity_issue']=False
    s=homepage('Swiftsure Medical')
    assert not company_identity_evidence(c,[s])['verified']


def test_compound_titles_and_before_name_without_cross_person_pairing():
    assert _current_role_mention('Randy AuCoin President & CEO', 'Randy AuCoin','CEO')
    assert _current_role_mention('CEO Randy AuCoin', 'Randy AuCoin','CEO')
    assert _current_role_mention('Jane Doe FACC FHRS Co-Founder / Chief Medical Officer','Jane Doe','Chief Medical Officer')
    assert not _current_role_mention('Former CEO Randy AuCoin','Randy AuCoin','CEO')
    assert not _current_role_mention('Former President & CEO Randy AuCoin','Randy AuCoin','CEO')
    assert _current_role_mention('Karen Cross MD PhD FRCSC CEO and co-founder','Karen Cross','CEO')
    assert not _current_role_mention('Randy AuCoin former CEO','Randy AuCoin','CEO')
    assert not _current_role_mention('Randy AuCoin Alice Smith CEO','Randy AuCoin','CEO')
    assert not _current_role_mention('Alice Smith CEO Bob Jones COO','Bob Jones','CEO')
    assert _current_role_mention('Alice Smith CEO Bob Jones COO','Bob Jones','COO')


def test_meet_the_team_page_is_eligible_but_archive_remains_pending():
    c=company();p=claim(role='https://swiftmedical.com/meet-the-team')
    source=role_source(url=p['role_url'])
    sources=[homepage(),source,profile_source()]
    options=dict(company_verdict='supported',company_status='active',conflict_checked=True,today=date(2026,9,28))
    assert assess_claim(c,p,sources,**options)[0]
    source['published_at']='2020-01-01'
    assert not assess_claim(c,p,sources,**options)[0]


def test_resolved_redirect_applies_to_role_domain_too():
    c=company();h=homepage();h['final_url']='https://swift.example/'
    p=claim(role='https://swift.example/team')
    ok,reason,refs=assess_claim(c,p,[h,role_source(url=p['role_url']),profile_source()],
        company_verdict='supported',company_status='active',conflict_checked=True)
    assert ok,reason
    assert refs['company_identity']['reason']=='verified_homepage_redirect'
