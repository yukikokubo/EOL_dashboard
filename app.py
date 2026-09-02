from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


DATA_PATH = Path(__file__).with_name("sample_assets.csv")
DATE_COLUMNS = ["EOL", "保守期限", "納品日", "登録日時", "更新日時"]
REQUIRED_COLUMNS = [
    "資産ID",
    "企業コード",
    "企業名",
    "営業担当者",
    "機器名",
    "メーカー",
    "型番",
    "数量",
    "資産種別",
    "EOL",
    "保守期限",
    "納品日",
    "設置場所",
    "登録日時",
    "更新日時",
]


st.set_page_config(
    page_title="EOL・保守期限ダッシュボード",
    page_icon="📊",
    layout="wide",
)


@st.cache_data
def load_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"CSVに必要な項目がありません: {', '.join(missing_columns)}")

    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["数量"] = pd.to_numeric(df["数量"], errors="coerce").fillna(0).astype(int)
    return df


def add_status_columns(df: pd.DataFrame, base_date: pd.Timestamp) -> pd.DataFrame:
    enriched = df.copy()
    enriched["EOL残日数"] = (enriched["EOL"] - base_date).dt.days
    enriched["保守残日数"] = (enriched["保守期限"] - base_date).dt.days
    enriched["対応期限"] = enriched[["EOL", "保守期限"]].min(axis=1)
    enriched["対応残日数"] = (enriched["対応期限"] - base_date).dt.days

    def label(days: int | float) -> str:
        if pd.isna(days):
            return "不明"
        if days < 0:
            return "期限切れ"
        if days <= 30:
            return "30日以内"
        if days <= 90:
            return "90日以内"
        return "90日以上"

    enriched["対応ステータス"] = enriched["対応残日数"].map(label)
    enriched["EOLステータス"] = enriched["EOL残日数"].map(label)
    enriched["保守ステータス"] = enriched["保守残日数"].map(label)
    return enriched


def status_order() -> list[str]:
    return ["期限切れ", "30日以内", "90日以内", "90日以上", "不明"]


def filter_by_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("フィルター")

    companies = st.sidebar.multiselect(
        "企業名",
        sorted(df["企業名"].dropna().unique()),
        placeholder="すべて",
    )
    owners = st.sidebar.multiselect(
        "営業担当者",
        sorted(df["営業担当者"].dropna().unique()),
        placeholder="すべて",
    )
    categories = st.sidebar.multiselect(
        "資産種別",
        sorted(df["資産種別"].dropna().unique()),
        placeholder="すべて",
    )
    manufacturers = st.sidebar.multiselect(
        "メーカー",
        sorted(df["メーカー"].dropna().unique()),
        placeholder="すべて",
    )
    statuses = st.sidebar.multiselect(
        "対応ステータス",
        status_order(),
        default=status_order(),
    )

    filtered = df.copy()
    if companies:
        filtered = filtered[filtered["企業名"].isin(companies)]
    if owners:
        filtered = filtered[filtered["営業担当者"].isin(owners)]
    if categories:
        filtered = filtered[filtered["資産種別"].isin(categories)]
    if manufacturers:
        filtered = filtered[filtered["メーカー"].isin(manufacturers)]
    if statuses:
        filtered = filtered[filtered["対応ステータス"].isin(statuses)]

    return filtered


def metric_card(label: str, value: int | str, help_text: str | None = None) -> None:
    st.metric(label=label, value=value, help=help_text)


def to_download_csv(df: pd.DataFrame) -> bytes:
    export_df = df.copy()
    for column in DATE_COLUMNS + ["対応期限"]:
        if column in export_df:
            export_df[column] = export_df[column].dt.strftime("%Y-%m-%d")
    return export_df.to_csv(index=False).encode("utf-8-sig")


STATUS_COLORS = {
    "期限切れ": "#d94f45",
    "30日以内": "#f28e2b",
    "90日以内": "#edc948",
    "90日以上": "#4e79a7",
    "不明": "#6b7280",
}

TABLE_STATUS_COLORS = {
    "期限切れ": "background-color: #fde7e4",
    "30日以内": "background-color: #fff0dc",
    "90日以内": "background-color: #fff8d7",
    "不明": "background-color: #f1f3f5",
}


def style_status_rows(row: pd.Series) -> list[str]:
    style = TABLE_STATUS_COLORS.get(row["対応ステータス"], "")
    return [style for _ in row]


def selected_statuses_from_event(event) -> list[str]:
    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, dict):
        selection = event.get("selection")
    points = getattr(selection, "points", None)
    if points is None and isinstance(selection, dict):
        points = selection.get("points", [])

    selected = []
    for point in points or []:
        value = getattr(point, "x", None)
        if value is None and isinstance(point, dict):
            value = point.get("x") or point.get("label")
        if value in STATUS_COLORS:
            selected.append(value)
    return list(dict.fromkeys(selected))


