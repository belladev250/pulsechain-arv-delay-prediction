"""Build the SHAP summary figure for the report from the saved model and the SCMS data.

Run from the project folder (virtual environment active):
    python3 scripts/make_shap_figure.py
It rebuilds the test set exactly as in the training notebook (same cleaning, 60-day lag history,
chronological 80/20 split), explains the saved model on the 464 test shipments and writes:
    figures/08_shap_importance.png   (mean absolute SHAP value per feature, for the report)
    figures/08_shap_beeswarm.png     (direction and spread of each feature's effect)
"""
import json
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "SCMS_Delivery_History_Dataset_20150929.csv"
MODELS = ROOT / "app" / "models"
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

COUNTRIES = ["Rwanda", "Uganda", "Tanzania", "Kenya", "Burundi", "South Sudan", "Ethiopia"]
cfg = json.load(open(MODELS / "feature_config.json"))
FEATURES = cfg["numeric"] + cfg["categorical"]
LAG = cfg["lag_days"]
W = cfg["windows"]

df = pd.read_csv(DATA, encoding="latin-1")
df = df[df["Country"].isin(COUNTRIES)].copy()
for c in ["PO Sent to Vendor Date", "Scheduled Delivery Date", "Delivered to Client Date"]:
    df[c] = pd.to_datetime(df[c], errors="coerce")
df["delay_days"] = (df["Delivered to Client Date"] - df["Scheduled Delivery Date"]).dt.days
df["target_late"] = (df["delay_days"] > 0).astype(int)
df = df.sort_values("Scheduled Delivery Date").reset_index(drop=True)


def add_history(frame, lag_days, vendor_window, country_window, global_window):
    d = frame.copy()
    sched = d["Scheduled Delivery Date"].values.astype("datetime64[D]")
    deliv = d["Delivered to Client Date"].values.astype("datetime64[D]")
    y = d["target_late"].values.astype(float)
    cutoff = sched - np.timedelta64(lag_days, "D")

    def groups(keys):
        out = {}
        for k in np.unique(keys):
            idx = np.where(keys == k)[0]
            idx = idx[np.argsort(deliv[idx], kind="stable")]
            out[k] = (deliv[idx], y[idx])
        return out

    vendor = d["Vendor"].values
    country = d["Country"].values
    gv, gc = groups(vendor), groups(country)
    order = np.argsort(deliv, kind="stable")
    deliv_all, y_all = deliv[order], y[order]
    names = ["vendor_past_late_rate", "vendor_recent_late_rate", "country_past_late_rate",
             "country_recent_late_rate", "global_recent_late_rate"]
    cols = {k: np.full(len(d), np.nan) for k in names}
    base = y.mean()
    for i in range(len(d)):
        k = np.searchsorted(deliv_all, cutoff[i], side="right")
        g_rate = y_all[:k].mean() if k > 0 else base
        cols["global_recent_late_rate"][i] = y_all[max(0, k - global_window):k].mean() if k > 0 else base
        dv, yv = gv[vendor[i]]
        kv = np.searchsorted(dv, cutoff[i], side="right")
        cols["vendor_past_late_rate"][i] = yv[:kv].mean() if kv > 0 else g_rate
        cols["vendor_recent_late_rate"][i] = yv[max(0, kv - vendor_window):kv].mean() if kv > 0 else g_rate
        dc, yc = gc[country[i]]
        kc = np.searchsorted(dc, cutoff[i], side="right")
        cols["country_past_late_rate"][i] = yc[:kc].mean() if kc > 0 else g_rate
        cols["country_recent_late_rate"][i] = yc[max(0, kc - country_window):kc].mean() if kc > 0 else g_rate
    for k, v in cols.items():
        d[k] = v
    return d


data = add_history(df, LAG, W["vendor"], W["country"], W["global"])
split = int(len(data) * 0.8)
test = data.iloc[split:].reset_index(drop=True)
print("Test shipments:", len(test), "late:", int(test["target_late"].sum()))

model = joblib.load(MODELS / "model_pipeline.joblib")
pre, clf = model.named_steps["pre"], model.named_steps["clf"]
X = pre.transform(test[FEATURES])
raw_names = [n.replace("num__", "").replace("cat__", "") for n in pre.get_feature_names_out()]
nice = {"vendor_recent_late_rate": "Vendor recent late rate (last 20 shipments)",
        "vendor_past_late_rate": "Vendor past late rate (all earlier shipments)",
        "country_recent_late_rate": "Country recent late rate (last 50 shipments)",
        "global_recent_late_rate": "Overall recent late rate (last 100 shipments)"}
names = [nice.get(n, n) for n in raw_names]

explainer = shap.TreeExplainer(clf)
sv = explainer.shap_values(np.asarray(X))
sv = sv[1] if isinstance(sv, list) else sv
mean_abs = np.abs(sv).mean(axis=0)
order = np.argsort(mean_abs)
print("\nMean absolute SHAP value (log-odds scale):")
for i in order[::-1]:
    print("  %-50s %.3f" % (names[i], mean_abs[i]))

plt.rcParams.update({"font.family": "serif", "font.size": 10})
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.barh([names[i] for i in order], mean_abs[order], color="#1f4e79")
ax.set_xlabel("Mean absolute SHAP value (effect on predicted log-odds of delay)")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig(OUT / "08_shap_importance.png", dpi=200, bbox_inches="tight")
plt.close()

shap.summary_plot(sv, X, feature_names=names, show=False)
plt.gcf().set_size_inches(7.5, 3.6)
plt.tight_layout()
plt.savefig(OUT / "08_shap_beeswarm.png", dpi=200, bbox_inches="tight")
print("\nSaved figures/08_shap_importance.png and figures/08_shap_beeswarm.png")
