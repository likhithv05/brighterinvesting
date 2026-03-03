"""
Scenario Forecasting Page — Tab 6
What-if financial projections based on custom assumptions.
"""

import streamlit as st
import plotly.graph_objects as go

from components.charts import apply_theme, PAL, TEAL, SKY, AMBER


# ─── Constants ───

_GRANT_SCENARIOS = [
    "Status quo",
    "Largest grant lost",
    "50% grant reduction",
    "Grants grow 10%",
]


# ─── Helpers ───

def _fmt(v):
    """Format a dollar value for display: $1.2M, $450.3K, or $1,234."""
    if v is None:
        return "N/A"
    av = abs(v)
    if av >= 1_000_000:
        s = f"${av / 1_000_000:,.1f}M"
    elif av >= 1_000:
        s = f"${av / 1_000:,.1f}K"
    else:
        s = f"${av:,.0f}"
    return f"({s})" if v < 0 else s


def _extract_baseline(row):
    """Pull baseline financial figures from the most recent filing."""
    g = lambda k: row.get(k, 0) or 0
    grants = g("TotalContributionsGrants")
    inv = g("InvestmentIncome") + g("NetGainLossInvestments")
    other = g("ProgramServiceRevenue") + g("OtherRevenue") + g("UnrelatedBusinessRevenue")
    return {
        "grants": grants,
        "investment": inv,
        "other_rev": other,
        "total_revenue": g("TotalRevenue"),
        "total_expenses": g("TotalExpenses"),
        "net_assets": g("TotalNetAssets"),
        "liquid": g("CashNonInterest") + g("SavingsTempCashInvestments")
                  + g("PublicInvestments"),
        "org_name": row.get("OrganizationName", "the organization"),
    }


def _grant_adj(base_grants, scenario, yr):
    """Return adjusted grant amount for a scenario at year offset yr."""
    if scenario == "Largest grant lost":
        return 0
    if scenario == "50% grant reduction":
        return base_grants * 0.5
    if scenario == "Grants grow 10%":
        return base_grants * (1.10 ** yr)
    return base_grants  # status quo


def _build_projections(bl, horizon, rev_pct, exp_pct, scenario, inv_pct):
    """Build list of projection dicts for each forecast year."""
    projections = []
    net = bl["net_assets"]
    liq = bl["liquid"]

    for yr in range(1, horizon + 1):
        grants = _grant_adj(bl["grants"], scenario, yr)
        inv = bl["investment"] * (1 + inv_pct) ** yr
        other = bl["other_rev"] * (1 + rev_pct) ** yr
        rev = grants + inv + other
        exp = bl["total_expenses"] * (1 + exp_pct) ** yr
        surplus = rev - exp
        net += surplus
        liq += surplus
        monthly_exp = exp / 12 if exp > 0 else 1
        runway = max(liq / monthly_exp, 0) if liq > 0 else 0

        projections.append({
            "yr": yr,
            "revenue": rev,
            "expenses": exp,
            "surplus": surplus,
            "net_assets": net,
            "liquid": liq,
            "runway": runway,
        })

    return projections


def _traffic_light(projections):
    """Determine traffic light status from projections."""
    cash_out = any(p["liquid"] <= 0 for p in projections)
    has_deficit = any(p["surplus"] < 0 for p in projections)
    if cash_out:
        return "b", "Cash Exhausted"
    if has_deficit:
        return "w", "Deficit Risk"
    return "g", "Sustainable"


