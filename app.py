import streamlit as st
import sys
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date

# ── Path fix ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

st.set_page_config(
    page_title="Finance Command Centre",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
section[data-testid="stSidebar"] { background: #0f1117; border-right: 1px solid #1e2130; }
section[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
[data-testid="metric-container"] {
    background: #0d1117; border: 1px solid #21262d;
    border-radius: 10px; padding: 16px !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    color: #8b949e !important; font-size: 12px !important; letter-spacing: 0.5px;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #e6edf3 !important; font-size: 22px !important; font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stFileUploader"] {
    border: 1.5px dashed #30363d !important; border-radius: 10px;
    padding: 12px; background: #0d1117;
}
.stTabs [data-baseweb="tab-list"] { background: #0d1117; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #8b949e; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #1f6feb !important; color: #fff !important; }
[data-testid="stDataFrame"] { border: 1px solid #21262d; border-radius: 8px; }
hr { border-color: #21262d !important; }
[data-testid="stExpander"] { border: 1px solid #21262d !important; border-radius: 8px; background: #0d1117; }
.section-header {
    font-size: 11px; font-weight: 600; letter-spacing: 1.5px;
    color: #8b949e; text-transform: uppercase; margin: 16px 0 8px;
}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# STATE
# ════════════════════════════════════════════════════════════════════════════
from state import init_state
init_state()

# ════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ════════════════════════════════════════════════════════════════════════════
PT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
          font_color="#c9d1d9", margin=dict(t=30, b=30, l=10, r=10))

def _fcol(df, aliases):
    for a in aliases:
        for c in df.columns:
            if a.lower() in c.lower():
                return c
    return None

def _num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
from state import (store_invoice, store_wms, store_cust_bal, store_po,
                   store_bill_hdr, store_bill_lines, delete_dataset,
                   update_item_master, update_customer_registry, clear_caches)
from database import get_data_status, clear_all_data, delete_item

PAGES = ["Overview","Inventory","P&L","Working Capital","Receivables","Supplier Performance"]
PAGE_ICONS = {"Overview":"◈","Inventory":"📦","P&L":"📊",
              "Working Capital":"⚙️","Receivables":"💰","Supplier Performance":"🚚"}
DATASETS = {
    "📄 Invoice CSV":          ("invoice",    "df_invoice",    "P&L · Receivables · Working Capital"),
    "🏭 WMS / Inventory CSV":  ("wms",        "df_wms",        "Inventory · Working Capital (DIO)"),
    "👥 Customer Balance CSV": ("cust_bal",   "df_cust_bal",   "Receivables reconciliation · WC DSO"),
    "📦 Purchase Orders CSV":  ("po",         "df_po",         "Supplier Performance · WC (DPO)"),
    "🧾 Bill Header CSV":      ("bill_hdr",   "df_bill_hdr",   "Supplier Performance"),
    "🔖 Bill Lines CSV":       ("bill_lines", "df_bill_lines", "Supplier Performance (lead time)"),
}
STORE_FN = {"invoice": store_invoice, "wms": store_wms, "cust_bal": store_cust_bal,
            "po": store_po, "bill_hdr": store_bill_hdr, "bill_lines": store_bill_lines}

with st.sidebar:
    st.markdown("## 📊 Finance Command Centre")
    st.markdown("---")
    st.markdown('<p class="section-header">Navigation</p>', unsafe_allow_html=True)
    for p in PAGES:
        active = st.session_state.get("page") == p
        lbl = f"{'▶ ' if active else ''}{PAGE_ICONS[p]}  {p}"
        if st.button(lbl, key=f"nav_{p}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state["page"] = p
            st.rerun()

    st.markdown("---")
    st.markdown('<p class="section-header">📁 Upload Data</p>', unsafe_allow_html=True)
    db_status = get_data_status()

    for lbl, (db_key, sess_key, hint) in DATASETS.items():
        info = db_status.get(db_key)
        badge = f" 🟢 {info['row_count']:,} rows" if info else ""
        with st.expander(f"{lbl}{badge}", expanded=False):
            st.caption(hint)
            f = st.file_uploader(lbl, type="csv", key=f"up_{db_key}", label_visibility="collapsed")
            if f:
                try:
                    df = pd.read_csv(f)
                    STORE_FN[db_key](df)
                    st.success(f"✅ {len(df):,} rows saved")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if info:
                if st.button("🗑️ Remove", key=f"del_{db_key}", use_container_width=True):
                    delete_dataset(db_key, sess_key)
                    st.rerun()

    st.markdown("---")
    st.markdown('<p class="section-header">☁️ Database Status</p>', unsafe_allow_html=True)
    if db_status:
        for dk, info in db_status.items():
            n = next((l.split(" ",1)[1].strip() for l,(k,_,__) in DATASETS.items() if k==dk), dk)
            ts = info["uploaded_at"].strftime("%d %b %H:%M") if info.get("uploaded_at") else "—"
            st.markdown(f"🟢 **{n}** — {info['row_count']:,} rows · _{ts}_")
    else:
        st.markdown("⚪ No data yet")

    st.markdown("---")
    # Item Master
    with st.expander("⚙️ Item Master", expanded=False):
        im = st.session_state.get("item_master", {})
        with st.form("im_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            sku  = c1.text_input("SKU"); name = c2.text_input("Name")
            c3, c4, c5 = st.columns(3)
            cogs = c3.number_input("COGS ₹", min_value=0.0, step=0.5, format="%.2f")
            dw   = c4.number_input("Dead wt", min_value=0.0, step=0.01, value=0.5, format="%.3f")
            vw   = c5.number_input("Vol wt",  min_value=0.0, step=0.01, value=0.5, format="%.3f")
            if st.form_submit_button("💾 Save", use_container_width=True):
                if sku:
                    im[sku] = {"name": name, "cogs": cogs, "dead_weight": dw, "vol_weight": vw}
                    update_item_master(im)
                    st.success(f"Saved {sku}")
        if im:
            df_im = pd.DataFrame(im).T.reset_index().rename(columns={"index":"SKU"})
            st.dataframe(df_im[["SKU","name","cogs"]].rename(columns={"name":"Name","cogs":"COGS"}),
                         hide_index=True, use_container_width=True, height=180)
            sel = st.selectbox("Delete SKU", ["—"]+list(im.keys()), key="del_sku_sel")
            if sel != "—" and st.button(f"🗑️ Delete {sel}", key="del_sku_btn"):
                im.pop(sel, None); delete_item(sel)
                st.session_state["item_master"] = im; st.rerun()

    # Customer Registry
    with st.expander("👥 Customer Registry", expanded=False):
        reg = st.session_state.get("customers", {})
        if not reg:
            st.info("Upload Invoice CSV to auto-populate.")
        else:
            df_reg = pd.DataFrame(reg).T.reset_index().rename(columns={"index":"customer"})
            for c in ["type","channel","credit_days","is_marketplace"]:
                if c not in df_reg.columns:
                    df_reg[c] = "" if c in ["type","channel"] else (30 if c=="credit_days" else False)
            edited = st.data_editor(df_reg[["customer","type","channel","credit_days","is_marketplace"]],
                hide_index=True, use_container_width=True, height=220,
                column_config={
                    "customer": st.column_config.TextColumn(disabled=True),
                    "type": st.column_config.SelectboxColumn(options=["B2B","B2C"]),
                    "credit_days": st.column_config.NumberColumn(min_value=0, max_value=365),
                    "is_marketplace": st.column_config.CheckboxColumn("Own Pickup"),
                }, key="cust_edit")
            if st.button("💾 Save", key="save_cust", use_container_width=True):
                new_reg = {r["customer"]: {"type":r["type"],"channel":r["channel"],
                           "credit_days":int(r["credit_days"]),"is_marketplace":bool(r["is_marketplace"])}
                           for _,r in edited.iterrows()}
                update_customer_registry(new_reg); st.success("Saved")

    st.markdown("---")
    with st.expander("⚠️ Danger Zone", expanded=False):
        if st.button("🗑️ Clear ALL uploaded data", use_container_width=True, type="primary"):
            clear_all_data()
            for k in ["df_invoice","df_wms","df_cust_bal","df_po","df_bill_hdr","df_bill_lines"]:
                st.session_state[k] = None
            clear_caches(); st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# TAB: OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
def render_overview():
    st.title("📊 Finance Command Centre")
    st.caption(f"Last refreshed: {date.today().strftime('%d %b %Y')}")
    inv_df = st.session_state["df_invoice"]
    wms_df = st.session_state["df_wms"]
    im     = st.session_state["item_master"]
    customers = st.session_state["customers"]

    if not any(x is not None for x in [inv_df, wms_df]):
        st.markdown("---")
        st.info("👈 Upload your CSV files from the sidebar to get started.")
        st.markdown("""
| Upload | Powers |
|---|---|
| **Invoice CSV** | P&L · Receivables · Working Capital (DSO) |
| **WMS / Inventory CSV** | Inventory snapshots · Working Capital (DIO) |
| **Customer Balance CSV** | Receivables reconciliation · Working Capital |
| **PO + Bill CSVs** | Supplier performance · Working Capital (DPO) |
        """)
        st.markdown("#### Expected CSV columns")
        c1,c2 = st.columns(2)
        c1.markdown("**Invoice CSV:** `Invoice Number`, `Invoice Date`, `Customer Name`, `SKU`, `Item Name`, `Quantity`, `Item Total`, `Balance`, `Place of Supply`")
        c2.markdown("**WMS CSV:** `Title`/`SKU`, `Total Stock`/`Qty`, `Mfg Date`, `Shelf Life`, `Channel` *(optional)*, `Value` *(optional)*")
        return

    st.markdown("### Key Performance Indicators")
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    revenue = _num(inv_df["Item Total"]).sum() if inv_df is not None and "Item Total" in (inv_df.columns if inv_df is not None else []) else 0
    cogs = 0
    if inv_df is not None and im:
        im_sku = {k: v.get("cogs",0) for k,v in im.items()}
        sku_c = _fcol(inv_df, ["sku","item code"])
        qty_c = _fcol(inv_df, ["quantity","qty"])
        if sku_c and qty_c:
            cogs = (inv_df.apply(lambda r: _num(pd.Series([r[qty_c]]))[0] * im_sku.get(str(r[sku_c]),0), axis=1).sum())
    gm_pct = (revenue-cogs)/revenue*100 if revenue > 0 else 0
    inv_val = 0
    if wms_df is not None:
        vc = _fcol(wms_df, ["value","val"])
        if vc: inv_val = _num(wms_df[vc]).sum()
    recv = 0
    if inv_df is not None:
        bc = _fcol(inv_df, ["balance","outstanding"])
        if bc: recv = _num(inv_df[bc]).sum()
    skus = inv_df[_fcol(inv_df,["sku","item"])].nunique() if inv_df is not None and _fcol(inv_df,["sku","item"]) else 0

    c1.metric("Revenue",        f"₹{revenue/1e5:.1f}L" if revenue>=1e5 else f"₹{revenue:,.0f}")
    c2.metric("COGS",           f"₹{cogs/1e5:.1f}L" if cogs>=1e5 else f"₹{cogs:,.0f}")
    c3.metric("Gross Margin",   f"{gm_pct:.1f}%")
    c4.metric("Inventory Value",f"₹{inv_val/1e5:.1f}L" if inv_val>=1e5 else f"₹{inv_val:,.0f}")
    c5.metric("Receivables",    f"₹{recv/1e5:.1f}L" if recv>=1e5 else f"₹{recv:,.0f}")
    c6.metric("Active SKUs",    skus)

    st.divider()
    cl, cr = st.columns(2)
    with cl:
        st.markdown("#### P&L Waterfall")
        if revenue > 0:
            ship = cogs * 0.12
            fig = go.Figure(go.Waterfall(
                x=["Revenue","COGS","Gross Margin","Logistics","CM1"],
                y=[revenue,-cogs,0,-ship,0],
                measure=["absolute","relative","total","relative","total"],
                decreasing={"marker":{"color":"#f85149"}},
                increasing={"marker":{"color":"#3fb950"}},
                totals={"marker":{"color":"#1f6feb"}},
                connector={"line":{"color":"#30363d","width":1}},
            ))
            fig.update_layout(**PT, height=300, yaxis=dict(gridcolor="#21262d",tickprefix="₹"), xaxis=dict(gridcolor="#21262d"))
            st.plotly_chart(fig, use_container_width=True)
    with cr:
        st.markdown("#### Jump to Module")
        for pg, desc in [("Inventory","Stock · ageing · shelf life"),("P&L","Revenue → COGS → margins"),
                         ("Working Capital","DSO · DIO · DPO · CCC"),("Receivables","Overdue aging · FIFO"),
                         ("Supplier Performance","Lead time · fill rate")]:
            if st.button(f"{PAGE_ICONS[pg]} {pg}", key=f"jump_{pg}", use_container_width=True):
                st.session_state["page"] = pg; st.rerun()
            st.caption(desc)

# ════════════════════════════════════════════════════════════════════════════
# TAB: INVENTORY
# ════════════════════════════════════════════════════════════════════════════
BUCKET_COLORS = {">80% shelf life":"#3fb950","60-80% shelf life":"#1f6feb",
                 "40-60% shelf life":"#d29922","<40% shelf life":"#f85149"}

def _prep_wms(df, im):
    df = df.copy()
    rn = {}
    for c in df.columns:
        cl = c.lower()
        if any(x in cl for x in ["title","name","product"]) and "Title" not in rn.values(): rn[c]="Title"
        elif "sku" in cl and "SKU" not in rn.values(): rn[c]="SKU"
        elif any(x in cl for x in ["stock","qty","quantity"]) and "Stock" not in rn.values(): rn[c]="Stock"
        elif "channel" in cl and "Channel" not in rn.values(): rn[c]="Channel"
        elif "shelf" in cl and "ShelfLife" not in rn.values(): rn[c]="ShelfLife"
        elif "mfg" in cl and "MfgDate" not in rn.values(): rn[c]="MfgDate"
        elif "value" in cl and "Value" not in rn.values(): rn[c]="Value"
    df = df.rename(columns=rn)
    for col in ["Title","SKU","Channel","ShelfLife","MfgDate"]:
        if col not in df.columns: df[col]=""
    for col in ["Stock","Value"]:
        if col not in df.columns: df[col]=0.0
        else: df[col]=_num(df[col])
    df["ShelfPct"] = _num(df["ShelfLife"].astype(str).str.replace("%","",regex=False))
    def bkt(p):
        if p>80: return ">80% shelf life"
        if p>=60: return "60-80% shelf life"
        if p>=40: return "40-60% shelf life"
        return "<40% shelf life"
    df["AgeingBucket"] = df["ShelfPct"].apply(bkt)
    df["MfgDate_dt"] = pd.to_datetime(df["MfgDate"], dayfirst=True, errors="coerce")
    im_name = {v.get("name","").lower(): v.get("cogs",0) for v in im.values()}
    im_sku  = {k: v.get("cogs",0) for k,v in im.items()}
    df["CostPrice"] = df.apply(lambda r: im_sku.get(str(r["SKU"]), im_name.get(str(r["Title"]).lower(),0)), axis=1)
    df["Valuation"] = df["Stock"] * df["CostPrice"]
    return df

def render_inventory():
    st.title("📦 Inventory Snapshot")
    wms_df = st.session_state["df_wms"]
    im     = st.session_state["item_master"]
    if wms_df is None:
        st.info("👈 Upload a **WMS / Inventory CSV** from the sidebar.")
        return
    df = _prep_wms(wms_df, im)
    with st.expander("🔍 Filters", expanded=True):
        fc1,fc2,fc3 = st.columns(3)
        ch_f  = fc1.selectbox("Channel", ["All"]+sorted(df["Channel"].dropna().unique().tolist()))
        itf   = fc2.multiselect("Products", sorted(df["Title"].dropna().unique().tolist()), placeholder="All")
        mode  = fc3.radio("View by", ["Quantity","Value (₹)"], horizontal=True)
    dff = df.copy()
    if ch_f != "All": dff = dff[dff["Channel"]==ch_f]
    if itf: dff = dff[dff["Title"].isin(itf)]
    mcol = "Stock" if mode=="Quantity" else "Valuation"
    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Total Stock",     f"{dff['Stock'].sum():,.0f} units")
    k2.metric("Inventory Value", f"₹{dff['Valuation'].sum():,.0f}")
    k3.metric("Active SKUs",     dff["Title"].nunique())
    k4.metric("Avg Shelf Life",  f"{dff['ShelfPct'].mean():.1f}%")
    k5.metric("At-Risk (<40%)",  f"{dff[dff['AgeingBucket']=='<40% shelf life']['Stock'].sum():,.0f}")
    st.divider()
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("#### Item-wise breakdown")
        isum = dff.groupby(["Title","Channel"])[mcol].sum().reset_index().sort_values(mcol)
        fig = px.bar(isum, x=mcol, y="Title", color="Channel", orientation="h",
                     color_discrete_map={"B2B":"#1f6feb","B2C":"#3fb950"}, barmode="stack",
                     height=max(320, len(isum)*22))
        fig.update_layout(**PT, yaxis_title="", legend=dict(orientation="h",y=-0.1))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("#### Ageing distribution")
        ag = dff.groupby("AgeingBucket")[mcol].sum().reset_index()
        fig2 = go.Figure(go.Pie(labels=ag["AgeingBucket"], values=ag[mcol], hole=0.55,
            textinfo="label+percent",
            marker_colors=[BUCKET_COLORS.get(b,"#8b949e") for b in ag["AgeingBucket"]]))
        fig2.update_layout(**PT, height=320, showlegend=True, legend=dict(orientation="h",y=-0.15))
        st.plotly_chart(fig2, use_container_width=True)
    if dff["MfgDate_dt"].notna().any():
        st.markdown("#### Stock by manufacture batch")
        md = dff.dropna(subset=["MfgDate_dt"]).groupby("MfgDate_dt")[mcol].sum().reset_index().sort_values("MfgDate_dt")
        md["Lbl"] = md["MfgDate_dt"].dt.strftime("%b %Y")
        fig3 = px.bar(md, x="Lbl", y=mcol, color_discrete_sequence=["#1f6feb"])
        fig3.update_layout(**PT, xaxis_title="Manufacture batch", yaxis_title=mode)
        st.plotly_chart(fig3, use_container_width=True)
    st.divider()
    st.markdown("#### Detailed records")
    disp = dff[["Channel","Title","SKU","Stock","ShelfPct","AgeingBucket","CostPrice","Valuation"]].copy()
    disp.columns = ["Channel","Product","SKU","Stock","Shelf Life %","Ageing","Cost (₹)","Value (₹)"]
    st.dataframe(disp.sort_values("Value (₹)", ascending=False), use_container_width=True, hide_index=True,
        column_config={"Shelf Life %": st.column_config.ProgressColumn(min_value=0, max_value=100),
                       "Value (₹)": st.column_config.NumberColumn(format="₹%.0f"),
                       "Cost (₹)":  st.column_config.NumberColumn(format="₹%.2f")})

# ════════════════════════════════════════════════════════════════════════════
# TAB: P&L
# ════════════════════════════════════════════════════════════════════════════
DEFAULT_LOG = {"B2B":35.0,"B2C":50.0,"Marketplace":0.0,"D2C":55.0,"Unknown":50.0}

def _prep_inv(df, im, customers):
    df = df.copy()
    rn = {}
    for c in df.columns:
        cl = c.lower()
        if "item name" in cl and "Item Name" not in rn.values(): rn[c]="Item Name"
        elif "sku" in cl and "SKU" not in rn.values(): rn[c]="SKU"
        elif "customer name" in cl and "Customer Name" not in rn.values(): rn[c]="Customer Name"
        elif "invoice date" in cl and "Invoice Date" not in rn.values(): rn[c]="Invoice Date"
        elif "invoice number" in cl and "Invoice Number" not in rn.values(): rn[c]="Invoice Number"
        elif "item total" in cl and "Item Total" not in rn.values(): rn[c]="Item Total"
        elif "quantity" in cl and "Quantity" not in rn.values(): rn[c]="Quantity"
        elif "balance" in cl and "Balance" not in rn.values(): rn[c]="Balance"
    df = df.rename(columns=rn)
    for c in ["Item Name","SKU","Customer Name","Invoice Number"]:
        if c not in df.columns: df[c]=""
    for c in ["Item Total","Quantity","Balance"]:
        if c not in df.columns: df[c]=0.0
        else: df[c]=_num(df[c])
    df["Invoice Date"] = pd.to_datetime(df.get("Invoice Date",""), dayfirst=True, errors="coerce")
    df["Channel"] = df["Customer Name"].apply(lambda n: customers.get(str(n),{}).get("channel","Unknown"))
    im_name = {v.get("name","").lower(): v.get("cogs",0) for v in im.values()}
    im_sku  = {k: v.get("cogs",0) for k,v in im.items()}
    df["UnitCOGS"] = df.apply(lambda r: im_sku.get(str(r["SKU"]), im_name.get(str(r["Item Name"]).lower(),0)), axis=1)
    df["COGS"] = df["UnitCOGS"] * df["Quantity"]
    return df

def render_pnl():
    st.title("📊 Profit & Loss")
    inv_df = st.session_state["df_invoice"]
    im     = st.session_state["item_master"]
    customers = st.session_state["customers"]
    if inv_df is None:
        st.info("👈 Upload an **Invoice CSV** from the sidebar."); return
    df = _prep_inv(inv_df, im, customers)
    with st.expander("🔍 Filters", expanded=True):
        fc1,fc2,fc3,fc4 = st.columns(4)
        ch_f  = fc1.selectbox("Channel", ["All"]+sorted(df["Channel"].dropna().unique().tolist()))
        pf    = fc2.selectbox("Product", ["All"]+sorted(df["Item Name"].dropna().unique().tolist())[:80])
        min_d = df["Invoice Date"].min(); max_d = df["Invoice Date"].max()
        def_from = (max_d - timedelta(days=90)) if pd.notna(max_d) else datetime(2025,1,1)
        d_from = fc3.date_input("From", value=def_from.date() if pd.notna(def_from) else None)
        d_to   = fc4.date_input("To",   value=max_d.date() if pd.notna(max_d) else None)
    with st.expander("⚙️ Logistics cost settings", expanded=False):
        lc1,lc2,lc3 = st.columns(3)
        lb2b = lc1.number_input("B2B ₹/unit", value=35.0, step=1.0)
        lb2c = lc2.number_input("B2C ₹/unit", value=50.0, step=1.0)
        lmkt = lc3.number_input("Marketplace ₹/unit", value=0.0, step=1.0)
    log_r = {"B2B":lb2b,"B2C":lb2c,"Marketplace":lmkt,"D2C":lb2c,"Unknown":lb2c}
    dff = df.copy()
    if ch_f != "All": dff = dff[dff["Channel"]==ch_f]
    if pf  != "All":  dff = dff[dff["Item Name"]==pf]
    if d_from and d_to:
        dff = dff[(dff["Invoice Date"].dt.date>=d_from)&(dff["Invoice Date"].dt.date<=d_to)]
    if dff.empty: st.warning("No data for selected filters."); return
    revenue  = dff["Item Total"].sum()
    cogs     = dff["COGS"].sum()
    dff["LogCost"] = dff["Quantity"] * dff["Channel"].map(lambda c: log_r.get(c,lb2c))
    logistics = dff["LogCost"].sum()
    gm = revenue-cogs; cm1 = gm-logistics
    gm_pct = gm/revenue*100 if revenue else 0
    cm1_pct= cm1/revenue*100 if revenue else 0
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Revenue",        f"₹{revenue:,.0f}")
    k2.metric("COGS",           f"₹{cogs:,.0f}", delta=f"{cogs/revenue*100:.1f}% of rev" if revenue else "")
    k3.metric("Gross Margin",   f"₹{gm:,.0f}", delta=f"{gm_pct:.1f}%")
    k4.metric("Logistics Cost", f"₹{logistics:,.0f}")
    k5.metric("CM1",            f"₹{cm1:,.0f}", delta=f"{cm1_pct:.1f}%")
    k6.metric("Orders",         f"{dff['Invoice Number'].nunique():,}")
    st.divider()
    st.markdown("#### P&L Statement")
    pl_rows = [
        {"Line Item":"Revenue (Net Sales)",      "Amount (₹)":revenue,   "% of Revenue":100.0},
        {"Line Item":"Cost of Goods Sold",       "Amount (₹)":-cogs,     "% of Revenue":cogs/revenue*100 if revenue else 0},
        {"Line Item":"─── Gross Margin",         "Amount (₹)":gm,        "% of Revenue":gm_pct},
        {"Line Item":"Logistics Cost",           "Amount (₹)":-logistics, "% of Revenue":logistics/revenue*100 if revenue else 0},
        {"Line Item":"─── Contribution Margin 1","Amount (₹)":cm1,       "% of Revenue":cm1_pct},
    ]
    st.dataframe(pd.DataFrame(pl_rows), hide_index=True, use_container_width=True,
        column_config={"Amount (₹)":st.column_config.NumberColumn(format="₹%.0f"),
                       "% of Revenue":st.column_config.NumberColumn(format="%.1f%%")})
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("#### Waterfall")
        fig = go.Figure(go.Waterfall(
            x=["Revenue","COGS","Gross Margin","Logistics","CM1"],
            y=[revenue,-cogs,0,-logistics,0],
            measure=["absolute","relative","total","relative","total"],
            decreasing={"marker":{"color":"#f85149"}},
            increasing={"marker":{"color":"#3fb950"}},
            totals={"marker":{"color":"#1f6feb"}},
            connector={"line":{"color":"#30363d","width":1}},
        ))
        fig.update_layout(**PT, height=320, yaxis=dict(gridcolor="#21262d",tickprefix="₹"), xaxis=dict(gridcolor="#21262d"))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("#### Revenue vs COGS by Channel")
        ca = dff.groupby("Channel").agg(Revenue=("Item Total","sum"),COGS=("COGS","sum"),Logistics=("LogCost","sum")).reset_index()
        fig2 = go.Figure()
        for col,color in [("Revenue","#1f6feb"),("COGS","#f85149"),("Logistics","#d29922")]:
            fig2.add_trace(go.Bar(name=col, x=ca["Channel"], y=ca[col], marker_color=color))
        fig2.update_layout(**PT, barmode="group", height=320,
                           yaxis=dict(gridcolor="#21262d",tickprefix="₹"), xaxis=dict(gridcolor="#21262d"),
                           legend=dict(orientation="h",y=-0.15))
        st.plotly_chart(fig2, use_container_width=True)
    if cogs > 0:
        st.markdown("#### Product-level P&L")
        pc = dff.groupby("Item Name").agg(Revenue=("Item Total","sum"),COGS=("COGS","sum"),Qty=("Quantity","sum")).reset_index()
        pc["GM"] = pc["Revenue"]-pc["COGS"]
        pc["GM %"] = (pc["GM"]/pc["Revenue"].replace(0,1)*100).map(lambda x: f"{x:.1f}%")
        pc = pc.sort_values("Revenue",ascending=False)
        st.dataframe(pc.rename(columns={"Item Name":"Product","Revenue":"Revenue (₹)","COGS":"COGS (₹)","GM":"Gross Margin (₹)"}),
                     use_container_width=True, hide_index=True,
                     column_config={"Revenue (₹)":st.column_config.NumberColumn(format="₹%.0f"),
                                    "COGS (₹)":st.column_config.NumberColumn(format="₹%.0f"),
                                    "Gross Margin (₹)":st.column_config.NumberColumn(format="₹%.0f")})
    else:
        st.info("Add COGS in **Item Master** (sidebar) to see product-level margins.")

# ════════════════════════════════════════════════════════════════════════════
# TAB: WORKING CAPITAL
# ════════════════════════════════════════════════════════════════════════════
def render_working_capital():
    st.title("⚙️ Working Capital")
    inv_df  = st.session_state["df_invoice"]
    wms_df  = st.session_state["df_wms"]
    cbal_df = st.session_state["df_cust_bal"]
    po_df   = st.session_state["df_po"]
    bill_hdr= st.session_state["df_bill_hdr"]
    im      = st.session_state["item_master"]

    ca,cb = st.columns(2)
    period_start = ca.date_input("Period start", value=datetime(2025,4,1).date())
    period_end   = cb.date_input("Period end",   value=datetime(2026,3,31).date())
    days = max((period_end-period_start).days, 1)

    t1,t2,t3 = st.columns(3)
    t_dso = t1.number_input("Target DSO (days)", value=60, min_value=1)
    t_dio = t2.number_input("Target DIO (days)", value=45, min_value=1)
    t_dpo = t3.number_input("Target DPO (days)", value=45, min_value=1)
    st.divider()

    dso=dio=dpo=None
    # DSO
    if cbal_df is not None:
        bc = _fcol(cbal_df,["closing_balance","balance"]); ic = _fcol(cbal_df,["invoiced","billed","sales"])
        if bc and ic:
            tb=_num(cbal_df[bc]).sum(); ti=_num(cbal_df[ic]).sum()
            if ti>0: dso=(tb/ti)*days
    elif inv_df is not None:
        bc=_fcol(inv_df,["balance"]); tc=_fcol(inv_df,["item total","total"])
        if bc and tc:
            tb=_num(inv_df[bc]).sum(); ti=_num(inv_df[tc]).sum()
            if ti>0: dso=(tb/ti)*days
    # DIO
    if wms_df is not None:
        vc=_fcol(wms_df,["value"]); iv=_num(wms_df[vc]).sum() if vc else 0
        if iv>0 and inv_df is not None and im:
            im_sku={k:v.get("cogs",0) for k,v in im.items()}
            sc=_fcol(inv_df,["sku"]); qc=_fcol(inv_df,["quantity","qty"])
            if sc and qc:
                ct=inv_df.apply(lambda r: _num(pd.Series([r[qc]]))[0]*im_sku.get(str(r[sc]),0),axis=1).sum()
                if ct>0: dio=(iv/ct)*days
    # DPO
    if bill_hdr is not None and po_df is not None:
        payc=_fcol(bill_hdr,["balance","bcy_balance","amount"]); potc=_fcol(po_df,["item total","total","amount"])
        if payc and potc:
            tp=_num(bill_hdr[payc]).sum(); tpu=_num(po_df[potc]).sum()
            if tpu>0: dpo=(tp/tpu)*days

    ccc = dso+dio-dpo if all(x is not None for x in [dso,dio,dpo]) else None

    def gauge(title, val, target, maxv, color):
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=val if val else 0,
            delta={"reference":target,"valueformat":".1f","suffix":"d"},
            title={"text":title,"font":{"color":"#c9d1d9","size":13}},
            number={"suffix":" days","font":{"color":"#e6edf3","size":22}},
            gauge={"axis":{"range":[0,maxv],"tickcolor":"#8b949e"},
                   "bar":{"color":color},"bgcolor":"#0d1117","bordercolor":"#21262d",
                   "threshold":{"line":{"color":"#f85149","width":2},"value":target},
                   "steps":[{"range":[0,target*0.8],"color":"#0d2a1f"},
                             {"range":[target*0.8,target],"color":"#1a3520"},
                             {"range":[target,maxv],"color":"#2a0f0f"}]}
        ))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",font_color="#c9d1d9",
                          height=220,margin=dict(t=40,b=20,l=20,r=20))
        return fig

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("DSO", f"{dso:.1f}d" if dso else "N/A", delta=f"{dso-t_dso:+.1f}d vs target" if dso else None, delta_color="inverse")
    k2.metric("DIO", f"{dio:.1f}d" if dio else "N/A", delta=f"{dio-t_dio:+.1f}d vs target" if dio else None, delta_color="inverse")
    k3.metric("DPO", f"{dpo:.1f}d" if dpo else "N/A", delta=f"{dpo-t_dpo:+.1f}d vs target" if dpo else None)
    k4.metric("Cash Cycle", f"{ccc:.1f}d" if ccc else "N/A (upload all files)")
    st.divider()

    g1,g2,g3 = st.columns(3)
    with g1:
        if dso: st.plotly_chart(gauge("DSO",dso,t_dso,max(t_dso*2.5,150),"#1f6feb"),use_container_width=True)
        else: st.info("Upload Invoice CSV + Customer Balance CSV for DSO.")
    with g2:
        if dio: st.plotly_chart(gauge("DIO",dio,t_dio,max(t_dio*2.5,120),"#3fb950"),use_container_width=True)
        else: st.info("Upload WMS CSV + Invoice CSV + Item Master for DIO.")
    with g3:
        if dpo: st.plotly_chart(gauge("DPO",dpo,t_dpo,max(t_dpo*2.5,180),"#d29922"),use_container_width=True)
        else: st.info("Upload PO CSV + Bill Header CSV for DPO.")

    if ccc is not None:
        st.markdown("#### Cash Conversion Cycle breakdown")
        fig = go.Figure()
        for lbl,val,color,desc in [("DSO",dso,"#1f6feb","Receivables"),
                                    ("DIO",dio,"#3fb950","Inventory"),
                                    ("DPO (-)",-dpo,"#d29922","Payables offset")]:
            fig.add_trace(go.Bar(name=f"{lbl}: {val:.1f}d",x=[val],y=[desc],
                                 orientation="h",marker_color=color,
                                 text=f"{abs(val):.1f} days",textposition="auto"))
        fig.add_vline(x=0,line_color="#8b949e",line_width=1)
        fig.update_layout(**PT,barmode="relative",height=200,
                          xaxis_title="Days",legend=dict(orientation="h",y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    if cbal_df is not None:
        st.markdown("#### Top debtors")
        cn=_fcol(cbal_df,["customer_name","customer","name"])
        bc=_fcol(cbal_df,["closing_balance","balance"])
        if cn and bc:
            top=cbal_df.assign(bal=_num(cbal_df[bc])).sort_values("bal",ascending=False).head(15)
            fig2=px.bar(top,x=cn,y="bal",color="bal",color_continuous_scale="RdYlGn_r")
            fig2.update_layout(**PT,height=300,yaxis=dict(gridcolor="#21262d",tickprefix="₹"),
                               xaxis=dict(gridcolor="#21262d",tickangle=-35))
            st.plotly_chart(fig2,use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB: RECEIVABLES
# ════════════════════════════════════════════════════════════════════════════
POS_DELAY = {'MH':2,'GJ':3,'GA':3,'KA':5,'TN':5,'KL':6,'TS':5,'AP':5,
             'DL':5,'HR':5,'PB':5,'UP':6,'RJ':4,'WB':7,'OR':7,'JH':7,'BH':7,'AS':10,'MN':12}

def render_receivables():
    st.title("💰 Receivables")
    inv_df  = st.session_state["df_invoice"]
    cbal_df = st.session_state["df_cust_bal"]
    if inv_df is None:
        st.info("👈 Upload an **Invoice CSV** from the sidebar."); return

    credit_days = st.sidebar.number_input("Default credit days", value=30, min_value=0, max_value=365)
    df = inv_df.copy()

    # normalise columns
    for alias,target in [([" invoice number","invoice no"],"_inv_no"),
                          (["customer name","customer"],"_cust"),
                          (["balance","outstanding"],"_balance"),
                          (["place of supply","state"],"_pos"),
                          (["invoice status","status"],"_status"),
                          (["gst treatment"],"_gst"),
                          (["invoice date","date"],"_date")]:
        col = _fcol(df, alias if isinstance(alias,list) else [alias])
        df[target] = df[col] if col else ("" if target != "_balance" else 0)
    df["_balance"] = _num(df["_balance"])
    df["_date"]    = pd.to_datetime(df["_date"], dayfirst=True, errors="coerce")

    b2b = df["_gst"].astype(str).str.lower().str.contains("business", na=False)
    if b2b.sum() > 0: df = df[b2b].copy()

    def state_code(s):
        s = str(s).strip().upper()
        return s.split("-")[0].strip()[:2] if "-" in s else s[:2]

    df["TransitDays"] = df["_pos"].apply(lambda s: POS_DELAY.get(state_code(s),5))
    df["GRNDate"]     = df["_date"] + pd.to_timedelta(df["TransitDays"],unit="D")
    df["TrueDueDate"] = df["GRNDate"] + pd.to_timedelta(credit_days,unit="D")

    # FIFO
    if cbal_df is not None:
        cn=_fcol(cbal_df,["customer_name","customer","name"])
        bc=_fcol(cbal_df,["closing_balance","balance"])
        if cn and bc:
            ledger=dict(zip(cbal_df[cn].astype(str),_num(cbal_df[bc])))
            rows=[]
            for cust,grp in df.groupby("_cust"):
                grp=grp.sort_values("_date"); rem=ledger.get(str(cust),grp["_balance"].sum())
                for _,row in grp.iterrows():
                    if rem<=0: row["EffBal"]=0.0
                    elif rem>=row["_balance"]: row["EffBal"]=float(row["_balance"]); rem-=row["_balance"]
                    else: row["EffBal"]=float(rem); rem=0
                    rows.append(row)
            df=pd.DataFrame(rows)
        else: df["EffBal"]=df["_balance"]
    else: df["EffBal"]=df["_balance"]

    today=pd.Timestamp(date.today())
    df["AgingDays"]=(today-df["TrueDueDate"]).dt.days

    with st.expander("🔍 Filters",expanded=True):
        fc1,fc2=st.columns(2)
        sel=fc1.multiselect("Customer",sorted(df["_cust"].dropna().unique()),placeholder="All")
        srch=fc2.text_input("Search invoice","")
    dff=df.copy()
    if sel:  dff=dff[dff["_cust"].isin(sel)]
    if srch: dff=dff[dff["_inv_no"].astype(str).str.contains(srch,case=False,na=False)]
    om=(dff["EffBal"]>0)&(dff["AgingDays"]>0)
    k1,k2,k3,k4=st.columns(4)
    k1.metric("Total Receivables", f"₹{dff['EffBal'].sum():,.0f}")
    k2.metric("Overdue Amount",    f"₹{dff[om]['EffBal'].sum():,.0f}")
    k3.metric("Avg Aging (overdue)",f"{int(dff[om]['AgingDays'].mean()) if om.any() else 0} days")
    k4.metric("Customers",         dff["_cust"].nunique())
    st.divider()
    st.markdown("#### Customer-wise summary")
    cs=[]
    for c in dff["_cust"].unique():
        cd=dff[dff["_cust"]==c]; cm=(cd["EffBal"]>0)&(cd["AgingDays"]>0)
        cs.append({"Customer":c,"Total Balance":cd["EffBal"].sum(),"Overdue":cd[cm]["EffBal"].sum(),
                   "Avg Aging":int(cd[cm]["AgingDays"].mean()) if cm.any() else 0,"Invoices":len(cd)})
    st.dataframe(pd.DataFrame(cs).sort_values("Overdue",ascending=False),
                 use_container_width=True,hide_index=True,
                 column_config={"Total Balance":st.column_config.NumberColumn(format="₹%.0f"),
                                "Overdue":st.column_config.NumberColumn(format="₹%.0f")})
    st.divider()
    st.markdown("#### Ageing buckets")
    bins=[-9999,0,15,30,60,9999]; labels=["Current","1–15d","16–30d","31–60d",">60d"]
    colors=["#3fb950","#58a6ff","#d29922","#f85149","#da3633"]
    dff["Bucket"]=pd.cut(dff["AgingDays"],bins=bins,labels=labels,right=True)
    bd=dff[dff["EffBal"]>0].groupby("Bucket",observed=False)["EffBal"].sum().reindex(labels).fillna(0)
    c1,c2=st.columns(2)
    with c1:
        fig=go.Figure(go.Bar(x=bd.index.tolist(),y=bd.values,marker_color=colors,
            text=[f"₹{v/1e3:.0f}K" if v>=1000 else f"₹{v:.0f}" for v in bd.values],textposition="outside"))
        fig.update_layout(**PT,height=280,yaxis=dict(gridcolor="#21262d",tickprefix="₹"),xaxis=dict(gridcolor="#21262d"))
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        fig2=go.Figure(go.Pie(labels=bd.index.tolist(),values=bd.values,hole=0.55,marker_colors=colors,textinfo="label+percent"))
        fig2.update_layout(**PT,height=280,showlegend=False)
        st.plotly_chart(fig2,use_container_width=True)
    st.divider()
    def flag(r):
        if r["EffBal"]<=0: return "✅ Settled"
        if r["AgingDays"]<=0: return "🟢 Current"
        if r["AgingDays"]<=15: return "🟡 1–15d"
        if r["AgingDays"]<=30: return "🟠 16–30d"
        if r["AgingDays"]<=60: return "🔴 31–60d"
        return "💀 >60d"
    dff["Status"]=dff.apply(flag,axis=1)
    od=dff[dff["EffBal"]>0][["Status","_inv_no","_cust","_date","GRNDate","TrueDueDate","_balance","EffBal","AgingDays"]].copy()
    od.columns=["Status","Invoice #","Customer","Invoice Date","GRN Date","Due Date","Balance","Effective Balance","Aging Days"]
    for dc in ["Invoice Date","GRN Date","Due Date"]:
        od[dc]=pd.to_datetime(od[dc],errors="coerce").dt.strftime("%d-%b-%Y")
    st.dataframe(od.sort_values("Aging Days",ascending=False),use_container_width=True,hide_index=True,
                 column_config={"Balance":st.column_config.NumberColumn(format="₹%.0f"),
                                "Effective Balance":st.column_config.NumberColumn(format="₹%.0f")})
    csv=od.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download aging report",csv,f"receivables_aging_{date.today()}.csv","text/csv")

# ════════════════════════════════════════════════════════════════════════════
# TAB: SUPPLIER PERFORMANCE
# ════════════════════════════════════════════════════════════════════════════
def _prep_po(df):
    df=df.copy(); rn={}
    for c in df.columns:
        cl=c.lower()
        if "purchase order number" in cl or "po number" in cl: rn[c]="PO_No"
        elif "purchase order date" in cl or "po date" in cl: rn[c]="PO_Date"
        elif "vendor name" in cl or "supplier" in cl: rn[c]="Vendor"
        elif "item name" in cl: rn[c]="Item"
        elif "quantityordered" in cl or "qty ordered" in cl: rn[c]="QtyOrdered"
        elif "item total" in cl or "po value" in cl: rn[c]="POValue"
    df=df.rename(columns=rn)
    for col in ["PO_No","Vendor","Item"]:
        if col not in df.columns: df[col]=""
    for col in ["QtyOrdered","POValue"]:
        if col not in df.columns: df[col]=0.0
        else: df[col]=_num(df[col])
    df["PO_Date"]=pd.to_datetime(df.get("PO_Date",""),dayfirst=True,errors="coerce")
    df["PO_No"]=df["PO_No"].astype(str).str.strip()
    df["Item"]=df["Item"].astype(str).str.strip().str.lower()
    return df

def _prep_bh(df):
    df=df.copy(); rn={}
    for c in df.columns:
        cl=c.lower()
        if "bill#" in cl or "bill number" in cl: rn[c]="InvNo"
        elif "reference number" in cl or "po_ref" in cl: rn[c]="PO_Ref"
        elif "vendor name" in cl: rn[c]="Vendor"
        elif "date" in cl: rn[c]="BillDate"
    df=df.rename(columns=rn)
    for col in ["InvNo","Vendor","PO_Ref"]:
        if col not in df.columns: df[col]=""
    df["BillDate"]=pd.to_datetime(df.get("BillDate",""),dayfirst=True,errors="coerce")
    df["InvNo"]=df["InvNo"].astype(str).str.strip()
    df["PO_Ref"]=df["PO_Ref"].astype(str).str.strip()
    return df

def _prep_bl(df):
    df=df.copy(); rn={}
    for c in df.columns:
        cl=c.lower()
        if "bill number" in cl: rn[c]="InvNo"
        elif "vendor name" in cl: rn[c]="Vendor"
        elif "bill date" in cl: rn[c]="BillDate"
        elif "item name" in cl: rn[c]="Item"
        elif "quantity" in cl or "qty" in cl: rn[c]="InvQty"
    df=df.rename(columns=rn)
    for col in ["InvNo","Vendor","Item"]:
        if col not in df.columns: df[col]=""
    if "InvQty" not in df.columns: df["InvQty"]=0.0
    else: df["InvQty"]=_num(df["InvQty"])
    df["BillDate"]=pd.to_datetime(df.get("BillDate",""),dayfirst=False,errors="coerce")
    df["InvNo"]=df["InvNo"].astype(str).str.strip()
    df["Item"]=df["Item"].astype(str).str.strip().str.lower()
    return df

def _walt(df):
    q=df["InvQty"].sum(); return df["W_Comp"].sum()/q if q>0 else 0

def render_supplier():
    st.title("🚚 Supplier Performance")
    po_df    = st.session_state["df_po"]
    bill_hdr = st.session_state["df_bill_hdr"]
    bill_lines=st.session_state["df_bill_lines"]
    if po_df is None:
        st.info("👈 Upload **PO CSV**, **Bill Header CSV**, and **Bill Lines CSV** from the sidebar.")
        return
    po=_prep_po(po_df)
    if bill_hdr is None or bill_lines is None:
        st.warning("Upload Bill Header + Bill Lines for lead time analysis. Showing PO summary only.")
        k1,k2,k3=st.columns(3)
        k1.metric("Total PO Value",f"₹{po['POValue'].sum():,.0f}")
        k2.metric("Total POs",po["PO_No"].nunique())
        k3.metric("Vendors",po["Vendor"].nunique())
        st.dataframe(po.groupby("Vendor").agg(POs=("PO_No","nunique"),Value=("POValue","sum")).reset_index()
                     .sort_values("Value",ascending=False),use_container_width=True,hide_index=True,
                     column_config={"Value":st.column_config.NumberColumn("PO Value (₹)",format="₹%.0f")}); return
    bh=_prep_bh(bill_hdr); bl=_prep_bl(bill_lines)
    lines=bl.merge(bh[["InvNo","Vendor","PO_Ref"]],on=["InvNo","Vendor"],how="left")
    lines=lines[lines["PO_Ref"].notna()&~lines["PO_Ref"].isin(["","nan","None"])]
    joined=lines.merge(po,left_on=["PO_Ref","Item","Vendor"],right_on=["PO_No","Item","Vendor"],how="inner")
    if joined.empty:
        st.warning("No matching records between PO and Bills. Check PO numbers and vendor names match."); return
    joined["LeadTime"]=(joined["BillDate"]-joined["PO_Date"]).dt.days
    joined=joined[joined["LeadTime"]>=0]
    joined["W_Comp"]=joined["LeadTime"]*joined["InvQty"]
    with st.expander("🔍 Filters",expanded=True):
        fc1,fc2,fc3=st.columns(3)
        vf=fc1.selectbox("Vendor",["All"]+sorted(po["Vendor"].dropna().unique().tolist()))
        min_d=po["PO_Date"].min(); max_d=po["PO_Date"].max()
        df_from=fc2.date_input("PO from",value=min_d.date() if pd.notna(min_d) else None)
        df_to  =fc3.date_input("PO to",  value=max_d.date() if pd.notna(max_d) else None)
    view=joined.copy()
    if vf!="All": view=view[view["Vendor"]==vf]
    if df_from and df_to:
        view=view[(view["PO_Date"].dt.date>=df_from)&(view["PO_Date"].dt.date<=df_to)]
    pof=po.copy()
    if vf!="All": pof=pof[pof["Vendor"]==vf]
    uninv=pof[~pof["PO_No"].isin(view["PO_No"].unique())]["PO_No"].nunique()
    walt=_walt(view) if not view.empty else 0
    fill=view["InvQty"].sum()/view["QtyOrdered"].sum()*100 if not view.empty and view["QtyOrdered"].sum()>0 else 0
    k1,k2,k3,k4,k5,k6=st.columns(6)
    k1.metric("Total PO Value",f"₹{pof['POValue'].sum():,.0f}")
    k2.metric("Total POs",pof["PO_No"].nunique())
    k3.metric("Yet to Supply",uninv,delta=f"-{uninv} pending" if uninv else None,delta_color="inverse")
    k4.metric("Unique SKUs",view["Item"].nunique())
    k5.metric("Weighted Avg Lead Time",f"{walt:.1f} days")
    k6.metric("Avg Fill Rate",f"{fill:.1f}%")
    st.divider()
    c1,c2=st.columns(2)
    with c1:
        st.markdown("#### Lead time by PO")
        pw=view.groupby("PO_No").apply(_walt,include_groups=False).reset_index(name="WALT")
        fig=px.bar(pw,x="PO_No",y="WALT",color="WALT",color_continuous_scale="RdYlGn_r")
        fig.update_layout(**PT,height=300,xaxis=dict(gridcolor="#21262d",tickangle=-35),yaxis=dict(gridcolor="#21262d"))
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        st.markdown("#### Lead time by SKU")
        iw=view.groupby("Item").apply(_walt,include_groups=False).reset_index(name="WALT").sort_values("WALT")
        iw["Item"]=iw["Item"].str.title()
        fig2=px.bar(iw,x="WALT",y="Item",orientation="h",color="WALT",color_continuous_scale="RdYlGn_r")
        fig2.update_layout(**PT,height=300,xaxis=dict(gridcolor="#21262d"),yaxis=dict(gridcolor="#21262d"))
        st.plotly_chart(fig2,use_container_width=True)
    st.divider()
    st.markdown("#### PO fulfilment detail")
    inv_keys=set(zip(view["PO_No"],view["Item"]))
    unf=pof[~pof.apply(lambda r:(r["PO_No"],r["Item"]) in inv_keys,axis=1)].copy()
    unf["Status"]="🔴 Not supplied"; unf["LeadTime"]=None; unf["InvQty"]=0; unf["FillPct"]=0.0
    fil=view.drop_duplicates(["PO_No","Item","Vendor"]).copy()
    fil["Status"]=fil.apply(lambda r:"🟢 Fully supplied" if r.get("InvQty",0)>=r["QtyOrdered"] else "🟡 Partially supplied",axis=1)
    fil["FillPct"]=(fil["InvQty"]/fil["QtyOrdered"].replace(0,1)*100).clip(upper=100)
    all_r=pd.concat([fil[["PO_No","PO_Date","Vendor","Item","QtyOrdered","InvQty","FillPct","LeadTime","Status"]],
                     unf[["PO_No","PO_Date","Vendor","Item","QtyOrdered","InvQty","FillPct","LeadTime","Status"]]],ignore_index=True)
    all_r["Item"]=all_r["Item"].str.title()
    all_r["PO_Date"]=pd.to_datetime(all_r["PO_Date"],errors="coerce").dt.strftime("%d-%b-%Y")
    st.dataframe(all_r.rename(columns={"PO_No":"PO Number","PO_Date":"PO Date","QtyOrdered":"Ordered",
                                        "InvQty":"Invoiced","FillPct":"Fill %","LeadTime":"Lead Time (days)"}),
                 use_container_width=True,hide_index=True,
                 column_config={"Fill %":st.column_config.NumberColumn(format="%.1f%%"),
                                "Lead Time (days)":st.column_config.NumberColumn(format="%.0f")})

# ════════════════════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════════════════════
page = st.session_state.get("page", "Overview")
{
    "Overview":             render_overview,
    "Inventory":            render_inventory,
    "P&L":                  render_pnl,
    "Working Capital":      render_working_capital,
    "Receivables":          render_receivables,
    "Supplier Performance": render_supplier,
}.get(page, render_overview)()
