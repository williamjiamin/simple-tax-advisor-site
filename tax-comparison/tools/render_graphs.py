import json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT/"data/tax_schedules.json").read_text())
out = ROOT/"assets"; out.mkdir(exist_ok=True)
xs = list(range(0, 200001, 2000))
fig, ax = plt.subplots(figsize=(11, 6))
for j in data["jurisdictions"]:
    ys=[]
    for x in xs:
        total=0; lower=0
        for b in j["brackets"]:
            upper=b["up_to"]
            taxable=max(0, x-lower) if upper is None else max(0,min(x,upper)-lower)
            total += taxable*b["rate"]
            if upper is None or x<=upper: break
            lower=upper
        ys.append(total)
    ax.plot(xs, ys, linewidth=2.4, label=j["label"]["en"])
ax.set(title="Illustrative progressive income-tax schedules", xlabel="Normalized annual income units", ylabel="Modeled tax units")
ax.grid(True, alpha=.25); ax.legend(); fig.tight_layout()
fig.savefig(out/"tax-brackets.png", dpi=300)
fig.savefig(out/"tax-brackets.svg", format="svg")
plt.close(fig)
