"""
state.py — Session state management
------------------------------------
On startup, loads all persisted data from Neon PostgreSQL into session state
so every tab can access DataFrames directly without hitting the DB each time.
Writes go to both session state (instant) and the DB (persistent).
"""

import streamlit as st
import pandas as pd
from database import (
    init_database,
    load_dataframe, save_dataframe, delete_dataframe,
    load_item_master, save_item_master,
    load_customer_registry, save_customer_registry,
)


def init_state():
    """
    Called once per session in app.py.
    1. Ensures DB tables exist.
    2. Loads all persisted data from DB into session state on first load.
    3. Sets safe defaults for everything else.
    """
    # Only run the full DB load once per browser session
    if st.session_state.get("_db_loaded"):
        return

    # Bootstrap database tables
    init_database()

    # Set navigation default
    if "page" not in st.session_state:
        st.session_state["page"] = "Overview"

    # Load raw CSV datasets from DB into session state
    dataset_keys = ["invoice", "wms", "cust_bal", "po", "bill_hdr", "bill_lines"]
    session_keys = ["df_invoice", "df_wms", "df_cust_bal", "df_po", "df_bill_hdr", "df_bill_lines"]

    for db_key, sess_key in zip(dataset_keys, session_keys):
        if sess_key not in st.session_state:
            st.session_state[sess_key] = load_dataframe(db_key)

    # Load item master and customer registry
    if "item_master" not in st.session_state:
        st.session_state["item_master"] = load_item_master()

    if "customers" not in st.session_state:
        st.session_state["customers"] = load_customer_registry()

    # Derived caches (never persisted — recomputed on demand)
    for cache_key in ["_inv_cache", "_pnl_cache", "_wc_cache", "_recv_cache", "_supp_cache"]:
        if cache_key not in st.session_state:
            st.session_state[cache_key] = None

    # Mark that we've completed the DB load for this browser session
    st.session_state["_db_loaded"] = True


def clear_caches():
    """Clear all computed caches so tabs recompute from fresh data."""
    for k in ["_inv_cache", "_pnl_cache", "_wc_cache", "_recv_cache", "_supp_cache"]:
        st.session_state[k] = None


# ── Data store functions (session state + DB) ──────────────────────────────
# Each function saves to both places: session state for instant UI response,
# and the DB for persistence across reloads.

def store_invoice(df: pd.DataFrame):
    st.session_state["df_invoice"] = df
    save_dataframe("invoice", df)
    _sync_customers(df)
    clear_caches()


def store_wms(df: pd.DataFrame):
    st.session_state["df_wms"] = df
    save_dataframe("wms", df)
    clear_caches()


def store_cust_bal(df: pd.DataFrame):
    st.session_state["df_cust_bal"] = df
    save_dataframe("cust_bal", df)
    clear_caches()


def store_po(df: pd.DataFrame):
    st.session_state["df_po"] = df
    save_dataframe("po", df)
    clear_caches()


def store_bill_hdr(df: pd.DataFrame):
    st.session_state["df_bill_hdr"] = df
    save_dataframe("bill_hdr", df)
    clear_caches()


def store_bill_lines(df: pd.DataFrame):
    st.session_state["df_bill_lines"] = df
    save_dataframe("bill_lines", df)
    clear_caches()


def delete_dataset(data_type: str, session_key: str):
    """Delete a single dataset from both session state and DB."""
    st.session_state[session_key] = None
    delete_dataframe(data_type)
    clear_caches()


def update_item_master(im: dict):
    """Save item master to session state and DB."""
    st.session_state["item_master"] = im
    save_item_master(im)
    clear_caches()


def update_customer_registry(registry: dict):
    """Save customer registry to session state and DB."""
    st.session_state["customers"] = registry
    save_customer_registry(registry)
    clear_caches()


def _sync_customers(df: pd.DataFrame):
    """
    Auto-classify new customers from an invoice CSV.
    Only adds customers that don't already exist in the registry.
    """
    if "Customer Name" not in df.columns:
        return

    registry = st.session_state.get("customers", {})
    new_entries = {}

    for name in df["Customer Name"].dropna().unique():
        if name in registry:
            continue
        name_up = str(name).upper()
        if any(mkt in name_up for mkt in ["AMAZON", "FLIPKART", "MYNTRA", "MEESHO", "NYKAA"]):
            ctype, channel = "B2C", "Marketplace"
        elif any(k in name_up for k in ["PVT", "PRIVATE", "LIMITED", "LTD", "LLP"]):
            ctype, channel = "B2B", "B2B"
        else:
            ctype, channel = "B2C", "D2C"

        new_entries[name] = {
            "type": ctype,
            "channel": channel,
            "credit_days": 30,
            "is_marketplace": channel == "Marketplace",
        }

    if new_entries:
        registry.update(new_entries)
        st.session_state["customers"] = registry
        save_customer_registry(new_entries)  # Only save the new ones
