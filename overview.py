import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date


def render():
    st.title("📊 Finance Command Centre")
    st.caption(f"Last refreshed: {date.today().strftime('%d %b %Y')}")

    inv_df   = st.session_state["df_invoice"]
    wms_df   = st.session_state["df_wms"]
    cbal_df  = st.session_state["df_cust_bal"]
    im       = st.session_state["item_master"]
    customers = st.session_state["customers"]

    any_data = any(x is not None for x in [inv_df, wms_df, cbal_df])

    if not any_data:
        _show_onboarding()
        return

    # ── Row 1: Core financial KPIs ─────────────────────────────────────────
    st.markdown("### Key Performance Indicators")
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    # Revenue
    revenue = 0
    if inv_df is not None and "Item Total" in inv_df.columns:
        revenue = pd.to_numeric(inv_df["Item Total"], errors="coerce").sum()
    c1.metric("Revenue", f"₹{revenue/1e5:.1f}L" if revenue >= 1e5 else f"₹{revenue:,.0f}")

    # COGS
    cogs = 0
    if inv_df is not None and im:
        for _, row in inv_df.iterrows():
            sku = str(row.get("SKU", ""))
            qty = float(row.get("Quantity", 0) or 0)
            if sku in im:
                cogs += im[sku].get("cogs", 0) * qty
    c2.metric("COGS", f"₹{cogs/1e5:.1f}L" if cogs >= 1e5 else f"₹{cogs:,.0f}")

    # Gross Margin %
    gm_pct = ((revenue - cogs) / revenue * 100) if revenue > 0 else 0
    c3.metric("Gross Margin", f"{gm_pct:.1f}%", delta=f"{gm_pct-50:.1f}% vs 50% target")

    # Inventory Value
    inv_val = 0
    if wms_df is not None:
        val_col = next((c for c in wms_df.columns if "value" in c.lower() or "val" in c.lower()), None)
        if val_col:
            inv_val = pd.to_numeric(wms_df[val_col], errors="coerce").sum()
        elif "Qty" in wms_df.columns and im:
            title_col = next((c for c in wms_df.columns if "title" in c.lower() or "name" in c.lower()), None)
            if title_col:
                for _, row in wms_df.iterrows():
                    t = str(row.get(title_col, ""))
                    qty = float(row.get("Qty", row.get("Total Stock", 0)) or 0)
                    sku_match = next((s for s, d in im.items() if d.get("name","").lower() == t.lower()), None)
                    if sku_match:
                        inv_val += im[sku_match].get("cogs", 0) * qty
    c4.metric("Inventory Value", f"₹{inv_val/1e5:.1f}L" if inv_val >= 1e5 else f"₹{inv_val:,.0f}")

    # Total Receivables
    total_recv = 0
    if inv_df is not None and "Balance" in inv_df.columns:
        total_recv = pd.to_numeric(inv_df["Balance"], errors="coerce").sum()
    elif cbal_df is not None:
        bal_col = next((c for c in cbal_df.columns if "balance" in c.lower()), None)
        if bal_col:
            total_recv = pd.to_numeric(cbal_df[bal_col], errors="coerce").sum()
    c5.metric("Receivables", f"₹{total_recv/1e5:.1f}L" if total_recv >= 1e5 else f"₹{total_recv:,.0f}")

    # Active SKUs
    sku_count = 0
    if inv_df is not None and "SKU" in inv_df.columns:
        sku_count = inv_df["SKU"].nunique()
    elif wms_df is not None:
        sku_col = next((c for c in wms_df.columns if "sku" in c.lower() or "title" in c.lower()), None)
        if sku_col:
            sku_count = wms_df[sku_col].nunique()
    c6.metric("Active SKUs", sku_count)

    st.divider()

    # ── Row 2: Charts ──────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Revenue by Channel")
        if inv_df is not None and "Item Total" in inv_df.columns:
            channel_col = next((c for c in inv_df.columns
                                if c.lower() in ["channel", "type", "customer type"]), None)
            if channel_col:
                ch_rev = inv_df.groupby(channel_col)["Item Total"].apply(
                    lambda s: pd.to_numeric(s, errors="coerce").sum()
                ).reset_index()
                ch_rev.columns = ["Channel", "Revenue"]
                fig = go.Figure(go.Pie(
                    labels=ch_rev["Channel"], values=ch_rev["Revenue"],
                    hole=0.55, textinfo="label+percent",
                    marker_colors=["#1f6feb", "#3fb950", "#d29922", "#f85149", "#8b949e"]
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#c9d1d9", showlegend=False, height=260, margin=dict(t=10,b=10,l=10,r=10)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                # Group by customer type from registry
                if customers:
                    inv_df2 = inv_df.copy()
                    inv_df2["_type"] = inv_df2["Customer Name"].map(
                        lambda n: customers.get(str(n), {}).get("type", "Unknown")
                    ) if "Customer Name" in inv_df2.columns else "Unknown"
                    ch_rev = inv_df2.groupby("_type")["Item Total"].apply(
                        lambda s: pd.to_numeric(s, errors="coerce").sum()
                    ).reset_index()
                    ch_rev.columns = ["Channel", "Revenue"]
                    fig = go.Figure(go.Pie(
                        labels=ch_rev["Channel"], values=ch_rev["Revenue"],
                        hole=0.55, textinfo="label+percent",
                        marker_colors=["#1f6feb", "#3fb950", "#d29922"]
                    ))
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#c9d1d9", showlegend=False, height=260, margin=dict(t=10,b=10,l=10,r=10)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Upload invoice data to see channel breakdown.")
        else:
            st.info("Upload invoice data to see revenue chart.")

    with col_r:
        st.markdown("#### P&L Waterfall")
        if revenue > 0:
            shipping_est = cogs * 0.12  # rough estimate if not calculated
            gm = revenue - cogs
            cm1 = gm - shipping_est
            fig = go.Figure(go.Waterfall(
                x=["Revenue", "COGS", "Gross Margin", "Logistics", "CM1"],
                y=[revenue, -cogs, 0, -shipping_est, 0],
                measure=["absolute", "relative", "total", "relative", "total"],
                decreasing={"marker": {"color": "#f85149"}},
                increasing={"marker": {"color": "#3fb950"}},
                totals={"marker": {"color": "#1f6feb"}},
                connector={"line": {"color": "#30363d", "width": 1}},
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#c9d1d9", height=260,
                margin=dict(t=10, b=10, l=10, r=10),
                yaxis=dict(gridcolor="#21262d", tickprefix="₹"),
                xaxis=dict(gridcolor="#21262d"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Upload invoice + item master data to see P&L waterfall.")

    st.divider()

    # ── Row 3: Quick navigation cards ─────────────────────────────────────
    st.markdown("### Jump to Module")
    tabs_info = [
        ("📦 Inventory",       "Inventory",      "Stock value, ageing, shelf life by channel"),
        ("📊 P&L",             "P&L",            "Revenue → COGS → Logistics → CM1 / CM2 / CM3"),
        ("⚙️ Working Capital", "Working Capital", "DSO · DIO · DPO · Cash Conversion Cycle"),
        ("💰 Receivables",     "Receivables",    "FIFO ageing, GRN-adjusted overdue analysis"),
        ("🚚 Supplier Perf.",  "Supplier Performance", "Lead time, fill rate, PO status by vendor"),
    ]
    cols = st.columns(5)
    for col, (label, page, desc) in zip(cols, tabs_info):
        with col:
            if st.button(label, use_container_width=True, key=f"jump_{page}"):
                st.session_state["page"] = page
                st.rerun()
            st.caption(desc)


def _show_onboarding():
    st.markdown("---")
    st.markdown("""
    ### Welcome! Upload your data files to get started.

    This dashboard unifies **5 finance modules** from a single set of uploads:

    | Upload | Powers |
    |---|---|
    | **Invoice CSV** | P&L · Receivables · Working Capital (DSO) |
    | **WMS / Inventory CSV** | Inventory snapshots · Working Capital (DIO) |
    | **Customer Balance CSV** | Receivables reconciliation · Working Capital |
    | **PO CSV + Bill CSVs** | Supplier performance · Working Capital (DPO) |

    👈 Use the **sidebar** to upload files. Item master & customer registry auto-populate from your invoices.
    """)

    st.markdown("#### Expected CSV column names")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        **Invoice CSV**
        - `Invoice Number`, `Invoice Date`, `Customer Name`
        - `SKU`, `Item Name`, `Quantity`, `Item Price`, `Item Total`
        - `Balance`, `Invoice Status`, `Place of Supply`

        **WMS / Inventory CSV**
        - `SKU`, `Title`, `Total Stock` (or `Qty`)
        - `Mfg Date`, `Shelf Life`, `Value`
        """)
    with c2:
        st.markdown("""
        **Customer Balance CSV**
        - `customer_name`, `closing_balance`, `invoiced_amount`, `amount_received`

        **PO CSV**
        - `Purchase Order Number`, `Purchase Order Date`
        - `Vendor Name`, `Item Name`, `QuantityOrdered`, `Item Total`

        **Bill CSVs** — Header & Lines (same format as Lead Time Tracker app)
        """)