st.title("EOL・保守期限ダッシュボード")
st.caption("販売済みオフィス機器のEOLと保守期限を営業・顧客・機器カテゴリ別に確認できます。")

uploaded_file = st.sidebar.file_uploader("CSVアップロード", type=["csv"])
source = uploaded_file if uploaded_file is not None else DATA_PATH

try:
    raw_df = load_csv(source)
except Exception as exc:
    st.error(str(exc))
    st.stop()

base_date = pd.Timestamp(date.today())
df = add_status_columns(raw_df, base_date)
sidebar_filtered_df = filter_by_sidebar(df)

if sidebar_filtered_df.empty:
    st.warning("条件に一致するデータがありません。フィルターを変更してください。")
    st.stop()

status_counts = (
    sidebar_filtered_df.groupby("対応ステータス", as_index=False)
    .agg(資産数=("資産ID", "count"), 数量=("数量", "sum"))
)
status_counts["対応ステータス"] = pd.Categorical(
    status_counts["対応ステータス"],
    categories=status_order(),
    ordered=True,
)
status_counts = status_counts.sort_values("対応ステータス")

selected_statuses = selected_statuses_from_event(st.session_state.get("status_filter_chart", {}))
if selected_statuses:
    filtered_df = sidebar_filtered_df[sidebar_filtered_df["対応ステータス"].isin(selected_statuses)].copy()
    st.caption(f"選択中のステータス: {', '.join(selected_statuses)}")
else:
    filtered_df = sidebar_filtered_df

expired_count = int((filtered_df["対応残日数"] < 0).sum())
within_90_count = int(((filtered_df["対応残日数"] >= 0) & (filtered_df["対応残日数"] <= 90)).sum())
within_30_count = int(((filtered_df["対応残日数"] >= 0) & (filtered_df["対応残日数"] <= 30)).sum())
total_quantity = int(filtered_df["数量"].sum())

kpi_cols = st.columns(5)
with kpi_cols[0]:
    metric_card("対象資産", f"{len(filtered_df):,} 件")
with kpi_cols[1]:
    metric_card("合計数量", f"{total_quantity:,} 台")
with kpi_cols[2]:
    metric_card("期限切れ", f"{expired_count:,} 件", "EOLまたは保守期限の早い方が過ぎている資産")
with kpi_cols[3]:
    metric_card("30日以内", f"{within_30_count:,} 件")
with kpi_cols[4]:
    metric_card("90日以内", f"{within_90_count:,} 件")

st.divider()

category_counts = (
    filtered_df.groupby("資産種別", as_index=False)
    .agg(資産数=("資産ID", "count"), 数量=("数量", "sum"))
    .sort_values("資産数", ascending=False)
)

owner_risk = (
    filtered_df[filtered_df["対応ステータス"].isin(["期限切れ", "30日以内", "90日以内"])]
    .groupby(["営業担当者", "対応ステータス"], as_index=False)
    .agg(資産数=("資産ID", "count"))
)

deadline_df = filtered_df.sort_values("対応期限")
risk_statuses = ["期限切れ", "30日以内", "90日以内"]
risk_df = filtered_df[filtered_df["対応ステータス"].isin(risk_statuses)].copy()
top_risk_companies = (
    risk_df.groupby("企業名", as_index=False)
    .agg(期限接近資産=("資産ID", "count"), 対象数量=("数量", "sum"))
    .sort_values(["期限接近資産", "対象数量"], ascending=False)
    .head(20)
)
company_risk = (
    risk_df[risk_df["企業名"].isin(top_risk_companies["企業名"])]
    .groupby(["企業名", "対応ステータス"], as_index=False)
    .agg(資産数=("資産ID", "count"))
)

