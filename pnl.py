import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9", margin=dict(t=30, b=30, l=10, r=10),
)

# Simple zone-based logistics rate (₹ per unit) — overridable from UI
DEFAULT_LOGISTICS = {"B2B": 35.0, "B2C": 50.0, "Marketplace": 0.0, "D2C": 55.0}


def _prep_invoice(df: pd.DataFrame, im: dict, customers: dict) -> pd.DataFrame:
    df = df.copy()
    str_cols = {"Item Name": ["item name", "item", "product"],
                "SKU": ["sku", "item code"],
                "Customer Name": ["customer name", "customer"],
                "Invoice Date": ["invoice date", "date"],
                "Invoice Number": ["invoice number", "invoice no"],
                "Place of Supply": ["place of supply", "state"]}
    num_cols = {"Quantity": ["quantity", "qty"],
                "Item Price": ["item price", "unit price", "rate"],
                "Item Total": ["item total", "amount", "total"],
                "Balance": ["balance", "outstanding"]}

    col_lower = {c.lower().strip(): c for c in df.columns}
    for target, aliases in {**str_cols, **num_cols}.items():
        if target not in df.columns:
            for a in aliases:
                if a in col_lower:
                    df[target] = df[col_lower[a]]
                    break

    for c in str_cols:
        if c not in df.columns: df[c] = ""
    for c in num_cols:
        if c not in df.columns: df[c] = 0.0
        else: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["Invoice Date"] = pd.to_datetime(df["Invoice Date"], dayfirst=True, errors="coerce")

    # Attach channel
    df["Channel"] = df["Customer Name"].apply(
        lambda n: customers.get(str(n), {}).get("channel", "Unknown")
    )
    df["CustomerType"] = df["Customer Name"].apply(
        lambda n: customers.get(str(n), {}).get("type", "B2C")
    )

    # COGS from item master
    im_name = {v.get("name","").lower(): v.get("cogs",0) for v in im.values()}
    im_sku  = {k: v.get("cogs",0) for k,v in im.items()}
    df["UnitCOGS"] = df.apply(
        lambda r: im_sku.get(str(r["SKU"]),
                  im_name.get(str(r["Item Name"]).lower(), 0)), axis=1
    )
    df["COGS"] = df["UnitCOGS"] * df["Quantity"]
    return df


