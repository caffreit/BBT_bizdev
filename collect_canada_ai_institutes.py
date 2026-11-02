from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from bbt_bizdev.adapters.canada_ai_institutes import (
    run_amii_level_up_health,
    run_mila_health_partners,
    run_mila_startups,
    run_vector_ai20,
    run_institute_mentions,
    run_vector_fastlane,
    run_vector_healthspark,
)
from bbt_bizdev.config import SOURCES


RUNNERS = {
    "vector_ai20": (run_vector_ai20, "vector_ai20_health_companies"),
    "vector_healthspark": (run_vector_healthspark, "vector_healthspark_members"),
    "vector_fastlane": (run_vector_fastlane, "vector_fastlane_health_companies"),
    "amii_level_up_health": (run_amii_level_up_health, "amii_level_up_health_cohort"),
    "institute_mentions": (run_institute_mentions, "ai_institute_mentions_health"),
    "mila_startups": (run_mila_startups, "mila_health_startups"),
    "mila_health_partners": (run_mila_health_partners, "mila_health_ai_partners"),
}
SNAPSHOT_DATE = "2026-10-28"


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
