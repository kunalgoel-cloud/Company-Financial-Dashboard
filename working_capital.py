import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9", margin=dict(t=30, b=30, l=10, r=10),
)


def _safe_col(df, aliases):
    for a in aliases:
        for c in df.columns:
            if a.lower() in c.lower():
                return c
    return None


def render():
    st.title("⚙️ Working Capital")

    inv_df   = st.session_state["df_invoice"]
    wms_df   = st.session_state["df_wms"]
    cbal_df  = st.session_state["df_cust_bal"]
    po_df    = st.session_state["df_po"]
    bill_hdr = st.session_state["df_bill_hdr"]
    im       = st.session_state["item_master"]

    # ── Targets ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("**WC Targets (days)**")
        t_dso = st.number_input("Target DSO", value=60, min_value=1)
        t_dio = st.number_input("Target DIO", value=45, min_value=1)
        t_dpo = st.number_input("Target DPO", value=45, min_value=1)

    # ── Analysis period ────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        period_start = st.date_input("Period start", value=datetime(2025, 4, 1).date())
    with col_b:
        period_end = st.date_input("Period end", value=datetime(2026, 3, 31).date())
    days = max((period_end - period_start).days, 1)

    st.divider()

    # ── DSO ────────────────────────────────────────────────────────────────
    dso = None
    if cbal_df is not None and inv_df is not None:
        bal_col = _safe_col(cbal_df, ["closing_balance", "balance", "outstanding"])
        inv_col = _safe_col(cbal_df, ["invoiced", "invoice", "sales", "billed"])
        if bal_col and inv_col:
            total_recv = pd.to_numeric(cbal_df[bal_col], errors="coerce").sum()
            total_inv  = pd.to_numeric(cbal_df[inv_col], errors="coerce").sum()
            if total_inv > 0:
                dso = (total_recv / total_inv) * days
    elif inv_df is not None:
        bal_c = _safe_col(inv_df, ["balance", "outstanding"])
        tot_c = _safe_col(inv_df, ["total", "item total", "amount"])
        if bal_c and tot_c:
            total_recv = pd.to_numeric(inv_df[bal_c], errors="coerce").sum()
            total_rev  = pd.to_numeric(inv_df[tot_c], errors="coerce").sum()
            if total_rev > 0:
                dso = (total_recv / total_rev) * days

    # ── DIO ────────────────────────────────────────────────────────────────
    dio = None
    if wms_df is not None and inv_df is not None:
        val_c = _safe_col(wms_df, ["value", "val"])
        qty_c = _safe_col(wms_df, ["qty", "stock", "quantity"])
        inv_val = 0
        if val_c:
            inv_val = pd.to_numeric(wms_df[val_c], errors="coerce").sum()
        elif qty_c and im:
            title_c = _safe_col(wms_df, ["title", "name", "product"])
            if title_c:
                im_name = {v.get("name","").lower(): v.get("cogs",0) for v in im.values()}
                inv_val = (wms_df.apply(
                    lambda r: pd.to_numeric(r.get(qty_c, 0), errors="coerce") *
                              im_name.get(str(r.get(title_c, "")).lower(), 0), axis=1
                ).sum())

        cogs_total = 0
        sku_c = _safe_col(inv_df, ["sku", "item code"])
        qty_inv_c = _safe_col(inv_df, ["quantity", "qty"])
        if sku_c and qty_inv_c and im:
            im_sku = {k: v.get("cogs",0) for k,v in im.items()}
            cogs_total = (inv_df.apply(
                lambda r: pd.to_numeric(r.get(qty_inv_c,0), errors="coerce") *
                          im_sku.get(str(r.get(sku_c,"")), 0), axis=1
            ).sum())

        if cogs_total > 0 and inv_val >= 0:
            dio = (inv_val / cogs_total) * days

    # ── DPO ────────────────────────────────────────────────────────────────
    dpo = None
    if bill_hdr is not None and po_df is not None:
        payables_c = _safe_col(bill_hdr, ["balance", "outstanding", "bcy_balance", "amount"])
        po_total_c = _safe_col(po_df, ["item total", "total", "amount", "value"])
        if payables_c and po_total_c:
            total_payable = pd.to_numeric(bill_hdr[payables_c], errors="coerce").sum()
            total_purchases = pd.to_numeric(po_df[po_total_c], errors="coerce").sum()
            if total_purchases > 0:
                dpo = (total_payable / total_purchases) * days

    ccc = None
    if dso is not None and dio is not None and dpo is not None:
        ccc = dso + dio - dpo

    # ── KPI Row ────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    def metric_delta(val, target, lower_is_better=True):
        if val is None: return "N/A", None
        diff = val - target
        delta = f"{diff:+.1f}d vs target"
        return f"{val:.1f} days", delta

    dso_val, dso_delta = metric_delta(dso, t_dso)
    dio_val, dio_delta = metric_delta(dio, t_dio)
    dpo_val, dpo_delta = metric_delta(dpo, t_dpo, lower_is_better=False)

    k1.metric("DSO — Days Sales Outstanding", dso_val, delta=dso_delta, delta_color="inverse")
    k2.metric("DIO — Days Inventory Outstanding", dio_val, delta=dio_delta, delta_color="inverse")
    k3.metric("DPO — Days Payables Outstanding", dpo_val, delta=dpo_delta)
    if ccc is not None:
        k4.metric("Cash Conversion Cycle", f"{ccc:.1f} days",
                  delta=f"{ccc-(t_dso+t_dio-t_dpo):+.1f}d vs target", delta_color="inverse")
    else:
        k4.metric("Cash Conversion Cycle", "N/A (upload all files)")

    st.divider()

    # ── Gauge charts ───────────────────────────────────────────────────────
    def gauge(title, val, target, max_val, color):
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=val if val else 0,
            delta={"reference": target, "valueformat": ".1f", "suffix": "d"},
            title={"text": title, "font": {"color": "#c9d1d9", "size": 13}},
            number={"suffix": " days", "font": {"color": "#e6edf3", "size": 22}},
            gauge={
                "axis": {"range": [0, max_val], "tickcolor": "#8b949e"},
                "bar": {"color": color},
                "bgcolor": "#0d1117",
                "bordercolor": "#21262d",
                "threshold": {"line": {"color": "#f85149", "width": 2}, "value": target},
                "steps": [
                    {"range": [0, target*0.8], "color": "#0d2a1f"},
                    {"range": [target*0.8, target], "color": "#1a3520"},
                    {"range": [target, max_val], "color": "#2a0f0f"},
                ],
            }
        ))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#c9d1d9",
                          height=220, margin=dict(t=40,b=20,l=20,r=20))
        return fig

    g1, g2, g3 = st.columns(3)
    with g1:
        if dso is not None:
            st.plotly_chart(gauge("DSO", dso, t_dso, max(t_dso*2.5, 150), "#1f6feb"), use_container_width=True)
        else:
            st.info("Upload **Invoice CSV** + **Customer Balance CSV** to calculate DSO.")
    with g2:
        if dio is not None:
            st.plotly_chart(gauge("DIO", dio, t_dio, max(t_dio*2.5, 120), "#3fb950"), use_container_width=True)
        else:
            st.info("Upload **WMS CSV** + **Invoice CSV** + **Item Master** to calculate DIO.")
    with g3:
        if dpo is not None:
            st.plotly_chart(gauge("DPO", dpo, t_dpo, max(t_dpo*2.5, 180), "#d29922"), use_container_width=True)
        else:
            st.info("Upload **PO CSV** + **Bill Header CSV** to calculate DPO.")

    # ── CCC bar chart ──────────────────────────────────────────────────────
    if ccc is not None:
        st.markdown("#### Cash Conversion Cycle breakdown")
        fig_ccc = go.Figure()
        components = [
            ("DSO", dso, "#1f6feb", "Receivables"),
            ("DIO", dio, "#3fb950", "Inventory"),
            ("DPO (-))", -dpo, "#d29922", "Payables offset"),
        ]
        for label, val, color, desc in components:
            fig_ccc.add_trace(go.Bar(
                name=f"{label}: {val:.1f}d", x=[val], y=[desc],
                orientation="h", marker_color=color,
                text=f"{abs(val):.1f} days", textposition="auto"
            ))
        fig_ccc.add_vline(x=0, line_color="#8b949e", line_width=1)
        fig_ccc.update_layout(**PLOTLY_THEME, barmode="relative", height=200,
                              xaxis_title="Days", yaxis_title="",
                              legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig_ccc, use_container_width=True)

    st.divider()

    # ── Customer-level DSO ─────────────────────────────────────────────────
    if cbal_df is not None:
        st.markdown("#### Customer-level DSO analysis")
        cname_c = _safe_col(cbal_df, ["customer_name", "customer", "name"])
        bal_c   = _safe_col(cbal_df, ["closing_balance", "balance"])
        inv_c   = _safe_col(cbal_df, ["invoiced", "invoice", "billed", "sales"])
        recv_c  = _safe_col(cbal_df, ["received", "amount_received", "collection"])

        if cname_c and bal_c:
            cbal = cbal_df.copy()
            cbal["closing_balance"] = pd.to_numeric(cbal[bal_c], errors="coerce").fillna(0)
            if inv_c:
                cbal["invoiced"] = pd.to_numeric(cbal[inv_c], errors="coerce").fillna(1)
                cbal["DSO"] = (cbal["closing_balance"] / cbal["invoiced"].replace(0,1)) * days
            if recv_c:
                cbal["amount_received"] = pd.to_numeric(cbal[recv_c], errors="coerce").fillna(0)
                cbal["CEI"] = cbal["amount_received"] / cbal["invoiced"].replace(0,1) * 100

            top10 = cbal.sort_values("closing_balance", ascending=False).head(15)
            fig_top = px.bar(top10, x=cname_c, y="closing_balance",
                             color="DSO" if "DSO" in top10.columns else "closing_balance",
                             color_continuous_scale="RdYlGn_r",
                             title="Top 15 debtors by outstanding balance")
            fig_top.update_layout(**PLOTLY_THEME, height=320,
                                  xaxis=dict(gridcolor="#21262d", tickangle=-35),
                                  yaxis=dict(gridcolor="#21262d", tickprefix="₹"))
            st.plotly_chart(fig_top, use_container_width=True)

    # ── SKU-level DIO ──────────────────────────────────────────────────────
    if wms_df is not None and im:
        st.markdown("#### SKU-level inventory days")
        val_c   = _safe_col(wms_df, ["value"])
        qty_c   = _safe_col(wms_df, ["qty","stock","quantity"])
        title_c = _safe_col(wms_df, ["title","name","product"])
        if title_c and qty_c:
            wms = wms_df.copy()
            im_name = {v.get("name","").lower(): v.get("cogs",0) for v in im.values()}
            wms["Stock"] = pd.to_numeric(wms[qty_c], errors="coerce").fillna(0)
            wms["UnitCost"] = wms[title_c].apply(lambda t: im_name.get(str(t).lower(), 0))
            wms["Value"]    = wms["Stock"] * wms["UnitCost"]
            if inv_df is not None:
                sku_c = _safe_col(inv_df, ["sku","item code"])
                qinv_c = _safe_col(inv_df, ["quantity","qty"])
                if sku_c and qinv_c:
                    sold_by_sku = (inv_df.assign(
                        _cogs=inv_df.apply(lambda r: pd.to_numeric(r.get(qinv_c,0), errors="coerce") *
                                           {k:v.get("cogs",0) for k,v in im.items()}.get(str(r.get(sku_c,"")),0), axis=1)
                    ).groupby(sku_c)["_cogs"].sum().reset_index())
                    sold_by_sku.columns = ["SKU","COGS_sold"]
                    wms["SKU"] = wms[title_c].apply(
                        lambda t: next((k for k,v in im.items() if v.get("name","").lower()==str(t).lower()), "")
                    )
                    wms = wms.merge(sold_by_sku, on="SKU", how="left")
                    wms["DIO_SKU"] = (wms["Value"] / wms["COGS_sold"].replace(0,1)) * days
                    wms["Risk"] = wms["DIO_SKU"].apply(
                        lambda d: "Fast (<30d)" if d<=30 else "Healthy (30-90d)" if d<=90 else "High Risk (>90d)"
                    )
                    cols = [title_c,"Stock","Value","DIO_SKU","Risk"]
                    st.dataframe(
                        wms[cols].rename(columns={title_c:"Product","DIO_SKU":"DIO (days)"})
                            .sort_values("DIO (days)", ascending=False),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "Value": st.column_config.NumberColumn("Value (₹)", format="₹%.0f"),
                            "DIO (days)": st.column_config.NumberColumn(format="%.1f"),
                        }
                    )
