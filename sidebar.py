import streamlit as st
import pandas as pd
from state import (store_invoice, store_wms, store_cust_bal,
                   store_po, store_bill_hdr, store_bill_lines, clear_caches)

PAGES = ["Overview", "Inventory", "P&L", "Working Capital", "Receivables", "Supplier Performance"]
PAGE_ICONS = {"Overview": "◈", "Inventory": "📦", "P&L": "📊",
              "Working Capital": "⚙️", "Receivables": "💰", "Supplier Performance": "🚚"}


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

        # ── Data Upload Section ─────────────────────────────────────────────
        st.markdown('<p class="section-header">📁 Upload Data</p>', unsafe_allow_html=True)

        with st.expander("📄 Invoice CSV  *(P&L · Receivables · WC)*", expanded=False):
            f = st.file_uploader("Invoice CSV", type="csv", key="up_invoice", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    store_invoice(df)
                    st.success(f"✅ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        with st.expander("🏭 WMS / Inventory CSV  *(Inventory · WC)*", expanded=False):
            f = st.file_uploader("WMS CSV", type="csv", key="up_wms", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    store_wms(df)
                    st.success(f"✅ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        with st.expander("👥 Customer Balance Summary  *(Receivables · WC)*", expanded=False):
            f = st.file_uploader("Customer Balance CSV", type="csv", key="up_cbal", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    store_cust_bal(df)
                    st.success(f"✅ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        with st.expander("📦 Purchase Orders CSV  *(Supplier · WC)*", expanded=False):
            f = st.file_uploader("PO CSV", type="csv", key="up_po", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    store_po(df)
                    st.success(f"✅ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        with st.expander("🧾 Bill Header CSV  *(Supplier · WC)*", expanded=False):
            f = st.file_uploader("Bill Header CSV", type="csv", key="up_bhdr", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    store_bill_hdr(df)
                    st.success(f"✅ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        with st.expander("🔖 Bill Lines CSV  *(Supplier)*", expanded=False):
            f = st.file_uploader("Bill Lines CSV", type="csv", key="up_blines", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    store_bill_lines(df)
                    st.success(f"✅ {len(df):,} rows loaded")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")

        # ── Data status indicators ──────────────────────────────────────────
        st.markdown('<p class="section-header">Data Status</p>', unsafe_allow_html=True)
        checks = [
            ("Invoice CSV",        st.session_state["df_invoice"]),
            ("WMS CSV",            st.session_state["df_wms"]),
            ("Customer Balance",   st.session_state["df_cust_bal"]),
            ("PO CSV",             st.session_state["df_po"]),
            ("Bill Header",        st.session_state["df_bill_hdr"]),
            ("Bill Lines",         st.session_state["df_bill_lines"]),
        ]
        for label, df in checks:
            icon = "🟢" if df is not None else "⚪"
            rows = f" ({len(df):,} rows)" if df is not None else ""
            st.markdown(f"{icon} {label}{rows}")

        st.markdown("---")

        # ── Item Master quick edit ──────────────────────────────────────────
        with st.expander("⚙️ Item Master", expanded=False):
            _render_item_master()

        # ── Customer registry quick edit ────────────────────────────────────
        with st.expander("👥 Customer Registry", expanded=False):
            _render_customer_registry()

        st.markdown("---")
        if st.button("🗑️ Clear all data", use_container_width=True):
            for k in ["df_invoice", "df_wms", "df_cust_bal", "df_po", "df_bill_hdr", "df_bill_lines"]:
                st.session_state[k] = None
            clear_caches()
            st.rerun()


def _render_item_master():
    im = st.session_state["item_master"]
    # Add new item
    with st.form("im_add", clear_on_submit=True):
        st.markdown("**Add / update item**")
        sku  = st.text_input("SKU")
        name = st.text_input("Name")
        cogs = st.number_input("COGS (₹)", min_value=0.0, step=0.5)
        dw   = st.number_input("Dead weight (kg)", min_value=0.0, step=0.01, value=0.5)
        vw   = st.number_input("Vol. weight (kg)", min_value=0.0, step=0.01, value=0.5)
        if st.form_submit_button("Save"):
            if sku:
                im[sku] = {"name": name, "cogs": cogs, "dead_weight": dw, "vol_weight": vw}
                st.session_state["item_master"] = im
                clear_caches()
                st.success("Saved")
    if im:
        st.dataframe(pd.DataFrame(im).T[["name","cogs","dead_weight","vol_weight"]],
                     use_container_width=True, height=180)


def _render_customer_registry():
    reg = st.session_state["customers"]
    if not reg:
        st.info("Upload an Invoice CSV to auto-populate customers.")
        return
    df = pd.DataFrame(reg).T.reset_index().rename(columns={"index": "customer"})
    edited = st.data_editor(
        df[["customer","type","channel","credit_days","is_marketplace"]],
        hide_index=True, use_container_width=True,
        column_config={
            "type": st.column_config.SelectboxColumn("Type", options=["B2B","B2C"]),
            "credit_days": st.column_config.NumberColumn("Credit Days", min_value=0, max_value=365),
            "is_marketplace": st.column_config.CheckboxColumn("Own Pickup"),
        },
        key="cust_editor"
    )
    if st.button("💾 Save customers"):
        new_reg = {}
        for _, row in edited.iterrows():
            new_reg[row["customer"]] = {
                "type": row["type"], "channel": row["channel"],
                "credit_days": int(row["credit_days"]),
                "is_marketplace": bool(row["is_marketplace"]),
            }
        st.session_state["customers"] = new_reg
        clear_caches()
        st.success("Saved")
