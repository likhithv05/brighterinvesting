"""
KPI Card & Financial Table HTML Generators
Reusable HTML rendering functions for KPI grids and financial data tables.
"""

import streamlit as st
from core.kpis import KPI_DEFINITIONS, format_kpi_value, get_kpi_status


_ST = {
    "good": ("Healthy", "g"),
    "warning": ("Watch", "w"),
    "concern": ("At Risk", "b"),
    "neutral": ("N/A", "n"),
}


def sec(title, sub):
    """Return section heading HTML."""
    return f'<div class="sec-t">{title}</div><div class="sec-s">{sub}</div>'


def kpi_html(keys, kpis_dict):
    """Generate KPI card grid HTML."""
    h = '<div class="kpi-grid">'
    for k in keys:
        d = KPI_DEFINITIONS.get(k, {})
        v = kpis_dict.get(k, 0)
        fv = format_kpi_value(k, v)
        s = get_kpi_status(k, v)
        lbl, cls = _ST.get(s, ("\u2014", "n"))
        h += f"""<div class="kpi-c">
          <div class="kpi-top">
            <span class="kpi-lbl">{d.get('label', k)}</span>
            <span class="bdg bdg-{cls}"><span class="dt"></span>{lbl}</span>
          </div>
          <div class="kpi-val">{fv}</div>
          <div class="kpi-bm">{d.get('benchmark', '')}</div>
        </div>"""
    h += "</div>"
    return h


def fin_table(title, years, fields, data):
    """Generate a financial HTML table (rows=fields, cols=years)."""
    h = f'<div class="fin-tbl"><div class="fin-hdr">{title}</div>'
    h += '<div style="overflow-x:auto"><table><thead><tr>'
    h += '<th style="text-align:left">Field</th>'
    for yr in years:
        h += f"<th>{yr}</th>"
    h += "</tr></thead><tbody>"
    for f_def in fields:
        h += "<tr>"
        h += f'<td>{f_def["label"]}</td>'
        for row in data:
            v = row.get(f_def["key"], 0)
            if isinstance(v, (int, float)):
                fv = f"${v:,.0f}"
            else:
                fv = str(v)
            h += f'<td class="num">{fv}</td>'
        h += "</tr>"
    h += "</tbody></table></div></div>"
    return h
