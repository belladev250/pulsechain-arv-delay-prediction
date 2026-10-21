import warnings
import pandas as pd

warnings.filterwarnings("ignore")

DATA = "data/SCMS_Delivery_History_Dataset_20150929.csv"
OUT = "app/data/upcoming_shipments.csv"
COUNTRIES = ["Rwanda", "Uganda", "Tanzania", "Kenya", "Burundi", "South Sudan", "Ethiopia"]

FEATURES_NUM = ["planned_lead_time_days", "weight_kg", "freight_cost_usd", "Line Item Quantity",
                "Line Item Value", "vendor_past_late_rate", "country_past_late_rate",
                "vendor_shipment_count_so_far"]
FEATURES_CAT = ["Country", "Shipment Mode", "Vendor INCO Term", "Fulfill Via", "Product Group"]

df = pd.read_csv(DATA, encoding="latin-1")
df = df[df["Country"].isin(COUNTRIES)].copy()

for c in ["PO Sent to Vendor Date", "Scheduled Delivery Date", "Delivered to Client Date"]:
    df[c] = pd.to_datetime(df[c], errors="coerce")

df["delay_days"] = (df["Delivered to Client Date"] - df["Scheduled Delivery Date"]).dt.days
df["target_late"] = (df["delay_days"] > 0).astype(int)
df["weight_kg"] = pd.to_numeric(df["Weight (Kilograms)"], errors="coerce")
df["freight_cost_usd"] = pd.to_numeric(df["Freight Cost (USD)"], errors="coerce")
df["planned_lead_time_days"] = (df["Scheduled Delivery Date"] - df["PO Sent to Vendor Date"]).dt.days

df = df.sort_values("Scheduled Delivery Date").reset_index(drop=True)


def past_mean(group_col):
    prior = df.groupby(group_col)["target_late"].transform(lambda s: s.shift(1).expanding().mean())
    return prior.fillna(df["target_late"].expanding().mean().shift(1)).fillna(df["target_late"].mean())


df["vendor_past_late_rate"] = past_mean("Vendor")
df["country_past_late_rate"] = past_mean("Country")
df["vendor_shipment_count_so_far"] = df.groupby("Vendor").cumcount()

split = int(len(df) * 0.8)
test = df.iloc[split:].copy()

out = test[["ID", "Vendor", "Scheduled Delivery Date"] + FEATURES_NUM + FEATURES_CAT + ["target_late"]].copy()
out = out.rename(columns={"ID": "shipment_id", "Vendor": "vendor",
                          "Scheduled Delivery Date": "scheduled_date", "target_late": "actual_late"})
out["scheduled_date"] = out["scheduled_date"].dt.strftime("%Y-%m-%d")
out.to_csv(OUT, index=False)
print("rows:", len(out), "late share: %.3f" % out["actual_late"].mean())
print(out["Country"].value_counts().to_dict())
print(out.head(3).T)
