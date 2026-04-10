"""
exports/exporters.py
---------------------
All export formats for generated designs.

Supported formats:
  CSV      — flat file, one row per (block, task, alternative)
  Excel    — multi-sheet workbook with design + diagnostics + legend
  JSON     — hierarchical structure preserving all metadata
  Qualtrics CSV — format compatible with Qualtrics embedded data import
  Sawtooth CSV  — numeric level codes compatible with Lighthouse Studio
"""

from __future__ import annotations

import io
import json
import math
from typing import Optional

import pandas as pd

from core.models import CBCDesign, CBCTask, DiagnosticsReport, MaxDiffDesign


# ── Shared helpers ─────────────────────────────────────────────────────────────

def cbc_to_dataframe(design: CBCDesign) -> pd.DataFrame:
    """Flatten a CBCDesign into a tidy DataFrame."""
    rows = []
    for task in design.tasks:
        for alt_idx, alt in enumerate(task.alternatives, start=1):
            row = {
                "Block": task.block,
                "Task": task.task_number,
                "Alternative": alt_idx,
                "Holdout": int(task.is_holdout),
            }
            row.update(alt)
            rows.append(row)
    return pd.DataFrame(rows)


def maxdiff_to_dataframe(design: MaxDiffDesign) -> pd.DataFrame:
    """Flatten a MaxDiffDesign into a tidy DataFrame."""
    rows = []
    for md_set in design.sets:
        for pos, item in enumerate(md_set.items, start=1):
            rows.append({
                "Block": md_set.block,
                "Set": md_set.set_number,
                "Position": pos,
                "Item": item,
            })
    return pd.DataFrame(rows)


# ── CSV ───────────────────────────────────────────────────────────────────────

def export_cbc_csv(design: CBCDesign) -> bytes:
    df = cbc_to_dataframe(design)
    return df.to_csv(index=False).encode("utf-8")


def export_maxdiff_csv(design: MaxDiffDesign) -> bytes:
    df = maxdiff_to_dataframe(design)
    return df.to_csv(index=False).encode("utf-8")


# ── JSON ──────────────────────────────────────────────────────────────────────

