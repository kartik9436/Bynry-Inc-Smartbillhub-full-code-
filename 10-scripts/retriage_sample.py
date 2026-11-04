import csv, random, sys, pathlib
CSV = pathlib.Path("12-governance/10-defect-log.csv")
OPEN = {"open", "reported", "fixed-in-part", "partially-fixed"}
EXCLUDE = {"DEF-611","DEF-628","DEF-634","DEF-635","DEF-637","DEF-638","DEF-640","DEF-648","DEF-649"}
rows = list(csv.DictReader(CSV.open(newline="", encoding="utf-8")))
pop = [r for r in rows
       if (r["severity"] or "").strip().lower() == "high"
       and (r["status"] or "").strip().lower() in OPEN]
print("open-high population (broad reading):", len(pop))
elig = sorted([r for r in pop if r["id"].strip() not in EXCLUDE], key=lambda r: int(r["id"].rsplit("-", 1)[1]))
print("eligible after excluding DEF-1930's nine:", len(elig))
rng = random.Random(19300827)          # SEED
sample = sorted(rng.sample(elig, 15), key=lambda r: int(r["id"].rsplit("-", 1)[1]))
for r in sample:
    print("|", r["id"], "|", r["module"], "|", r["status"], "|", r["category"], "|", r["title"][:150], "|")
