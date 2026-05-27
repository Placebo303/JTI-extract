from TimeTagger import FileReader
from collections import Counter

path = r"D:\Data\Raw Data\Time Tags\Time Tags\Type II FPC 135° Single Filter_2026-04-13_171823.1.ttbin"
reader = FileReader(path)
try:
    cfg = dict(reader.getConfiguration())
    for m in cfg.get("measurements", []):
        name = m.get("name", "")
        params = m.get("params", {})
        print(f"  measurement: {name}, params={params}")
except Exception as e:
    print(f"Config error: {e}")

ch_counts = Counter()
total = 0
while reader.hasData() and total < 500000:
    data = reader.getData(500000)
    ch = data.getChannels()
    total += len(ch)
    for c in ch:
        ch_counts[int(c)] += 1

print(f"Total events sampled: {total}")
for ch_id in sorted(ch_counts):
    print(f"  ch {ch_id}: {ch_counts[ch_id]}")
