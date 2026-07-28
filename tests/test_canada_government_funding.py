import unittest

from bbt_bizdev.canada_government_funding import (
    amount_cad,
    candidate_to_event,
    parse_detail,
    parse_search_results,
)


SEARCH_HTML = """
<div class="row mrgn-bttm-xl mrgn-lft-md">
 <div class="row"><div class="col-sm-8">
 <h4><a href="/grants/record/test"><p><mark>Trexo Robotics</mark> Inc.</p></a></h4>
 </div><div class="col-sm-4 text-right">
 <h4>$466,300.00</h4><h5>Sep 1, 2025</h5></div></div>
 <div class="row mrgn-bttm-md">
 <div class="col-sm-12"><strong>Agreement:</strong> <p>Gait trainer development</p></div>
 <div class="col-sm-12"><strong>Agreement Number:</strong> <p>1034623</p></div>
 <div class="col-sm-12"><strong>Description:</strong> <p>Designing a pediatric walker.</p></div>
 <div class="col-sm-12"><strong>Organization:</strong> National Research Council Canada</div>
 <div class="col-sm-12"><strong>Program Name:</strong> IRAP</div>
 <div class="col-sm-12"><strong>Location:</strong> Mississauga, Ontario</div>
 </div></div>
"""

DETAIL_HTML = """
<div class="row mrgn-bttm-sm"><div class="col-sm-4"><strong>Agreement Type:</strong></div>
<div class="col-sm-8">Contribution</div></div>
<div class="row mrgn-bttm-sm"><div class="col-sm-4"><strong>Recipient's Legal Name:</strong></div>
<div class="col-sm-8">Trexo Robotics Inc.</div></div>
"""


class CanadaGovernmentFundingTests(unittest.TestCase):
    def test_parse_search_and_detail(self):
        rows = parse_search_results(SEARCH_HTML)
        self.assertEqual(1, len(rows))
        self.assertEqual("Trexo Robotics Inc.", rows[0]["recipient_name"])
        self.assertEqual("$466,300.00", rows[0]["amount_original"])
        detail = parse_detail(DETAIL_HTML)
        self.assertEqual("Contribution", detail["Agreement Type"])

    def test_candidate_to_event(self):
        row = parse_search_results(SEARCH_HTML)[0]
        event = candidate_to_event("c1", row, parse_detail(DETAIL_HTML), "2026-07-28")
        self.assertEqual("2025-09-01", event["event_date"])
        self.assertEqual("contribution", event["funding_type"])
        self.assertEqual(466300.0, event["amount_cad"])

    def test_amount_parser(self):
        self.assertEqual(35000.0, amount_cad("$35,000.00"))


if __name__ == "__main__":
    unittest.main()