def export_cbc_json(design: CBCDesign) -> bytes:
    data = {
        "study_type": "CBC",
        "metadata": design.metadata,
        "attributes": [
            {"name": a.name, "levels": a.levels, "is_price": a.is_price}
            for a in design.attributes
        ],
        "blocks": {
            str(b): [
                {
                    "task_number": t.task_number,
                    "is_holdout": t.is_holdout,
                    "complexity_score": round(t.complexity_score, 3),
                    "alternatives": t.alternatives,
                }
                for t in design.get_block(b)
            ]
            for b in design.blocks
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def export_maxdiff_json(design: MaxDiffDesign) -> bytes:
    data = {
        "study_type": "MaxDiff",
        "metadata": design.metadata,
        "items": design.items,
        "appearance_counts": design.appearance_counts,
        "blocks": {
            str(b): [
                {"set_number": s.set_number, "items": s.items}
                for s in design.get_block(b)
            ]
            for b in design.blocks
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


# ── Excel ─────────────────────────────────────────────────────────────────────

def _write_header(ws, text: str, row: int = 1) -> None:
    ws.cell(row=row, column=1, value=text)


def export_cbc_excel(
    design: CBCDesign,
    diagnostics: Optional[DiagnosticsReport] = None,
) -> bytes:
    """
    Multi-sheet Excel workbook:
      Sheet 1: Full Design Matrix
      Sheet 2: Diagnostics (if provided)
      Sheet 3: Legend / Codebook
    """
    buffer = io.BytesIO()
    df = cbc_to_dataframe(design)

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # ── Sheet 1: Design Matrix ──
        df.to_excel(writer, sheet_name="Design Matrix", index=False)
        wb = writer.book
        ws = writer.sheets["Design Matrix"]

        # Header formatting
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#4B6BFB", "font_color": "#FFFFFF",
            "border": 1,
        })
        holdout_fmt = wb.add_format({"bg_color": "#FEF3C7", "border": 1})
        normal_fmt = wb.add_format({"border": 1})

        for col_num, col_name in enumerate(df.columns):
            ws.write(0, col_num, col_name, header_fmt)
            ws.set_column(col_num, col_num, max(12, len(str(col_name)) + 4))

        for row_num in range(1, len(df) + 1):
            fmt = holdout_fmt if df.iloc[row_num - 1]["Holdout"] == 1 else normal_fmt
            for col_num in range(len(df.columns)):
                ws.write(row_num, col_num, df.iloc[row_num - 1, col_num], fmt)

        # ── Sheet 2: Diagnostics ──
        if diagnostics:
            diag_rows = [
                ["Metric", "Value", "Status"],
                ["D-efficiency (%)", f"{diagnostics.d_efficiency:.2f}",
                 "✓ Good" if diagnostics.d_efficiency >= 80 else "⚠ Marginal"],
                ["Max attribute correlation", f"{diagnostics.max_attr_correlation:.4f}",
                 "✓ OK" if diagnostics.max_attr_correlation < 0.10 else "⚠ High"],
                ["Task overlap (%)", f"{diagnostics.overlap_pct:.1f}",
                 "✓ OK" if diagnostics.overlap_pct < 30 else "⚠ High"],
                ["Expected SE per param", f"{diagnostics.expected_se:.4f}", ""],
                ["Overall grade", diagnostics.overall_grade, ""],
            ]
            diag_df = pd.DataFrame(diag_rows[1:], columns=diag_rows[0])
            diag_df.to_excel(writer, sheet_name="Diagnostics", index=False)

            if diagnostics.warnings:
                warn_df = pd.DataFrame({"Warnings": diagnostics.warnings})
                warn_df.to_excel(writer, sheet_name="Diagnostics",
                                 startrow=len(diag_df) + 3, index=False)

        # ── Sheet 3: Legend ──
        legend_rows = [["Attribute", "Level Index", "Level Value"]]
        for attr in design.attributes:
            for i, lvl in enumerate(attr.levels):
                legend_rows.append([attr.name, i, lvl])
        legend_df = pd.DataFrame(legend_rows[1:], columns=legend_rows[0])
        legend_df.to_excel(writer, sheet_name="Codebook", index=False)

    buffer.seek(0)
    return buffer.read()


def export_maxdiff_excel(
    design: MaxDiffDesign,
    diagnostics: Optional[DiagnosticsReport] = None,
) -> bytes:
    buffer = io.BytesIO()
    df = maxdiff_to_dataframe(design)

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Design Matrix", index=False)
        wb = writer.book
        ws = writer.sheets["Design Matrix"]
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#4B6BFB", "font_color": "#FFFFFF", "border": 1
        })
        for col_num, col_name in enumerate(df.columns):
            ws.write(0, col_num, col_name, header_fmt)
            ws.set_column(col_num, col_num, max(14, len(str(col_name)) + 4))

        # Item appearances sheet
        app_df = pd.DataFrame(
            [(item, count) for item, count in design.appearance_counts.items()],
            columns=["Item", "Appearances"]
        )
        app_df.to_excel(writer, sheet_name="Item Appearances", index=False)

        if diagnostics:
            diag_rows = [
                ["Metric", "Value"],
                ["Balance score (lower = better)", f"{diagnostics.appearance_variance:.4f}"],
                ["Pair coverage (%)", f"{diagnostics.pair_coverage_pct:.1f}"],
                ["Appearance variance", f"{diagnostics.appearance_variance:.4f}"],
                ["Expected SE", f"{diagnostics.expected_se:.4f}"],
            ]
            diag_df = pd.DataFrame(diag_rows[1:], columns=diag_rows[0])
            diag_df.to_excel(writer, sheet_name="Diagnostics", index=False)

    buffer.seek(0)
    return buffer.read()


# ── Qualtrics CSV ─────────────────────────────────────────────────────────────

def export_qualtrics_csv(design: CBCDesign) -> bytes:
    """
    Export a Qualtrics-compatible CSV with embedded data variable names.
    Each row represents one alternative in one task, with variable names
    formatted as "Q{task}_Alt{alt}_{AttrName}" for use in Qualtrics loop & merge.
    """
    rows = []
    for task in design.tasks:
        if task.is_holdout:
            continue
        for alt_idx, alt in enumerate(task.alternatives, start=1):
            row = {
                "QualticsBlock": task.block,
                "TaskNum": task.task_number,
                "AltNum": alt_idx,
            }
            for attr_name, level_val in alt.items():
                # Qualtrics embedded data format
                var_name = f"Q{task.task_number}_Alt{alt_idx}_{attr_name.replace(' ', '_')}"
                row[var_name] = level_val
            rows.append(row)

    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")


# ── Sawtooth SSI-compatible CSV ───────────────────────────────────────────────

def export_sawtooth_csv(design: CBCDesign) -> bytes:
    """
    Export numeric level codes compatible with Sawtooth Software Lighthouse Studio.
    Levels are 1-indexed integers. Format: Version, Task, Concept, Attr1, Attr2, ...
    """
    attr_names = [a.name for a in design.attributes]
    level_maps = {a.name: {lvl: i + 1 for i, lvl in enumerate(a.levels)} for a in design.attributes}

    rows = []
    for task in design.tasks:
        if task.is_holdout:
            continue
        for alt_idx, alt in enumerate(task.alternatives, start=1):
            row = {
                "Version": task.block,
                "Task": task.task_number,
                "Concept": alt_idx,
            }
            for attr_name in attr_names:
                level_val = alt.get(attr_name, "")
                row[attr_name] = level_maps[attr_name].get(level_val, 0)
            rows.append(row)

    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")