def _forecast_chart(parsed_rows, projections, last_year):
    """Line chart: historical (solid) + projected (dashed) lines."""
    # Historical data
    hist_years = [str(r.get("TaxYear", "")) for r in parsed_rows]
    hist_rev = [r.get("TotalRevenue", 0) or 0 for r in parsed_rows]
    hist_exp = [r.get("TotalExpenses", 0) or 0 for r in parsed_rows]
    hist_net = [r.get("TotalNetAssets", 0) or 0 for r in parsed_rows]

    # Projected data (overlap by 1 point to connect lines)
    proj_years = [str(last_year)] + [str(last_year + p["yr"]) for p in projections]
    proj_rev = [hist_rev[-1]] + [p["revenue"] for p in projections]
    proj_exp = [hist_exp[-1]] + [p["expenses"] for p in projections]
    proj_net = [hist_net[-1]] + [p["net_assets"] for p in projections]

    series = [
        ("Revenue", TEAL, hist_years, hist_rev, proj_years, proj_rev),
        ("Expenses", AMBER, hist_years, hist_exp, proj_years, proj_exp),
        ("Net Assets", SKY, hist_years, hist_net, proj_years, proj_net),
    ]

    fig = go.Figure()

    for name, color, hx, hy, px, py in series:
        # Historical (solid)
        fig.add_trace(go.Scatter(
            x=hx, y=hy, name=name,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=7),
        ))
        # Projected (dashed)
        fig.add_trace(go.Scatter(
            x=px, y=py, name=name,
            mode="lines+markers",
            line=dict(color=color, width=2.5, dash="dash"),
            marker=dict(size=7, symbol="diamond"),
            showlegend=False,
        ))

    # Vertical line at boundary
    fig.add_vline(
        x=str(last_year), line_dash="dot", line_color="#CBD5E1", line_width=1,
    )
    fig.add_annotation(
        x=str(last_year + 1), y=1, yref="paper",
        text="Projected", showarrow=False,
        font=dict(size=11, color="#94A3B8"),
        yshift=10,
    )

    apply_theme(fig, 440)
    fig.update_yaxes(tickprefix="$", title_text="Amount ($)")
    st.plotly_chart(fig, use_container_width=True)


def _summary(bl, projections, scenario, last_year):
    """Generate plain-English forecast summary."""
    final = projections[-1]
    end_year = last_year + len(projections)
    base_rev = bl["total_revenue"]
    base_exp = bl["total_expenses"]

    # Revenue direction
    if final["revenue"] > base_rev:
        rev_dir = "increase"
    elif final["revenue"] < base_rev:
        rev_dir = "decrease"
    else:
        rev_dir = "remain flat"

    # Expense direction
    if final["expenses"] > base_exp:
        exp_dir = "grow"
    elif final["expenses"] < base_exp:
        exp_dir = "shrink"
    else:
        exp_dir = "remain flat"

    parts = [
        f"Under the **{scenario}** scenario, "
        f"**{bl['org_name']}** would see revenue "
        f"**{rev_dir}** from {_fmt(base_rev)} to {_fmt(final['revenue'])} "
        f"over {len(projections)} year{'s' if len(projections) > 1 else ''}.",

        f"Operating expenses would **{exp_dir}** "
        f"from {_fmt(base_exp)} to {_fmt(final['expenses'])}.",
    ]

    # Surplus / deficit status
    deficit_years = [p for p in projections if p["surplus"] < 0]
    if not deficit_years:
        parts.append(
            "The organization would **maintain a surplus** "
            "throughout the forecast period."
        )
    else:
        first_def = deficit_years[0]["yr"]
        parts.append(
            f"The organization would **enter a deficit in year {first_def}** "
            f"of the forecast period."
        )

    # Runway
    runway = final["runway"]
    if final["liquid"] <= 0:
        parts.append(
            "**Projected cash runway: 0 months.** "
            "The organization is projected to exhaust liquid reserves."
        )
    elif runway > 120:
        parts.append(
            "Projected cash runway: **well over 10 years** — "
            "a strong liquidity position."
        )
    elif runway < 6:
        parts.append(
            f"Projected cash runway: **{runway:.0f} months.** "
            f"This is below the recommended 6-month threshold."
        )
    else:
        parts.append(
            f"Projected cash runway: **{runway:.0f} months.**"
        )

    return " ".join(parts)


# ─── Public Render ───

