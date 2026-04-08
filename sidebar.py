"""
sidebar.py — Navigation, file uploads, item master, customer registry
----------------------------------------------------------------------
All uploads now persist to Neon PostgreSQL via state.py store functions.
The sidebar also shows DB-sourced upload timestamps and row counts.
"""

import streamlit as st
import pandas as pd
from state import (
    store_invoice, store_wms, store_cust_bal,
    store_po, store_bill_hdr, store_bill_lines,
    delete_dataset, update_item_master, update_customer_registry,
    clear_caches,
)
from database import get_data_status, clear_all_data, delete_item

PAGES = ["Overview", "Inventory", "P&L", "Working Capital", "Receivables", "Supplier Performance"]
PAGE_ICONS = {
    "Overview": "◈", "Inventory": "📦", "P&L": "📊",
    "Working Capital": "⚙️", "Receivables": "💰", "Supplier Performance": "🚚",
}

# Maps display label → (db_key, session_key)
DATASETS = {
    "📄 Invoice CSV":           ("invoice",    "df_invoice"),
    "🏭 WMS / Inventory CSV":   ("wms",        "df_wms"),
    "👥 Customer Balance CSV":  ("cust_bal",   "df_cust_bal"),
    "📦 Purchase Orders CSV":   ("po",         "df_po"),
    "🧾 Bill Header CSV":       ("bill_hdr",   "df_bill_hdr"),
    "🔖 Bill Lines CSV":        ("bill_lines", "df_bill_lines"),
}

DATASET_HINTS = {
    "📄 Invoice CSV":           "Powers: P&L · Receivables · Working Capital",
    "🏭 WMS / Inventory CSV":   "Powers: Inventory · Working Capital (DIO)",
    "👥 Customer Balance CSV":  "Powers: Receivables reconciliation · WC (DSO)",
    "📦 Purchase Orders CSV":   "Powers: Supplier Performance · WC (DPO)",
    "🧾 Bill Header CSV":       "Powers: Supplier Performance",
    "🔖 Bill Lines CSV":        "Powers: Supplier Performance (lead time)",
}


