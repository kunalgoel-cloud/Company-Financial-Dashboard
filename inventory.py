import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c9d1d9", margin=dict(t=30, b=30, l=10, r=10),
)
CHANNEL_COLORS = {"B2B": "#1f6feb", "B2C": "#3fb950"}
BUCKET_COLORS = {
    ">80% shelf life": "#3fb950", "60-80% shelf life": "#1f6feb",
    "40-60% shelf life": "#d29922", "<40% shelf life": "#f85149"
}


def _prep(df: pd.DataFrame, im: dict) -> pd.DataFrame:
    df = df.copy()
    # Normalise column names
    col_map = {}
    for c in df.columns:
        cl = c.lower().strip()
        if "title" in cl or "name" in cl: col_map[c] = "Title"
        elif "sku" in cl: col_map[c] = "SKU"
        elif "stock" in cl or "qty" in cl or "quantity" in cl: col_map[c] = "Stock"
        elif "channel" in cl: col_map[c] = "Channel"
        elif "shelf" in cl: col_map[c] = "ShelfLife"
        elif "mfg" in cl or "manuf" in cl: col_map[c] = "MfgDate"
        elif "value" in cl or "val" in cl: col_map[c] = "Value"
        elif "date" in cl and "mfg" not in cl.lower(): col_map[c] = "SnapshotDate"
    df = df.rename(columns=col_map)

    for col in ["Title", "SKU", "Channel", "ShelfLife", "MfgDate"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["Stock", "Value"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Shelf life %
    df["ShelfPct"] = (
        df["ShelfLife"].astype(str).str.replace("%", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce").fillna(0)
    )

    def bucket(p):
        if p > 80: return ">80% shelf life"
        if p >= 60: return "60-80% shelf life"
        if p >= 40: return "40-60% shelf life"
        return "<40% shelf life"

    df["AgeingBucket"] = df["ShelfPct"].apply(bucket)
    df["MfgDate_dt"] = pd.to_datetime(df["MfgDate"], dayfirst=True, errors="coerce")

    # Cost price from item master
    im_lookup = {v.get("name","").lower(): v.get("cogs", 0) for v in im.values()}
    im_sku    = {k: v.get("cogs", 0) for k, v in im.items()}
    df["CostPrice"] = df.apply(
        lambda r: im_sku.get(str(r["SKU"]), im_lookup.get(str(r["Title"]).lower(), 0)), axis=1
    )
    df["Valuation"] = df["Stock"] * df["CostPrice"]
    return df


def render():
    st.title("📦 Inventory Snapshot")
    wms_df = st.session_state["df_wms"]
    im     = st.session_state["item_master"]

    if wms_df is None:
        st.info("👈 Upload a **WMS / Inventory CSV** from the sidebar to populate this tab.")
        st.caption("Required columns: Title/SKU, Total Stock/Qty, Mfg Date, Shelf Life, Channel (optional), Value (optional)")
        return

    df = _prep(wms_df, im)

    # ── Filters ────────────────────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            channels = ["All"] + sorted(df["Channel"].dropna().unique().tolist())
            ch_filter = st.selectbox("Channel", channels)
        with fc2:
            items = sorted(df["Title"].dropna().unique().tolist())
            item_filter = st.multiselect("Products", items, placeholder="All products")
        with fc3:
            metric_mode = st.radio("View by", ["Quantity", "Value (₹)"], horizontal=True)

    dff = df.copy()
    if ch_filter != "All":
        dff = dff[dff["Channel"] == ch_filter]
    if item_filter:
        dff = dff[dff["Title"].isin(item_filter)]

    metric_col = "Stock" if metric_mode == "Quantity" else "Valuation"
    suffix     = " units" if metric_mode == "Quantity" else " ₹"

    # ── KPI Row ────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Stock",      f"{dff['Stock'].sum():,.0f} units")
    k2.metric("Inventory Value",  f"₹{dff['Valuation'].sum():,.0f}")
    k3.metric("Active SKUs",      dff["Title"].nunique())
    k4.metric("Avg Shelf Life",   f"{dff['ShelfPct'].mean():.1f}%")
    k5.metric("At-Risk Stock (<40%)",
              f"{dff[dff['AgeingBucket']=='<40% shelf life']['Stock'].sum():,.0f}")

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Item-wise breakdown")
        item_summary = (dff.groupby(["Title","Channel"])[metric_col]
                        .sum().reset_index().sort_values(metric_col))
        fig = px.bar(item_summary, x=metric_col, y="Title", color="Channel",
                     orientation="h", color_discrete_map=CHANNEL_COLORS,
                     barmode="stack", height=max(350, len(item_summary)*22))
        fig.update_layout(**PLOTLY_THEME, yaxis_title="", xaxis_title=metric_mode,
                          legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("#### Ageing distribution")
        ageing_data = dff.groupby("AgeingBucket")[metric_col].sum().reset_index()
        order = [">80% shelf life", "60-80% shelf life", "40-60% shelf life", "<40% shelf life"]
        ageing_data["AgeingBucket"] = pd.Categorical(ageing_data["AgeingBucket"], categories=order, ordered=True)
        ageing_data = ageing_data.sort_values("AgeingBucket")
        fig2 = go.Figure(go.Pie(
            labels=ageing_data["AgeingBucket"], values=ageing_data[metric_col],
            hole=0.55, textinfo="label+percent",
            marker_colors=[BUCKET_COLORS.get(b, "#8b949e") for b in ageing_data["AgeingBucket"]],
        ))
        fig2.update_layout(**PLOTLY_THEME, height=350, showlegend=True,
                           legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig2, use_container_width=True)

    # Mfg date bar
    if dff["MfgDate_dt"].notna().any():
        st.markdown("#### Stock by manufacture batch")
        mfg_data = (dff.dropna(subset=["MfgDate_dt"])
                    .groupby("MfgDate_dt")[metric_col].sum().reset_index()
                    .sort_values("MfgDate_dt"))
        mfg_data["MfgLabel"] = mfg_data["MfgDate_dt"].dt.strftime("%b %Y")
        fig3 = px.bar(mfg_data, x="MfgLabel", y=metric_col,
                      color_discrete_sequence=["#1f6feb"])
        fig3.update_layout(**PLOTLY_THEME, xaxis_title="Manufacture batch", yaxis_title=metric_mode)
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    # ── Detail table ───────────────────────────────────────────────────────
    st.markdown("#### Detailed records")
    display_df = dff[["Channel","Title","SKU","Stock","ShelfPct","AgeingBucket","CostPrice","Valuation"]].copy()
    display_df.columns = ["Channel","Product","SKU","Stock","Shelf Life %","Ageing","Cost (₹)","Value (₹)"]
    st.dataframe(display_df.sort_values("Value (₹)", ascending=False),
                 use_container_width=True, hide_index=True,
                 column_config={
                     "Shelf Life %": st.column_config.ProgressColumn("Shelf Life %", min_value=0, max_value=100),
                     "Value (₹)": st.column_config.NumberColumn("Value (₹)", format="₹%.0f"),
                     "Cost (₹)": st.column_config.NumberColumn("Cost (₹)", format="₹%.2f"),
                 })

    if im and dff["CostPrice"].eq(0).any():
        missing = dff[dff["CostPrice"]==0]["Title"].unique().tolist()
        st.warning(f"⚠️ {len(missing)} products have no cost price in Item Master — valuations are ₹0. "
                   f"Add them via the sidebar ⚙️ Item Master.")
