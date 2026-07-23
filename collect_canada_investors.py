from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path

from bbt_bizdev.adapters.canada_investors import (
    run_amplitude,
    run_bdc_health,
    run_facit,
    run_genesys,
    run_lumira,
)
from bbt_bizdev.config import SOURCES


RUNNERS = {
    "lumira_portfolio": (run_lumira, "lumira_ventures_portfolio"),
    "genesys_portfolio": (run_genesys, "genesys_capital_active_portfolio"),
    "amplitude_portfolio": (run_amplitude, "amplitude_ventures_portfolio"),
    "bdc_health_portfolio": (run_bdc_health, "bdc_current_health_life_sciences_portfolio"),
    "facit_portfolio": (run_facit, "facit_oncology_investment_portfolio"),
}
SNAPSHOT_DATE = "2026-07-23"


def normalize_company(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\([^)]*(?:acquired|formerly)[^)]*\)", " ", value)
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|limited|ltd)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def write_overlap_report() -> None:
    investor_files = {f"{filename}_{SNAPSHOT_DATE}.json" for _, filename in RUNNERS.values()}
    investor, ecosystem = {}, {}
    for path in Path("data").glob(f"*_{SNAPSHOT_DATE}.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        target = investor if path.name in investor_files else ecosystem
        for record in payload.get("records", []):
            company = record.get("company") or ""
            key = normalize_company(company)
            if not key:
                continue
            item = target.setdefault(key, {"names": set(), "sources": set()})
            item["names"].add(company)
            source_meta = payload.get("source", {})
            source_label = source_meta.get("name") if isinstance(source_meta, dict) else str(source_meta)
            item["sources"].add(record.get("source_name") or source_label or path.stem)
    rows = []
    for key in sorted(set(investor) & set(ecosystem)):
        names = sorted(investor[key]["names"] | ecosystem[key]["names"])
        rows.append({
            "normalized_company": key,
            "canonical_company": names[0],
            "known_name_variants": " | ".join(names),
            "investor_sources": " | ".join(sorted(investor[key]["sources"])),
            "ecosystem_sources": " | ".join(sorted(ecosystem[key]["sources"])),
        })
    path = Path("outputs") / f"canada_tier_a_investor_ecosystem_overlap_{SNAPSHOT_DATE}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [
            "normalized_company", "canonical_company", "known_name_variants",
            "investor_sources", "ecosystem_sources",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"overlap: {len(rows)} normalized companies appear in both investor and ecosystem snapshots; CSV={path}")


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
    write_overlap_report()


if __name__ == "__main__":
    main()