def render():
    st.title("📊 Profit & Loss")
    inv_df    = st.session_state["df_invoice"]
    im        = st.session_state["item_master"]
    customers = st.session_state["customers"]

    if inv_df is None:
        st.info("👈 Upload an **Invoice CSV** from the sidebar to populate this tab.")
        return

    df = _prep_invoice(inv_df, im, customers)

    # ── Filters ────────────────────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            channels = ["All"] + sorted(df["Channel"].dropna().unique().tolist())
            ch_filter = st.selectbox("Channel", channels)
        with fc2:
            products = ["All"] + sorted(df["Item Name"].dropna().unique().tolist())[:80]
            prod_filter = st.selectbox("Product", products)
        with fc3:
            min_d = df["Invoice Date"].min()
            max_d = df["Invoice Date"].max()
            default_from = max_d - timedelta(days=90) if pd.notna(max_d) else datetime(2025,1,1)
            date_from = st.date_input("From", value=default_from.date() if pd.notna(default_from) else None)
        with fc4:
            date_to = st.date_input("To", value=max_d.date() if pd.notna(max_d) else None)

    # Logistics rate override
    with st.expander("⚙️ Logistics cost settings", expanded=False):
        lc1, lc2, lc3 = st.columns(3)
        log_b2b = lc1.number_input("B2B rate (₹/unit)", value=DEFAULT_LOGISTICS["B2B"], step=1.0)
        log_b2c = lc2.number_input("B2C rate (₹/unit)", value=DEFAULT_LOGISTICS["B2C"], step=1.0)
        log_mkt = lc3.number_input("Marketplace rate (₹/unit)", value=DEFAULT_LOGISTICS["Marketplace"], step=1.0)

    log_rates = {"B2B": log_b2b, "B2C": log_b2c, "Marketplace": log_mkt, "D2C": log_b2c, "Unknown": log_b2c}

    # Apply filters
    dff = df.copy()
    if ch_filter != "All":
        dff = dff[dff["Channel"] == ch_filter]
    if prod_filter != "All":
        dff = dff[dff["Item Name"] == prod_filter]
    if date_from and date_to:
        dff = dff[(dff["Invoice Date"].dt.date >= date_from) &
                  (dff["Invoice Date"].dt.date <= date_to)]

    if dff.empty:
        st.warning("No data for selected filters.")
        return

    # ── Compute P&L lines ──────────────────────────────────────────────────
    revenue = dff["Item Total"].sum()
    cogs    = dff["COGS"].sum()
    dff["LogisticsCost"] = dff["Quantity"] * dff["Channel"].map(
        lambda c: log_rates.get(c, log_b2c)
    )
    logistics = dff["LogisticsCost"].sum()
    gm = revenue - cogs
    cm1 = gm - logistics
    gm_pct  = gm/revenue*100 if revenue else 0
    cm1_pct = cm1/revenue*100 if revenue else 0

    # ── KPI Row ────────────────────────────────────────────────────────────
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Revenue",       f"₹{revenue:,.0f}")
    k2.metric("COGS",          f"₹{cogs:,.0f}", delta=f"{cogs/revenue*100:.1f}% of rev" if revenue else "")
    k3.metric("Gross Margin",  f"₹{gm:,.0f}", delta=f"{gm_pct:.1f}%")
    k4.metric("Logistics Cost",f"₹{logistics:,.0f}", delta=f"{logistics/revenue*100:.1f}% of rev" if revenue else "")
    k5.metric("CM1",           f"₹{cm1:,.0f}", delta=f"{cm1_pct:.1f}%")
    k6.metric("Orders",        f"{dff['Invoice Number'].nunique():,}")

    st.divider()

    # ── P&L Statement Table ────────────────────────────────────────────────
    st.markdown("#### P&L Statement")
    pl_rows = [
        {"Line Item": "Revenue (Net Sales)",       "Amount (₹)": revenue,   "% of Revenue": 100.0},
        {"Line Item": "Cost of Goods Sold (COGS)", "Amount (₹)": -cogs,     "% of Revenue": cogs/revenue*100 if revenue else 0},
        {"Line Item": "─── Gross Margin",          "Amount (₹)": gm,        "% of Revenue": gm_pct},
        {"Line Item": "Logistics Cost",            "Amount (₹)": -logistics, "% of Revenue": logistics/revenue*100 if revenue else 0},
        {"Line Item": "─── Contribution Margin 1", "Amount (₹)": cm1,       "% of Revenue": cm1_pct},
    ]
    pl_df = pd.DataFrame(pl_rows)
    st.dataframe(
        pl_df, hide_index=True, use_container_width=True,
        column_config={
            "Amount (₹)": st.column_config.NumberColumn("Amount (₹)", format="₹%.0f"),
            "% of Revenue": st.column_config.NumberColumn("% of Revenue", format="%.1f%%"),
        }
    )

    # ── Charts ─────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Waterfall P&L")
        fig_wf = go.Figure(go.Waterfall(
            x=["Revenue", "COGS", "Gross Margin", "Logistics", "CM1"],
            y=[revenue, -cogs, 0, -logistics, 0],
            measure=["absolute","relative","total","relative","total"],
            decreasing={"marker":{"color":"#f85149"}},
            increasing={"marker":{"color":"#3fb950"}},
            totals={"marker":{"color":"#1f6feb"}},
            connector={"line":{"color":"#30363d","width":1}},
            text=[f"₹{abs(v)/1e3:.0f}K" if abs(v)>=1000 else f"₹{abs(v):.0f}"
                  for v in [revenue, -cogs, gm, -logistics, cm1]],
            textposition="outside",
        ))
        fig_wf.update_layout(**PLOTLY_THEME, height=320,
                             yaxis=dict(gridcolor="#21262d", tickprefix="₹"),
                             xaxis=dict(gridcolor="#21262d"))
        st.plotly_chart(fig_wf, use_container_width=True)

    with c2:
        st.markdown("#### Revenue vs COGS by Channel")
        ch_agg = dff.groupby("Channel").agg(
            Revenue=("Item Total","sum"), COGS=("COGS","sum"),
            Logistics=("LogisticsCost","sum")
        ).reset_index()
        fig_ch = go.Figure()
        for col, color in [("Revenue","#1f6feb"),("COGS","#f85149"),("Logistics","#d29922")]:
            fig_ch.add_trace(go.Bar(name=col, x=ch_agg["Channel"], y=ch_agg[col],
                                   marker_color=color))
        fig_ch.update_layout(**PLOTLY_THEME, barmode="group", height=320,
                             yaxis=dict(gridcolor="#21262d", tickprefix="₹"),
                             xaxis=dict(gridcolor="#21262d"),
                             legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_ch, use_container_width=True)

    # ── COGS breakdown ─────────────────────────────────────────────────────
    st.markdown("#### COGS breakdown by product")
    if dff["COGS"].sum() > 0:
        prod_cogs = (dff.groupby("Item Name")
                    .agg(Revenue=("Item Total","sum"), COGS=("COGS","sum"), Qty=("Quantity","sum"))
                    .assign(GM=lambda x: x["Revenue"]-x["COGS"],
                            GM_pct=lambda x: (x["Revenue"]-x["COGS"])/x["Revenue"].replace(0,1)*100)
                    .sort_values("Revenue", ascending=False).reset_index())
        fig_pc = px.bar(prod_cogs.head(20), x="Item Name", y=["Revenue","COGS"],
                        barmode="group", color_discrete_sequence=["#1f6feb","#f85149"])
        fig_pc.update_layout(**PLOTLY_THEME, height=320,
                             yaxis=dict(gridcolor="#21262d", tickprefix="₹"),
                             xaxis=dict(gridcolor="#21262d", tickangle=-35),
                             legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig_pc, use_container_width=True)

        st.markdown("#### Product-level P&L")
        prod_cogs["GM %"] = prod_cogs["GM_pct"].map(lambda x: f"{x:.1f}%")
        st.dataframe(
            prod_cogs[["Item Name","Revenue","COGS","GM","GM %","Qty"]].rename(
                columns={"Item Name":"Product","Revenue":"Revenue (₹)","COGS":"COGS (₹)","GM":"Gross Margin (₹)"}),
            use_container_width=True, hide_index=True,
            column_config={
                "Revenue (₹)":       st.column_config.NumberColumn(format="₹%.0f"),
                "COGS (₹)":          st.column_config.NumberColumn(format="₹%.0f"),
                "Gross Margin (₹)":  st.column_config.NumberColumn(format="₹%.0f"),
            }
        )
    else:
        st.info("Add COGS values in **Item Master** (sidebar) to see product-level P&L.")

    # ── Logistics deep dive ─────────────────────────────────────────────────
    with st.expander("🚚 Logistics cost deep dive"):
        log_agg = (dff.groupby(["Channel","CustomerType"])
                   .agg(Units=("Quantity","sum"), LogisticsCost=("LogisticsCost","sum"),
                        Revenue=("Item Total","sum"))
                   .assign(LogPct=lambda x: x["LogisticsCost"]/x["Revenue"].replace(0,1)*100)
                   .reset_index())
        st.dataframe(log_agg, use_container_width=True, hide_index=True,
                     column_config={
                         "LogisticsCost": st.column_config.NumberColumn("Logistics (₹)", format="₹%.0f"),
                         "Revenue": st.column_config.NumberColumn("Revenue (₹)", format="₹%.0f"),
                         "LogPct": st.column_config.NumberColumn("Logistics %", format="%.1f%%"),
                     })

    if not im:
        st.warning("⚠️ Item Master is empty — COGS shows ₹0. Add products via the sidebar ⚙️ Item Master.")
