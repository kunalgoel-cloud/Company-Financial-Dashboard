import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9", margin=dict(t=30, b=30, l=10, r=10),
)

POS_DELAY = {
    'MH':2,'GJ':3,'GA':3,'KA':5,'TN':5,'KL':6,'TS':5,'AP':5,
    'DL':5,'HR':5,'PB':5,'UP':6,'RJ':4,'WB':7,'OR':7,'JH':7,
    'BH':7,'AS':10,'MN':12
}


def _extract_state(pos_str):
    s = str(pos_str).strip().upper()
    if "-" in s:
        return s.split("-")[0].strip()
    return s[:2]


def _prep_invoices(df: pd.DataFrame, customers: dict) -> pd.DataFrame:
    df = df.copy()
    col_lower = {c.lower().strip(): c for c in df.columns}

    def fcol(aliases):
        for a in aliases:
            if a in col_lower: return col_lower[a]
        return None

    inv_no   = fcol(["invoice number","invoice no","invoice_number"])
    inv_date = fcol(["invoice date","date","invoice_date"])
    cust     = fcol(["customer name","customer","customer_name"])
    balance  = fcol(["balance","outstanding"])
    pos      = fcol(["place of supply","state","place_of_supply"])
    status   = fcol(["invoice status","status","invoice_status"])
    gst      = fcol(["gst treatment","gst_treatment"])

    for c, default in [(inv_no,"INV"),(cust,"Customer"),(status,"Sent"),(pos,"MH"),(gst,"business_gst")]:
        if c is None:
            df[c or "___"] = default

    df["_inv_no"]  = df[inv_no]  if inv_no  else "INV"
    df["_cust"]    = df[cust]    if cust    else ""
    df["_balance"] = pd.to_numeric(df[balance], errors="coerce").fillna(0) if balance else 0
    df["_pos"]     = df[pos]     if pos     else "MH"
    df["_status"]  = df[status]  if status  else "Sent"
    df["_gst"]     = df[gst]     if gst     else "business_gst"
    df["_date"]    = pd.to_datetime(df[inv_date], dayfirst=True, errors="coerce") if inv_date else pd.NaT

    # Filter B2B (business_gst) only for proper receivables aging
    b2b_filter = df["_gst"].str.lower().str.contains("business", na=False)
    if b2b_filter.sum() > 0:
        df = df[b2b_filter].copy()

    return df


def _fifo_reconcile(inv_df: pd.DataFrame, cbal_df: pd.DataFrame | None) -> pd.DataFrame:
    """Apply FIFO reconciliation using customer ledger balances."""
    if cbal_df is None:
        inv_df["EffectiveBalance"] = inv_df["_balance"]
        return inv_df

    cname_c = next((c for c in cbal_df.columns if "name" in c.lower()), None)
    bal_c   = next((c for c in cbal_df.columns if "balance" in c.lower()), None)
    if not cname_c or not bal_c:
        inv_df["EffectiveBalance"] = inv_df["_balance"]
        return inv_df

    ledger = dict(zip(
        cbal_df[cname_c].astype(str),
        pd.to_numeric(cbal_df[bal_c], errors="coerce").fillna(0)
    ))

    rows = []
    for cust, grp in inv_df.groupby("_cust"):
        grp = grp.sort_values("_date")
        remaining = ledger.get(str(cust), grp["_balance"].sum())
        for _, row in grp.iterrows():
            if remaining <= 0:
                row["EffectiveBalance"] = 0.0
            elif remaining >= row["_balance"]:
                row["EffectiveBalance"] = float(row["_balance"])
                remaining -= row["_balance"]
            else:
                row["EffectiveBalance"] = float(remaining)
                remaining = 0
            rows.append(row)
    return pd.DataFrame(rows)


