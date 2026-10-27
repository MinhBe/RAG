import httpx

BASE = "https://datasets-server.huggingface.co"
DS = "th1nhng0/vietnamese-legal-documents"

for so in ["45/2019/QH14", "10/2012/QH13", "145/2020/NĐ-CP"]:
    where = '"so_ky_hieu" = ' + "'" + so + "'"
    r = httpx.get(
        BASE + "/filter",
        params={"dataset": DS, "config": "metadata", "split": "data", "where": where, "limit": 20},
        timeout=120,
    )
    print("==", so, r.status_code)
    if r.status_code == 200:
        for row in r.json().get("rows", []):
            d = row["row"]
            print("  id=", d.get("id"), "| loai=", d.get("loai_van_ban"), "|", (d.get("title") or "")[:80])
