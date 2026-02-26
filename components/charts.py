"""
Chart Helpers
Plotly theme and reusable chart configuration.
"""

# ─── Design Tokens ───
NAVY = "#0F172A"
NAVY_MID = "#1E293B"
SLATE = "#334155"
TEAL = "#0D9488"
TEAL_LT = "#14B8A6"
TEAL_BG = "#F0FDFA"
EMERALD = "#059669"
SKY = "#0284C7"
AMBER = "#D97706"
ROSE = "#E11D48"
PAL = [TEAL, SKY, AMBER, ROSE, "#7C3AED", "#0891B2"]

_CF = dict(family="Inter, -apple-system, sans-serif", size=12, color="#64748B")


def apply_theme(fig, h=420):
    """Apply the standard chart theme to a Plotly figure."""
    fig.update_layout(
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=_CF, margin=dict(l=50, r=30, t=40, b=40), height=h,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=11, color="#475569"), bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="#fff", bordercolor="#E2E8F0",
            font=dict(size=12, color="#0F172A", family="Inter"),
        ),
    )
    for ax in [fig.update_xaxes, fig.update_yaxes]:
        ax(gridcolor="#F1F5F9", griddash="dot", linecolor="#E2E8F0",
           linewidth=1, tickfont=dict(size=11, color="#64748B"),
           title_font=dict(size=12, color="#475569"))
    return fig