chart_cols = st.columns((1.05, 1))
with chart_cols[0]:
    fig_status = px.bar(
        status_counts,
        x="対応ステータス",
        y="資産数",
        color="対応ステータス",
        category_orders={"対応ステータス": status_order()},
        color_discrete_map=STATUS_COLORS,
        title="対応ステータス別 資産数",
    )
    fig_status.update_traces(
        selected=dict(marker=dict(opacity=1)),
        unselected=dict(marker=dict(opacity=0.35)),
    )
    fig_status.update_layout(showlegend=False, height=380, margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(
        fig_status,
        use_container_width=True,
        key="status_filter_chart",
        on_select="rerun",
        selection_mode="points",
    )

with chart_cols[1]:
    fig_category = px.pie(
        category_counts,
        names="資産種別",
        values="数量",
        title="資産種別別 数量構成",
        hole=0.45,
    )
    fig_category.update_layout(height=380, margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(fig_category, use_container_width=True)

lower_cols = st.columns((1, 1))
with lower_cols[0]:
    if owner_risk.empty:
        st.info("期限が近い資産はありません。")
    else:
        fig_owner = px.bar(
            owner_risk,
            x="営業担当者",
            y="資産数",
            color="対応ステータス",
            category_orders={"対応ステータス": status_order()},
            color_discrete_map=STATUS_COLORS,
            title="営業担当者別 期限接近資産",
        )
        fig_owner.update_layout(height=360, margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(fig_owner, use_container_width=True)

with lower_cols[1]:
    if company_risk.empty:
        st.info("期限が近い企業はありません。")
    else:
        fig_company = px.bar(
            company_risk,
            x="企業名",
            y="資産数",
            color="対応ステータス",
            category_orders={"対応ステータス": status_order()},
            color_discrete_map=STATUS_COLORS,
            title="企業別 期限接近資産",
        )
        fig_company.update_layout(height=360, margin=dict(l=10, r=10, t=55, b=10), xaxis_tickangle=-35)
        st.plotly_chart(fig_company, use_container_width=True)

st.subheader("機器別 期限ガントチャート")
gantt_df = (
    filtered_df.assign(対応残日数_並び=filtered_df["対応残日数"].fillna(999999))
    .sort_values(["対応残日数_並び", "企業名", "機器名"])
    .copy()
)
gantt_df = gantt_df[gantt_df["納品日"].notna() & gantt_df["対応期限"].notna()].copy()

if gantt_df.empty:
    st.info("ガントチャートに表示できる日付データがありません。")
else:
    gantt_df["表示名"] = gantt_df["企業名"] + " / " + gantt_df["機器名"] + " / " + gantt_df["型番"]
    gantt_order = gantt_df["表示名"].tolist()

    fig_gantt = px.timeline(
        gantt_df,
        x_start="納品日",
        x_end="対応期限",
        y="表示名",
        color="対応ステータス",
        category_orders={
            "対応ステータス": status_order(),
            "表示名": gantt_order,
        },
        color_discrete_map=STATUS_COLORS,
        hover_data={
            "表示名": False,
            "資産ID": True,
            "企業名": True,
            "営業担当者": True,
            "資産種別": True,
            "数量": True,
            "EOL": "|%Y-%m-%d",
            "保守期限": "|%Y-%m-%d",
            "納品日": "|%Y-%m-%d",
            "対応期限": "|%Y-%m-%d",
            "対応残日数": True,
            "設置場所": True,
        },
        title="納品日から対応期限まで（期限切れ・期限接近順）",
    )
    fig_gantt.add_shape(
        type="line",
        x0=base_date,
        x1=base_date,
        y0=0,
        y1=1,
        xref="x",
        yref="paper",
        line=dict(width=2, dash="dash", color="#333333"),
    )
    fig_gantt.add_annotation(
        x=base_date,
        y=1,
        xref="x",
        yref="paper",
        text="今日",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
    )
    fig_gantt.add_trace(
        go.Scatter(
            x=[gantt_df["納品日"].min(), gantt_df["対応期限"].max()],
            y=[None, None],
            mode="markers",
            marker=dict(opacity=0),
            xaxis="x2",
            yaxis="y",
            showlegend=False,
            hoverinfo="skip",
        )
    )
    gantt_height = max(720, len(gantt_df) * 24 + 120)
    fig_gantt.update_layout(
        height=gantt_height,
        margin=dict(l=10, r=10, t=55, b=10),
        yaxis_title=None,
        xaxis2=dict(
            overlaying="x",
            side="top",
            matches="x",
            showgrid=False,
            ticks="outside",
        ),
    )
    with st.container(height=590):
        st.plotly_chart(fig_gantt, use_container_width=True)

st.subheader("フィルター結果一覧")
table_columns = [
    "対応ステータス",
    "対応残日数",
    "資産ID",
    "企業名",
    "営業担当者",
    "資産種別",
    "機器名",
    "メーカー",
    "型番",
    "数量",
    "EOL",
    "保守期限",
    "設置場所",
]
display_df = deadline_df[table_columns].copy()
display_df.insert(0, "No.", range(1, len(display_df) + 1))
display_df["EOL"] = display_df["EOL"].dt.strftime("%Y-%m-%d")
display_df["保守期限"] = display_df["保守期限"].dt.strftime("%Y-%m-%d")
st.dataframe(
    display_df.style.apply(style_status_rows, axis=1),
    use_container_width=True,
    hide_index=True,
    height=560,
)

st.download_button(
    "フィルター後データをCSVダウンロード",
    data=to_download_csv(filtered_df),
    file_name="filtered_eol_assets.csv",
    mime="text/csv",
)
