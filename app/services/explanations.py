"""Plain-language wording for model explanations (pure functions, no model state)."""
import pandas as pd


def clean_name(name: str) -> str:
    for prefix in ("num__", "cat__"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.replace("_", " ")


CAT_BASES = ["Country", "Shipment Mode", "Vendor INCO Term", "Fulfill Via", "Product Group"]


def plain_reason(raw: str, row: pd.Series, direction: str) -> str:
    raw = raw.replace("num__", "").replace("cat__", "")
    effect = "raises" if direction == "raises risk" else "lowers"

    def num(key):
        value = row.get(key)
        return None if value is None or pd.isna(value) else float(value)

    if raw == "vendor_past_late_rate":
        return f"This vendor was late on {num(raw) * 100:.0f}% of its past shipments, which {effect} the risk compared with an average shipment."
    if raw == "country_past_late_rate":
        return f"Past shipments to this country were late {num(raw) * 100:.0f}% of the time, which {effect} the risk compared with an average shipment."
    if raw == "vendor_recent_late_rate":
        return f"This vendor was late on {num(raw) * 100:.0f}% of its most recent shipments, which {effect} the risk compared with an average shipment."
    if raw == "country_recent_late_rate":
        return f"Recent shipments to this country were late {num(raw) * 100:.0f}% of the time, which {effect} the risk compared with an average shipment."
    if raw == "global_recent_late_rate":
        return f"Across all vendors, {num(raw) * 100:.0f}% of recent shipments were late, which {effect} the risk compared with an average shipment."
    if raw == "vendor_country_late_rate":
        return f"This vendor was late on {num(raw) * 100:.0f}% of past shipments to this country, which {effect} the risk compared with an average shipment."
    if raw == "vendor_country_count":
        return f"The vendor has {num(raw):,.0f} earlier shipments to this country, which {effect} the risk compared with an average shipment."
    if raw == "has_lead_time":
        return ("A planned lead time was provided, which " + effect + " the risk." if num(raw)
                else "No planned lead time was provided, which " + effect + " the risk.")
    if raw == "value_per_unit":
        value = num(raw)
        return ("Unit value is unknown, which " + effect + " the risk." if value is None
                else f"A unit value of ${value:,.2f} {effect} the risk compared with an average shipment.")
    if raw == "freight_per_kg":
        value = num(raw)
        return ("Freight cost per kg is unknown, which " + effect + " the risk." if value is None
                else f"A freight cost of ${value:,.2f} per kg {effect} the risk compared with an average shipment.")
    if raw == "scheduled_month":
        return f"The delivery month ({num(raw):.0f}) {effect} the risk compared with an average shipment."
    if raw == "vendor_shipment_count_so_far":
        return f"The vendor has {num(raw):,.0f} earlier shipments on record, which {effect} the risk compared with an average shipment."
    if raw == "planned_lead_time_days":
        value = num(raw)
        return ("No planned lead time was provided, which " + effect + " the risk." if value is None
                else f"A planned lead time of {value:.0f} days {effect} the risk compared with an average shipment.")
    if raw == "weight_kg":
        value = num(raw)
        return ("Weight is missing for this shipment, which " + effect + " the risk." if value is None
                else f"A shipment weight of {value:,.0f} kg {effect} the risk compared with an average shipment.")
    if raw == "freight_cost_usd":
        value = num(raw)
        return ("Freight cost is missing for this shipment, which " + effect + " the risk." if value is None
                else f"A freight cost of ${value:,.0f} {effect} the risk compared with an average shipment.")
    if raw == "Line Item Quantity":
        return f"An order size of {num(raw):,.0f} units {effect} the risk compared with an average shipment."
    if raw == "Line Item Value":
        return f"An order value of ${num(raw):,.0f} {effect} the risk compared with an average shipment."
    for base in CAT_BASES:
        if raw.startswith(base + "_"):
            return f"{base}: {raw[len(base) + 1:]} {effect} the risk compared with an average shipment."
    return f"{clean_name(raw)} {effect} the risk compared with an average shipment."