def render(parsed_rows):
    if not parsed_rows:
        st.info("Load an organization's data to use forecasting.")
        return

    # ── Section header ──
    st.markdown(
        '<div class="sec-t">Scenario Forecasting</div>'
        '<div class="sec-s">'
        'Model future financial outcomes based on custom assumptions.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Input controls: Row 1 ──
    c1, c2, c3 = st.columns(3)
    with c1:
        horizon = st.slider("Forecast horizon (years)", 1, 5, 3, key="fc_hz")
    with c2:
        rev_pct = st.slider("Revenue change (%/yr)", -50, 50, 0, key="fc_rv") / 100
    with c3:
        exp_pct = st.slider("Expense change (%/yr)", -30, 30, 0, key="fc_ex") / 100

    # ── Input controls: Row 2 ──
    c4, c5 = st.columns(2)
    with c4:
        scenario = st.selectbox(
            "Grant dependency scenario", _GRANT_SCENARIOS, key="fc_gs",
        )
    with c5:
        inv_pct = st.slider("Investment return (%/yr)", -10, 20, 0, key="fc_iv") / 100

    # ── Compute projections ──
    latest = parsed_rows[-1]
    bl = _extract_baseline(latest)
    projections = _build_projections(bl, horizon, rev_pct, exp_pct, scenario, inv_pct)
    final = projections[-1]

    try:
        last_year = int(latest.get("TaxYear", 2024))
    except (ValueError, TypeError):
        last_year = 2024
    end_year = last_year + horizon

    # ── Traffic light + KPI summary ──
    tl_cls, tl_label = _traffic_light(projections)

    st.markdown(
        f'<div class="sec-t">Forecast Summary — {end_year}</div>'
        f'<div class="sec-s">Projected outcomes for the final forecast year.</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)

    # Card 1: Projected Revenue
    with cols[0]:
        with st.container(border=True):
            st.markdown(
                f'<div class="kpi-lbl">Projected Revenue</div>'
                f'<div class="kpi-val">{_fmt(final["revenue"])}</div>',
                unsafe_allow_html=True,
            )

    # Card 2: Projected Expenses
    with cols[1]:
        with st.container(border=True):
            st.markdown(
                f'<div class="kpi-lbl">Projected Expenses</div>'
                f'<div class="kpi-val">{_fmt(final["expenses"])}</div>',
                unsafe_allow_html=True,
            )

    # Card 3: Operating Surplus / Deficit
    with cols[2]:
        surplus_cls = "g" if final["surplus"] >= 0 else "b"
        surplus_lbl = "Surplus" if final["surplus"] >= 0 else "Deficit"
        with st.container(border=True):
            st.markdown(
                f'<div class="kpi-lbl">Operating Surplus</div>'
                f'<div class="kpi-val">{_fmt(final["surplus"])}</div>'
                f'<span class="bdg bdg-{surplus_cls}">'
                f'<span class="dt"></span>{surplus_lbl}</span>',
                unsafe_allow_html=True,
            )

    # Card 4: Cash Runway + Traffic Light
    with cols[3]:
        if final["liquid"] <= 0:
            runway_str = "0 mo"
        elif final["runway"] > 120:
            runway_str = "10+ yrs"
        else:
            runway_str = f'{final["runway"]:.0f} mo'
        with st.container(border=True):
            st.markdown(
                f'<div class="kpi-lbl">Cash Runway</div>'
                f'<div class="kpi-val">{runway_str}</div>'
                f'<span class="bdg bdg-{tl_cls}">'
                f'<span class="dt"></span>{tl_label}</span>',
                unsafe_allow_html=True,
            )

    # ── Projection chart ──
    st.markdown(
        '<div class="sec-t">Revenue, Expenses & Net Assets</div>'
        '<div class="sec-s">'
        'Solid lines show historical data; dashed lines show projections.'
        '</div>',
        unsafe_allow_html=True,
    )
    _forecast_chart(parsed_rows, projections, last_year)

    # ── Plain-English summary ──
    st.markdown(
        '<div class="sec-t">Forecast Analysis</div>'
        '<div class="sec-s">Plain-language interpretation of the scenario.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_summary(bl, projections, scenario, last_year))
