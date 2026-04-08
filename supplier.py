import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9", margin=dict(t=30, b=30, l=10, r=10),
)


def _fcol(df, aliases):
    for a in aliases:
        for c in df.columns:
            if a.lower() in c.lower():
                return c
    return None


def _prep_po(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {}
    for c in df.columns:
        cl = c.lower()
        if "purchase order number" in cl or "po number" in cl or "po_number" in cl: rename[c]="PO_No"
        elif "purchase order date" in cl or "po date" in cl: rename[c]="PO_Date"
        elif "vendor name" in cl or "supplier" in cl: rename[c]="Vendor"
        elif "item name" in cl or "item" in cl: rename[c]="Item"
        elif "quantityordered" in cl or "qty ordered" in cl or "order qty" in cl: rename[c]="QtyOrdered"
        elif "item total" in cl or "po value" in cl or "amount" in cl: rename[c]="POValue"
    df = df.rename(columns=rename)
    for col in ["PO_No","Vendor","Item"]:
        if col not in df.columns: df[col]=""
    for col in ["QtyOrdered","POValue"]:
        if col not in df.columns: df[col]=0.0
        else: df[col]=pd.to_numeric(df[col],errors="coerce").fillna(0)
    df["PO_Date"] = pd.to_datetime(df.get("PO_Date",""), dayfirst=True, errors="coerce")
    df["PO_No"]  = df["PO_No"].astype(str).str.strip()
    df["Item"]   = df["Item"].astype(str).str.strip().str.lower()
    return df


def _prep_bill_hdr(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {}
    for c in df.columns:
        cl = c.lower()
        if "bill#" in cl or "bill number" in cl or "invoice_number" in cl: rename[c]="InvNo"
        elif "reference number" in cl or "po_ref" in cl or "po ref" in cl: rename[c]="PO_Ref"
        elif "vendor name" in cl or "supplier" in cl: rename[c]="Vendor"
        elif "date" in cl: rename[c]="BillDate"
        elif "amount" in cl or "balance" in cl: rename[c]="BillAmt"
    df = df.rename(columns=rename)
    for col in ["InvNo","Vendor","PO_Ref"]:
        if col not in df.columns: df[col]=""
    df["BillDate"] = pd.to_datetime(df.get("BillDate",""), dayfirst=True, errors="coerce")
    df["InvNo"]   = df["InvNo"].astype(str).str.strip()
    df["PO_Ref"]  = df["PO_Ref"].astype(str).str.strip()
    return df


def _prep_bill_lines(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {}
    for c in df.columns:
        cl = c.lower()
        if "bill number" in cl or "invoice_number" in cl: rename[c]="InvNo"
        elif "vendor name" in cl or "supplier" in cl: rename[c]="Vendor"
        elif "bill date" in cl or "invoice date" in cl: rename[c]="BillDate"
        elif "item name" in cl or "item" in cl: rename[c]="Item"
        elif "quantity" in cl or "qty" in cl: rename[c]="InvQty"
        elif "item total" in cl or "amount" in cl: rename[c]="BillAmt"
    df = df.rename(columns=rename)
    for col in ["InvNo","Vendor","Item"]:
        if col not in df.columns: df[col]=""
    if "InvQty" not in df.columns: df["InvQty"]=0.0
    else: df["InvQty"]=pd.to_numeric(df["InvQty"],errors="coerce").fillna(0)
    df["BillDate"] = pd.to_datetime(df.get("BillDate",""), dayfirst=False, errors="coerce")
    df["InvNo"]    = df["InvNo"].astype(str).str.strip()
    df["Item"]     = df["Item"].astype(str).str.strip().str.lower()
    return df


def _build_joined(po, bill_hdr, bill_lines):
    # Attach PO_Ref to lines via InvNo+Vendor
    lines_enriched = bill_lines.merge(
        bill_hdr[["InvNo","Vendor","PO_Ref","BillDate"]].rename(columns={"BillDate":"BillDateHdr"}),
        on=["InvNo","Vendor"], how="left"
    )
    lines_enriched = lines_enriched[
        lines_enriched["PO_Ref"].notna() & ~lines_enriched["PO_Ref"].isin(["","nan","None"])
    ]
    # Join with PO
    joined = lines_enriched.merge(
        po, left_on=["PO_Ref","Item","Vendor"], right_on=["PO_No","Item","Vendor"], how="inner"
    )
    joined["BillDate"] = joined["BillDate"].combine_first(joined["BillDateHdr"])
    joined["LeadTime"] = (joined["BillDate"] - joined["PO_Date"]).dt.days
    joined = joined[joined["LeadTime"] >= 0]
    joined["W_Comp"] = joined["LeadTime"] * joined["InvQty"]
    return joined


def _walt(df):
    q = df["InvQty"].sum()
    return df["W_Comp"].sum() / q if q > 0 else 0


def _fulfil_pct(df):
    u = df.drop_duplicates(subset=["PO_No","Item"])
    tot_ord = u["QtyOrdered"].sum()
    tot_inv = u["InvQty"].sum() if "InvQty" in u.columns else 0
    return (tot_inv / tot_ord * 100) if tot_ord > 0 else 0


def render():
    st.title("🚚 Supplier Performance")
    po_df    = st.session_state["df_po"]
    bill_hdr = st.session_state["df_bill_hdr"]
    bill_lines = st.session_state["df_bill_lines"]

    if po_df is None:
        st.info("👈 Upload **PO CSV**, **Bill Header CSV**, and **Bill Lines CSV** to populate this tab.")
        st.markdown("""
        **Expected columns:**
        - **PO CSV**: `Purchase Order Number`, `Purchase Order Date`, `Vendor Name`, `Item Name`, `QuantityOrdered`, `Item Total`
        - **Bill Header CSV**: `Bill#`, `Date`, `Vendor Name`, `Reference Number` (PO number), `Amount`
        - **Bill Lines CSV**: `Bill Number`, `Bill Date`, `Vendor Name`, `Item Name`, `Quantity`, `Item Total`
        """)
        return

    po = _prep_po(po_df)

    # If only PO available, show basic PO-level view
    if bill_hdr is None or bill_lines is None:
        st.warning("Upload **Bill Header** and **Bill Lines** CSVs for lead time analysis. Showing PO summary only.")
        _render_po_only(po)
        return

    bill_h = _prep_bill_hdr(bill_hdr)
    bill_l = _prep_bill_lines(bill_lines)

    joined = _build_joined(po, bill_h, bill_l)

    if joined.empty:
        st.warning("No matching records between PO and Bills. Check that PO numbers and vendor names match exactly.")
        _render_po_only(po)
        return

    # ── Filters ────────────────────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            vendors = ["All"] + sorted(po["Vendor"].dropna().unique().tolist())
            vendor_f = st.selectbox("Vendor", vendors)
        with fc2:
            min_d = po["PO_Date"].min()
            max_d = po["PO_Date"].max()
            df_from = st.date_input("PO from", value=min_d.date() if pd.notna(min_d) else None)
        with fc3:
            df_to = st.date_input("PO to", value=max_d.date() if pd.notna(max_d) else None)
        with fc4:
            po_filter = st.multiselect("PO Numbers", sorted(po["PO_No"].unique()), placeholder="All POs")

    view = joined.copy()
    if vendor_f != "All":  view = view[view["Vendor"] == vendor_f]
    if df_from and df_to:
        view = view[(view["PO_Date"].dt.date >= df_from) & (view["PO_Date"].dt.date <= df_to)]
    if po_filter: view = view[view["PO_No"].isin(po_filter)]

    all_po_filtered = po.copy()
    if vendor_f != "All":  all_po_filtered = all_po_filtered[all_po_filtered["Vendor"] == vendor_f]
    if po_filter: all_po_filtered = all_po_filtered[all_po_filtered["PO_No"].isin(po_filter)]

    # ── KPIs ───────────────────────────────────────────────────────────────
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Total PO Value",       f"₹{all_po_filtered['POValue'].sum():,.0f}")
    k2.metric("Total POs",            all_po_filtered["PO_No"].nunique())
    uninvoiced = all_po_filtered[~all_po_filtered["PO_No"].isin(view["PO_No"].unique())]["PO_No"].nunique()
    k3.metric("Yet to Supply",        uninvoiced, delta=f"-{uninvoiced} pending" if uninvoiced else None,
              delta_color="inverse")
    k4.metric("Unique SKUs",          view["Item"].nunique())
    walt_val = _walt(view) if not view.empty else 0
    k5.metric("Weighted Avg Lead Time", f"{walt_val:.1f} days")
    k6.metric("Avg Fill Rate",         f"{_fulfil_pct(view):.1f}%")

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Lead time by PO")
        if not view.empty:
            po_walt = (view.groupby("PO_No").apply(_walt, include_groups=False)
                       .reset_index(name="WALT"))
            fig = px.bar(po_walt, x="PO_No", y="WALT",
                         color="WALT", color_continuous_scale="RdYlGn_r",
                         labels={"WALT":"Weighted Lead Time (days)","PO_No":"PO Number"})
            fig.update_layout(**PLOTLY_THEME, height=320,
                              xaxis=dict(gridcolor="#21262d", tickangle=-35),
                              yaxis=dict(gridcolor="#21262d"))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("#### Lead time efficiency by SKU")
        if not view.empty:
            item_walt = (view.groupby("Item").apply(_walt, include_groups=False)
                         .reset_index(name="WALT").sort_values("WALT"))
            item_walt["Item"] = item_walt["Item"].str.title()
            fig2 = px.bar(item_walt, x="WALT", y="Item", orientation="h",
                          color="WALT", color_continuous_scale="RdYlGn_r",
                          labels={"WALT":"Lead Time (days)","Item":"SKU"})
            fig2.update_layout(**PLOTLY_THEME, height=320,
                               xaxis=dict(gridcolor="#21262d"),
                               yaxis=dict(gridcolor="#21262d"))
            st.plotly_chart(fig2, use_container_width=True)

    # Vendor comparison (only if All Vendors)
    if vendor_f == "All" and not view.empty:
        st.markdown("#### Vendor comparison")
        vc1, vc2 = st.columns(2)
        with vc1:
            vend_walt = (view.groupby("Vendor").apply(_walt, include_groups=False)
                         .reset_index(name="WALT"))
            fig3 = px.bar(vend_walt, x="Vendor", y="WALT", color="Vendor",
                          title="Weighted lead time by vendor")
            fig3.update_layout(**PLOTLY_THEME, height=280, showlegend=False,
                               xaxis=dict(gridcolor="#21262d", tickangle=-25),
                               yaxis=dict(gridcolor="#21262d"))
            st.plotly_chart(fig3, use_container_width=True)
        with vc2:
            vend_fill = (view.drop_duplicates(["PO_No","Item","Vendor"])
                         .groupby("Vendor").apply(
                             lambda d: (d["InvQty"].sum()/d["QtyOrdered"].sum()*100)
                             if d["QtyOrdered"].sum()>0 else 0, include_groups=False
                         ).reset_index(name="FillPct"))
            fig4 = px.bar(vend_fill, x="Vendor", y="FillPct", color="Vendor",
                          title="Fill rate % by vendor", range_y=[0,110])
            fig4.add_hline(y=100, line_dash="dash", line_color="#3fb950", opacity=0.6)
            fig4.update_layout(**PLOTLY_THEME, height=280, showlegend=False,
                               xaxis=dict(gridcolor="#21262d", tickangle=-25),
                               yaxis=dict(gridcolor="#21262d"))
            st.plotly_chart(fig4, use_container_width=True)

    st.divider()

    # ── Fulfilment table ────────────────────────────────────────────────────
    st.markdown("#### PO fulfilment detail")
    inv_keys = set(zip(view["PO_No"], view["Item"]))
    unfulfilled = all_po_filtered[
        ~all_po_filtered.apply(lambda r: (r["PO_No"],r["Item"]) in inv_keys, axis=1)
    ].copy()
    unfulfilled["Status"] = "🔴 Not supplied"
    unfulfilled["LeadTime"] = None
    unfulfilled["InvQty"] = 0
    unfulfilled["FillPct"] = 0.0

    filled = view.drop_duplicates(["PO_No","Item","Vendor"]).copy()
    filled["Status"] = filled.apply(
        lambda r: "🟢 Fully supplied" if r.get("InvQty",0)>=r["QtyOrdered"]
        else "🟡 Partially supplied", axis=1
    )
    filled["FillPct"] = (filled["InvQty"]/filled["QtyOrdered"].replace(0,1)*100).clip(upper=100)

    all_records = pd.concat([
        filled[["PO_No","PO_Date","Vendor","Item","QtyOrdered","InvQty","FillPct","LeadTime","Status"]],
        unfulfilled[["PO_No","PO_Date","Vendor","Item","QtyOrdered","InvQty","FillPct","LeadTime","Status"]],
    ], ignore_index=True).sort_values(["Status","PO_Date"], ascending=[True,False])

    all_records["Item"] = all_records["Item"].str.title()
    all_records["PO_Date"] = pd.to_datetime(all_records["PO_Date"], errors="coerce").dt.strftime("%d-%b-%Y")

    st.dataframe(all_records.rename(columns={
        "PO_No":"PO Number","PO_Date":"PO Date","QtyOrdered":"Ordered",
        "InvQty":"Invoiced","FillPct":"Fill %","LeadTime":"Lead Time (days)"
    }), use_container_width=True, hide_index=True,
    column_config={
        "Fill %": st.column_config.NumberColumn(format="%.1f%%"),
        "Lead Time (days)": st.column_config.NumberColumn(format="%.0f"),
    })


def _render_po_only(po: pd.DataFrame):
    st.markdown("#### Purchase Order Summary")
    k1, k2, k3 = st.columns(3)
    k1.metric("Total PO Value", f"₹{po['POValue'].sum():,.0f}")
    k2.metric("Total POs",      po["PO_No"].nunique())
    k3.metric("Vendors",        po["Vendor"].nunique())

    vendor_agg = (po.groupby("Vendor")
                  .agg(POs=("PO_No","nunique"), Value=("POValue","sum"), SKUs=("Item","nunique"))
                  .reset_index().sort_values("Value", ascending=False))
    st.dataframe(vendor_agg, use_container_width=True, hide_index=True,
                 column_config={"Value": st.column_config.NumberColumn("PO Value (₹)", format="₹%.0f")})
