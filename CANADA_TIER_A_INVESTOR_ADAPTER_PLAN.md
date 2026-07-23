# Canada Tier A Investor Adapter Record

Tier A investor and funder sources were handled with the same discovery, access, completeness, and testing gates as the accelerator sources. Distinct investment portfolios were extracted; accelerator/funder overlaps were not duplicated.

| Source | Decision | Expected | Extracted | Coverage / note |
| --- | --- | ---: | ---: | --- |
| Lumira Ventures | Dedicated current/exited portfolio adapter | 59 | 59 | 34 current, 25 exited; 22 Canadian-headquarters/presence records |
| Genesys Capital | Dedicated active-investment index/detail adapter | 12 | 12 | Placeholder and 15 acquired/divested past-success cards excluded |
| Amplitude Ventures | Dedicated embedded portfolio-data adapter | 24 | 24 | 20 active, 4 exited |
| BDC | Dedicated current direct-company adapter across six health sectors | 31 | 31 | New Life Sciences Venture Fund has no named portfolio yet; fund-investment records excluded |
| FACIT | Dedicated full investment-portfolio adapter | 56 eligible among 81 | 56 | Excluded 25 institution-owned pre-company assets using an explicit name-prefix rule |
| TIAP | Reuse prior snapshot | 57 | 57 | Existing page is already TIAP’s funded/developed portfolio |
| adMare | Reuse prior snapshot | 52 | 52 | No distinct public adMare Ventures portfolio found |
| UCeed Health funds | Reuse prior snapshot | 42 records | 42 | Existing source is the two health investment-fund portfolios |
| MEDTEQ+ | Reuse prior snapshot | 17 | 17 | Existing source is explicitly the MEDTEQ+ funds portfolio |
| Investissement Québec / BioMed Propulsion | Manual/news treatment | 12 historical recipients reported | No complete public names | Do not automate a three-company or similarly partial list as complete |

The five newly extracted sources produced 182 source records. A normalized comparison against the existing accelerator, hub, and commercialization snapshots found 46 companies appearing in both groups; the overlap CSV retains all source provenance.

All adapters return `INCOMPLETE` if live counts fall below their documented denominators.

Validation: all dedicated investor tests passed; full suite 163/163.