def render():
    st.title("💰 Receivables")
    inv_df    = st.session_state["df_invoice"]
    cbal_df   = st.session_state["df_cust_bal"]
    customers = st.session_state["customers"]

    if inv_df is None:
        st.info("👈 Upload an **Invoice CSV** from the sidebar to populate this tab.")
        return

    df = _prep_invoices(inv_df, customers)

    # Credit days from sidebar
    credit_days = st.sidebar.number_input("Default credit days", value=30, min_value=0, max_value=365)

    # Transit delay
    df["TransitDays"] = df["_pos"].apply(lambda s: POS_DELAY.get(_extract_state(s), 5))
    df["GRNDate"]     = df["_date"] + pd.to_timedelta(df["TransitDays"], unit="D")
    df["TrueDueDate"] = df["GRNDate"] + pd.to_timedelta(credit_days, unit="D")

    # FIFO reconciliation
    df = _fifo_reconcile(df, cbal_df)

    today_ts = pd.Timestamp(date.today())
    df["AgingDays"] = (today_ts - df["TrueDueDate"]).dt.days

    # ── Filters ────────────────────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2 = st.columns(2)
        with fc1:
            custs = sorted(df["_cust"].dropna().unique().tolist())
            sel_custs = st.multiselect("Customer", custs, placeholder="All customers")
        with fc2:
            search = st.text_input("Search invoice number", "")

    dff = df.copy()
    if sel_custs: dff = dff[dff["_cust"].isin(sel_custs)]
    if search:    dff = dff[dff["_inv_no"].astype(str).str.contains(search, case=False, na=False)]

    overdue_mask = (dff["EffectiveBalance"] > 0) & (dff["AgingDays"] > 0)
    overdue_amt  = dff[overdue_mask]["EffectiveBalance"].sum()
    total_bal    = dff["EffectiveBalance"].sum()
    avg_aging    = dff[overdue_mask]["AgingDays"].mean() if overdue_mask.any() else 0

    # ── KPI Row ────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Receivables",  f"₹{total_bal:,.0f}")
    k2.metric("Overdue Amount",     f"₹{overdue_amt:,.0f}",
              delta=f"{overdue_amt/total_bal*100:.1f}% of total" if total_bal else "")
    k3.metric("Avg Aging (overdue)", f"{int(avg_aging)} days")
    k4.metric("Customers",          dff["_cust"].nunique())

    st.divider()

    # ── Customer summary table ─────────────────────────────────────────────
    st.markdown("#### Customer-wise summary")
    cust_summary = []
    for cust in dff["_cust"].unique():
        cdf = dff[dff["_cust"] == cust]
        cm = (cdf["EffectiveBalance"] > 0) & (cdf["AgingDays"] > 0)
        cust_summary.append({
            "Customer": cust,
            "Total Balance": cdf["EffectiveBalance"].sum(),
            "Overdue": cdf[cm]["EffectiveBalance"].sum(),
            "Avg Aging (days)": int(cdf[cm]["AgingDays"].mean()) if cm.any() else 0,
            "Invoices": len(cdf),
        })
    cs_df = pd.DataFrame(cust_summary).sort_values("Overdue", ascending=False)
    st.dataframe(cs_df, use_container_width=True, hide_index=True,
                 column_config={
                     "Total Balance": st.column_config.NumberColumn("Total Balance (₹)", format="₹%.0f"),
                     "Overdue": st.column_config.NumberColumn("Overdue (₹)", format="₹%.0f"),
                 })

    st.divider()

    # ── Ageing buckets chart ───────────────────────────────────────────────
    st.markdown("#### Ageing buckets")
    bins   = [-9999, 0, 15, 30, 60, 9999]
    labels = ["Current", "1–15 days", "16–30 days", "31–60 days", ">60 days"]
    colors = ["#3fb950", "#58a6ff", "#d29922", "#f85149", "#da3633"]
    dff["Bucket"] = pd.cut(dff["AgingDays"], bins=bins, labels=labels, right=True)
    bucket_data = (dff[dff["EffectiveBalance"] > 0]
                   .groupby("Bucket", observed=False)["EffectiveBalance"].sum()
                   .reindex(labels).fillna(0))

    c1, c2 = st.columns(2)
    with c1:
        fig_bar = go.Figure(go.Bar(
            x=bucket_data.index.tolist(), y=bucket_data.values,
            marker_color=colors,
            text=[f"₹{v/1e3:.0f}K" if v >= 1000 else f"₹{v:.0f}" for v in bucket_data.values],
            textposition="outside"
        ))
        fig_bar.update_layout(**PLOTLY_THEME, height=300,
                              yaxis=dict(gridcolor="#21262d", tickprefix="₹"),
                              xaxis=dict(gridcolor="#21262d"), title="Overdue by bucket")
        st.plotly_chart(fig_bar, use_container_width=True)

    with c2:
        fig_pie = go.Figure(go.Pie(
            labels=bucket_data.index.tolist(), values=bucket_data.values,
            hole=0.55, marker_colors=colors, textinfo="label+percent"
        ))
        fig_pie.update_layout(**PLOTLY_THEME, height=300, showlegend=False,
                              title="Concentration by bucket")
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ── Detailed invoice table ─────────────────────────────────────────────
    st.markdown("#### Detailed invoice aging")

    def _flag(row):
        if row["EffectiveBalance"] <= 0: return "✅ Settled"
        if row["AgingDays"] <= 0:        return "🟢 Current"
        if row["AgingDays"] <= 15:       return "🟡 1–15 days"
        if row["AgingDays"] <= 30:       return "🟠 16–30 days"
        if row["AgingDays"] <= 60:       return "🔴 31–60 days"
        return "💀 >60 days"

    dff["Status"] = dff.apply(_flag, axis=1)
    dff_disp = dff[dff["EffectiveBalance"] > 0].copy()
    disp_cols = {
        "Status": "Status",
        "_inv_no": "Invoice #",
        "_cust": "Customer",
        "_date": "Invoice Date",
        "GRNDate": "GRN Date",
        "TrueDueDate": "Due Date",
        "_balance": "Invoice Balance",
        "EffectiveBalance": "Effective Balance",
        "AgingDays": "Aging Days",
    }
    dff_disp = dff_disp[[c for c in disp_cols if c in dff_disp.columns]].rename(columns=disp_cols)
    for dc in ["Invoice Date", "GRN Date", "Due Date"]:
        if dc in dff_disp.columns:
            dff_disp[dc] = pd.to_datetime(dff_disp[dc], errors="coerce").dt.strftime("%d-%b-%Y")

    st.dataframe(
        dff_disp.sort_values("Aging Days", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={
            "Invoice Balance":   st.column_config.NumberColumn(format="₹%.0f"),
            "Effective Balance": st.column_config.NumberColumn(format="₹%.0f"),
        }
    )

    # Download
    csv = dff_disp.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download aging report", csv,
                       f"receivables_aging_{date.today()}.csv", "text/csv")
