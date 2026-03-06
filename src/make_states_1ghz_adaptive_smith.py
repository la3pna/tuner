from pathlib import Path
import pandas as pd

xmax = 14750
ymax = 3030

Ny = 20
p_y = 2.8

y_levels = []
for i in range(Ny):
    u = i / (Ny - 1)
    y = round(ymax * (1 - (1 - u) ** p_y))
    y_levels.append(int(y))
y_levels = sorted(set([0, *y_levels, ymax]))

rows = []
meta = []

for y in y_levels:
    yn = y / ymax if ymax else 0.0
    n_x = max(4, round(4 + 34 * (yn ** 1.8)))
    x_vals = sorted(set(round(i * xmax / (n_x - 1)) for i in range(n_x)))
    for x in x_vals:
        rows.append({"x_steps": int(x), "y_steps": int(y)})
    meta.append({"y_steps": int(y), "n_x": len(x_vals)})

df = pd.DataFrame(rows)
meta_df = pd.DataFrame(meta)

out_csv = Path("states_1ghz_adaptive_smith.csv")
out_meta = Path("states_1ghz_adaptive_smith_y_summary.csv")

df.to_csv(out_csv, index=False)
meta_df.to_csv(out_meta, index=False)

print("Wrote", out_csv, "rows:", len(df))
print("Wrote", out_meta)
print(meta_df.to_string(index=False))