def render_sidebar():
    with st.sidebar:
        st.markdown("## 📊 Finance Command Centre")
        st.markdown("---")

        # ── Navigation ─────────────────────────────────────────────────────
        st.markdown('<p class="section-header">Navigation</p>', unsafe_allow_html=True)
        for p in PAGES:
            active = st.session_state.get("page") == p
            label = f"{'▶ ' if active else ''}{PAGE_ICONS[p]}  {p}"
            if st.button(label, key=f"nav_{p}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state["page"] = p
                st.rerun()

        st.markdown("---")

        # ── Upload Section ─────────────────────────────────────────────────
        st.markdown('<p class="section-header">📁 Upload Data</p>', unsafe_allow_html=True)

        # Pull current DB status once (cached for this render)
        db_status = get_data_status()

        for label, (db_key, sess_key) in DATASETS.items():
            status = db_status.get(db_key)
            # Show green dot + row count if data already exists in DB
            badge = ""
            if status:
                ts = status["uploaded_at"].strftime("%d %b %H:%M") if status["uploaded_at"] else ""
                badge = f" 🟢 {status['row_count']:,} rows · {ts}"

            with st.expander(f"{label}{badge}", expanded=False):
                st.caption(DATASET_HINTS[label])

                f = st.file_uploader(
                    label, type="csv",
                    key=f"up_{db_key}",
                    label_visibility="collapsed"
                )
                if f:
                    try:
                        df = pd.read_csv(f)
                        # Route to the right store function
                        {
                            "invoice":    store_invoice,
                            "wms":        store_wms,
                            "cust_bal":   store_cust_bal,
                            "po":         store_po,
                            "bill_hdr":   store_bill_hdr,
                            "bill_lines": store_bill_lines,
                        }[db_key](df)
                        st.success(f"✅ {len(df):,} rows saved to database")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

                # Delete button if data exists
                if status:
                    if st.button(f"🗑️ Remove from DB", key=f"del_{db_key}",
                                 use_container_width=True):
                        delete_dataset(db_key, sess_key)
                        st.rerun()

        st.markdown("---")

        # ── Data Status Summary ────────────────────────────────────────────
        st.markdown('<p class="section-header">☁️ Database Status</p>', unsafe_allow_html=True)
        if db_status:
            for db_key, info in db_status.items():
                label = next((l for l, (k, _) in DATASETS.items() if k == db_key), db_key)
                ts = info["uploaded_at"].strftime("%d %b %H:%M") if info["uploaded_at"] else "—"
                st.markdown(f"🟢 **{label.split(' ', 1)[-1].strip()}** — {info['row_count']:,} rows · _{ts}_")
        else:
            st.markdown("⚪ No data in database yet")

        st.markdown("---")

        # ── Item Master ────────────────────────────────────────────────────
        with st.expander("⚙️ Item Master", expanded=False):
            _render_item_master()

        # ── Customer Registry ──────────────────────────────────────────────
        with st.expander("👥 Customer Registry", expanded=False):
            _render_customer_registry()

        st.markdown("---")

        # ── Danger Zone ────────────────────────────────────────────────────
        with st.expander("⚠️ Danger Zone", expanded=False):
            st.warning("These actions delete data from the database permanently.")
            if st.button("🗑️ Clear ALL uploaded data", use_container_width=True, type="primary"):
                clear_all_data()
                for k in ["df_invoice", "df_wms", "df_cust_bal", "df_po", "df_bill_hdr", "df_bill_lines"]:
                    st.session_state[k] = None
                clear_caches()
                st.success("All uploaded data cleared.")
                st.rerun()


# ── Item Master panel ──────────────────────────────────────────────────────

def _render_item_master():
    im = st.session_state.get("item_master", {})

    with st.form("im_add_form", clear_on_submit=True):
        st.markdown("**Add / update item**")
        c1, c2 = st.columns(2)
        sku  = c1.text_input("SKU")
        name = c2.text_input("Product Name")
        c3, c4, c5 = st.columns(3)
        cogs = c3.number_input("COGS (₹)", min_value=0.0, step=0.5, format="%.2f")
        dw   = c4.number_input("Dead wt (kg)", min_value=0.0, step=0.01, value=0.5, format="%.3f")
        vw   = c5.number_input("Vol wt (kg)",  min_value=0.0, step=0.01, value=0.5, format="%.3f")

        if st.form_submit_button("💾 Save to Database", use_container_width=True):
            if sku:
                im[sku] = {"name": name, "cogs": cogs, "dead_weight": dw, "vol_weight": vw}
                update_item_master(im)
                st.success(f"✅ Saved {sku}")
            else:
                st.error("SKU is required")

    if im:
        df = pd.DataFrame(im).T.reset_index().rename(columns={"index": "sku"})
        df = df[["sku", "name", "cogs", "dead_weight", "vol_weight"]]
        df.columns = ["SKU", "Name", "COGS (₹)", "Dead Wt", "Vol Wt"]

        st.dataframe(df, use_container_width=True, hide_index=True, height=200,
                     column_config={
                         "COGS (₹)": st.column_config.NumberColumn(format="₹%.2f"),
                     })

        # Delete a SKU
        sku_to_del = st.selectbox("Delete SKU", ["— select —"] + list(im.keys()), key="del_sku_select")
        if sku_to_del != "— select —":
            if st.button(f"🗑️ Delete {sku_to_del}", key="del_sku_btn"):
                im.pop(sku_to_del, None)
                delete_item(sku_to_del)
                st.session_state["item_master"] = im
                st.success(f"Deleted {sku_to_del}")
                st.rerun()
    else:
        st.info("No items yet. Add your first SKU above.")


# ── Customer Registry panel ────────────────────────────────────────────────

def _render_customer_registry():
    reg = st.session_state.get("customers", {})

    if not reg:
        st.info("Upload an Invoice CSV — customers are auto-detected and saved here.")
        return

    df = pd.DataFrame(reg).T.reset_index().rename(columns={"index": "customer"})
    cols_needed = ["customer", "type", "channel", "credit_days", "is_marketplace"]
    for c in cols_needed:
        if c not in df.columns:
            df[c] = "" if c in ["type", "channel"] else (30 if c == "credit_days" else False)

    edited = st.data_editor(
        df[cols_needed],
        hide_index=True,
        use_container_width=True,
        height=250,
        column_config={
            "customer":      st.column_config.TextColumn("Customer", disabled=True),
            "type":          st.column_config.SelectboxColumn("Type", options=["B2B", "B2C"]),
            "channel":       st.column_config.TextColumn("Channel"),
            "credit_days":   st.column_config.NumberColumn("Credit Days", min_value=0, max_value=365),
            "is_marketplace":st.column_config.CheckboxColumn("Own Pickup"),
        },
        key="cust_registry_editor"
    )

    if st.button("💾 Save to Database", key="save_cust_btn", use_container_width=True):
        new_reg = {}
        for _, row in edited.iterrows():
            new_reg[row["customer"]] = {
                "type":           row["type"],
                "channel":        row["channel"],
                "credit_days":    int(row["credit_days"]),
                "is_marketplace": bool(row["is_marketplace"]),
            }
        update_customer_registry(new_reg)
        st.success(f"✅ Saved {len(new_reg)} customers to database")
