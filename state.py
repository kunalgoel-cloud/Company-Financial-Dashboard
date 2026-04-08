import streamlit as st
import pandas as pd

def init_state():
    """Initialise all session-state keys exactly once."""
    defaults = {
        "page": "Overview",
        # Raw uploaded DataFrames
        "df_invoice":   None,   # Invoice CSV  (P&L, Receivables, WC-DSO)
        "df_wms":       None,   # WMS/Inventory CSV  (Inventory, WC-DIO)
        "df_cust_bal":  None,   # Customer balance summary  (Receivables, WC-DSO)
        "df_po":        None,   # Purchase Order CSV  (Supplier, WC-DPO)
        "df_bill_hdr":  None,   # Bill header CSV  (Supplier, WC-DPO)
        "df_bill_lines":None,   # Bill lines CSV  (Supplier)
        # Item master: dict[sku -> {name, cogs, dead_weight, vol_weight, item_type, ...}]
        "item_master":  {},
        # Customer registry: dict[name -> {type, credit_days, is_marketplace, channel}]
        "customers":    {},
        # Derived/computed caches (cleared when source data changes)
        "_inv_cache":   None,
        "_pnl_cache":   None,
        "_wc_cache":    None,
        "_recv_cache":  None,
        "_supp_cache":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def clear_caches():
    for k in ["_inv_cache", "_pnl_cache", "_wc_cache", "_recv_cache", "_supp_cache"]:
        st.session_state[k] = None


def store_invoice(df: pd.DataFrame):
    st.session_state["df_invoice"] = df
    # Auto-populate customer registry from invoice
    _sync_customers(df)
    clear_caches()


def store_wms(df: pd.DataFrame):
    st.session_state["df_wms"] = df
    clear_caches()


def store_cust_bal(df: pd.DataFrame):
    st.session_state["df_cust_bal"] = df
    clear_caches()


def store_po(df: pd.DataFrame):
    st.session_state["df_po"] = df
    clear_caches()


def store_bill_hdr(df: pd.DataFrame):
    st.session_state["df_bill_hdr"] = df
    clear_caches()


def store_bill_lines(df: pd.DataFrame):
    st.session_state["df_bill_lines"] = df
    clear_caches()


def _sync_customers(df: pd.DataFrame):
    """Parse customer type from invoice data and populate registry."""
    if "Customer Name" not in df.columns:
        return
    registry = st.session_state["customers"]
    for name in df["Customer Name"].dropna().unique():
        if name in registry:
            continue
        name_up = str(name).upper()
        if "AMAZON" in name_up or "FLIPKART" in name_up or "MYNTRA" in name_up:
            ctype, channel = "B2C", "Marketplace"
        elif any(k in name_up for k in ["PVT", "PRIVATE", "LIMITED", "LTD", "LLP", "INDIA"]):
            ctype, channel = "B2B", "B2B"
        else:
            ctype, channel = "B2C", "D2C"
        registry[name] = {
            "type": ctype,
            "channel": channel,
            "credit_days": 30,
            "is_marketplace": channel == "Marketplace",
        }
    st.session_state["customers"] = registry
