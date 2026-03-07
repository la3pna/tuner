
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def make_y_levels(ymax: int, n_y: int, p_y: float):
    vals = []
    for i in range(n_y):
        u = i/(n_y-1) if n_y>1 else 0.0
        y = round(ymax*(1-(1-u)**p_y))
        vals.append(int(y))
    return sorted(set([0,*vals,ymax]))

def estimate_full_x_levels(freq_mhz, xmax_used, step_um, vf, phase_step_deg,
                           min_x_levels, max_x_levels):

    c = 299792458.0
    freq_hz = freq_mhz * 1e6

    l_m = xmax_used * step_um * 1e-6
    lambda_g = c*vf/freq_hz

    phase_span_deg = 720*l_m/lambda_g
    n = int(round(phase_span_deg/phase_step_deg))+1

    return int(clamp(n, min_x_levels, max_x_levels))

def make_x_levels(xmax_used, n_x):
    vals=[round(i*xmax_used/(n_x-1)) for i in range(n_x)]
    vals=sorted(set(int(v) for v in vals))
    if vals[-1]!=xmax_used:
        vals.append(xmax_used)
    return vals

def generate_states(freq_mhz,
                    xmax_used=14600,
                    ymax=3030,
                    step_um=25.4,
                    vf=1.0,
                    n_y=20,
                    p_y=2.8,
                    phase_step_deg=45,
                    min_x_levels=4,
                    max_x_levels=24,
                    x_weight_exp=1.8):

    y_levels = make_y_levels(ymax,n_y,p_y)

    n_x_full = estimate_full_x_levels(freq_mhz,xmax_used,step_um,vf,
                                      phase_step_deg,min_x_levels,max_x_levels)

    rows=[]
    summary=[]

    for y in y_levels:

        yn = y/ymax if ymax else 0.0

        n_x_here=max(
            min_x_levels,
            int(round(min_x_levels+(n_x_full-min_x_levels)*(yn**x_weight_exp)))
        )

        x_levels = make_x_levels(xmax_used,n_x_here)

        for x in x_levels:
            rows.append({"x_steps":int(x),"y_steps":int(y)})

        summary.append({
            "y_steps":int(y),
            "n_x":len(x_levels),
            "x_min":min(x_levels),
            "x_max":max(x_levels)
        })

    return pd.DataFrame(rows), pd.DataFrame(summary)

def main():

    ap = argparse.ArgumentParser(
        description="Generate adaptive tuner states (frequency in MHz)."
    )

    ap.add_argument("--freq-mhz",type=int,required=True)
    ap.add_argument("--xmax-used",type=int,default=14600)
    ap.add_argument("--ymax",type=int,default=3030)
    ap.add_argument("--out",default="")

    args=ap.parse_args()

    states,summary = generate_states(
        freq_mhz=args.freq_mhz,
        xmax_used=args.xmax_used,
        ymax=args.ymax
    )

    if args.out:
        out=Path(args.out)
    else:
        out=Path(f"states_{args.freq_mhz}MHz_adaptive.csv")

    states.to_csv(out,index=False)
    summary.to_csv(out.with_name(out.stem+"_summary.csv"),index=False)

    print("States written:",out)
    print("Rows:",len(states))
    print(summary.to_string(index=False))

if __name__=="__main__":
    main()
