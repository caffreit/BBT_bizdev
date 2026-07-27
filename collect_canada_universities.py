from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from bbt_bizdev.adapters.canada_universities import (
    run_axelys_supported_startups,
    run_mcgill_health_spinouts,
    run_mcmaster_health_startups,
    run_velocity_health_companies,
)
from bbt_bizdev.config import SOURCES


RUNNERS = {
    "mcgill_health_spinouts": (run_mcgill_health_spinouts, "mcgill_health_sector_spinouts"),
    "mcmaster_health_startups": (run_mcmaster_health_startups, "mcmaster_health_startups"),
    "axelys_supported_startups": (run_axelys_supported_startups, "axelys_supported_startups"),
    "velocity_health_companies": (run_velocity_health_companies, "velocity_health_companies"),
}


def main() -> None:
    snapshot_date = date.today().isoformat()
    Path("data").mkdir(exist_ok=True)
    Path("outputs").mkdir(exist_ok=True)
    sources = {source.adapter: source for source in SOURCES if source.adapter in RUNNERS}
    for adapter, (runner, filename) in RUNNERS.items():
        source = sources[adapter]
        hits, triggers, result = runner(source)
        payload = {
            "snapshot_date": snapshot_date,
            "source": asdict(source),
            "result": result,
            "records": [asdict(hit) for hit in hits],
        }
        json_path = Path("data") / f"{filename}_{snapshot_date}.json"
        csv_path = Path("outputs") / f"{filename}_{snapshot_date}.csv"
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows = payload["records"]
        if rows:
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        print(
            f"{adapter}: {result}; JSON={json_path}; CSV={csv_path}; "
            f"triggers={len(triggers)}"
        )


if __name__ == "__main__":
    main()
