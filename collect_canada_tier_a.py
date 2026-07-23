from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from bbt_bizdev.adapters.canada_tier_a import (
    run_cts_sante,
    run_district3,
    run_innovation_ubc,
    run_medteq,
    run_obio,
    run_ualberta,
    run_uceed,
)
from bbt_bizdev.config import SOURCES


RUNNERS = {
    "cts_sante_portfolio": (run_cts_sante, "cts_sante_portfolio"),
    "district3_health": (run_district3, "district3_bio_health_startups"),
    "obio_cohorts": (run_obio, "obio_named_health_cohorts"),
    "medteq_portfolio": (run_medteq, "medteq_investment_portfolio"),
    "uceed_health": (run_uceed, "uceed_health_portfolios"),
    "ualberta_health_hub": (run_ualberta, "ualberta_health_innovation_hub_companies"),
    "innovation_ubc_health": (run_innovation_ubc, "innovation_ubc_human_health_portfolio"),
}
SNAPSHOT_DATE = "2026-07-23"


def main() -> None:
    Path("data").mkdir(exist_ok=True)
    Path("outputs").mkdir(exist_ok=True)
    sources = {source.adapter: source for source in SOURCES if source.adapter in RUNNERS}
    for adapter, (runner, filename) in RUNNERS.items():
        source = sources[adapter]
        hits, triggers, result = runner(source)
        payload = {
            "snapshot_date": SNAPSHOT_DATE,
            "source": asdict(source),
            "result": result,
            "records": [asdict(hit) for hit in hits],
        }
        json_path = Path("data") / f"{filename}_{SNAPSHOT_DATE}.json"
        csv_path = Path("outputs") / f"{filename}_{SNAPSHOT_DATE}.csv"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        rows = payload["records"]
        if rows:
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        print(f"{adapter}: {result}; JSON={json_path}; CSV={csv_path}; triggers={len(triggers)}")


if __name__ == "__main__":
    main()
