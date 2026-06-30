"""CLI：快速將求職申請加入 Redis tracker。

用法：
  python3 scripts/add_job.py --company "TransUnion" --role "Data Analyst" --link "https://..."
  python3 scripts/add_job.py --company "HKU" --role "Programme Officer"   # 無 link 都得
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import load_jobs, save_jobs


def main():
    parser = argparse.ArgumentParser(description="新增求職申請到 tracker")
    parser.add_argument("--company", required=True, help="公司名稱")
    parser.add_argument("--role",    required=True, help="職位名稱")
    parser.add_argument("--link",    default="",    help="Job link（可選）")
    parser.add_argument("--jd",      default="",    help="JD 內容（可選）")
    args = parser.parse_args()

    jobs   = load_jobs()
    new_id = (max(j["id"] for j in jobs) + 1) if jobs else 1
    job = {
        "id":           new_id,
        "company":      args.company,
        "role":         args.role,
        "jd":           args.jd,
        "link":         args.link,
        "applied_date": str(date.today()),
        "status":       "Applied",
    }
    jobs.append(job)
    save_jobs(jobs)
    print(f"✅ 已新增：{args.company} — {args.role}（id={new_id}）")


if __name__ == "__main__":
    main()
