#!/usr/bin/env python3
"""Regenerate manuscript numbers and LaTeX tables from the released analysis files.

The script performs deterministic validation only. It does not call a model, Docker,
or a verifier, and it does not alter the input data.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TABLES = ROOT / "tables"
NUMBERS = ROOT / "numbers.tex"

STRATUM_LABELS = {
    "deepseek_clean": "DeepSeek clean",
    "deepseek_extension": "DeepSeek extension",
    "glm_supplementary": "GLM boundary",
}
STRATUM_ORDER = ["deepseek_clean", "deepseek_extension", "glm_supplementary"]


def pct(n: int | float, d: int | float, digits: int = 2) -> str:
    if d == 0:
        return "0.00"
    return f"{100.0 * float(n) / float(d):.{digits}f}"


def tex_escape(value: object) -> str:
    s = str(value)
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in s)


def macro(name: str, value: object) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def support_profile(df: pd.DataFrame, signal: str) -> tuple[int, int, int, int]:
    pos = df[df[signal] == 1]
    if pos.empty:
        return (0, 0, 0, 0)
    return (
        len(pos),
        pos["cell_id"].nunique(),
        pos["task_id"].nunique(),
        pos["task_family"].nunique(),
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def load() -> dict[str, pd.DataFrame]:
    files = {
        "rows": "row_level_claim_view.csv",
        "canonical": "row_level_master_original.csv",
        "crosstab": "action_pass_crosstab_by_stratum.csv",
        "task_support": "task_support_summary.csv",
        "opportunity": "repeated_opportunity_k1_k8.csv",
        "contradictions": "glm_12_contradictions.csv",
        "controls": "endpoint_control_runs.csv",
        "stratified": "protocol_stratified_summary.csv",
        "provider": "provider_metadata_coverage.csv",
        "windows": "run_windows_from_canonical_rows.csv",
        "task_manifest": "task_manifest.csv",
    }
    return {key: pd.read_csv(DATA / filename) for key, filename in files.items()}


def validate(d: dict[str, pd.DataFrame]) -> None:
    rows = d["rows"]
    canonical = d["canonical"]
    assert_equal(len(rows), 2400, "total rows")
    assert_equal(len(canonical), 2400, "canonical rows")
    assert_equal(
        int((rows["canonical_row_id"].astype(str) != canonical["row_id"].astype(str)).sum()),
        0,
        "claim-view/canonical row-order mismatches",
    )
    recomputed_action = (
        canonical["action_governance_success"].eq(1)
        & canonical["deterministic_edit_apply_success"].eq(1)
        & canonical["patch_apply_check_ok"].eq(1)
    ).astype(int)
    assert_equal(
        int((recomputed_action != canonical["action_governance_harmonized"].eq(1).astype(int)).sum()),
        0,
        "canonical raw-to-harmonized formula mismatches",
    )
    assert_equal(
        int((rows["action_harmonized"] != recomputed_action).sum()),
        0,
        "claim-view harmonized action mismatches",
    )
    assert_equal(
        int((rows["verifier_pass"] != canonical["answer_success"].eq(1).astype(int)).sum()),
        0,
        "claim-view verifier-pass mismatches",
    )
    expected_rows = {
        "deepseek_clean": 960,
        "deepseek_extension": 960,
        "glm_supplementary": 480,
    }
    expected_cells = {
        "deepseek_clean": 120,
        "deepseek_extension": 120,
        "glm_supplementary": 60,
    }
    expected_actions = {
        "deepseek_clean": 199,
        "deepseek_extension": 204,
        "glm_supplementary": 86,
    }
    expected_passes = {
        "deepseek_clean": 14,
        "deepseek_extension": 14,
        "glm_supplementary": 0,
    }
    expected_raw_actions = {
        "deepseek_clean": 199,
        "deepseek_extension": 204,
        "glm_supplementary": 98,
    }
    for s in STRATUM_ORDER:
        sub = rows[rows.stratum == s]
        assert_equal(len(sub), expected_rows[s], f"{s} rows")
        assert_equal(sub.cell_id.nunique(), expected_cells[s], f"{s} cells")
        assert_equal(sub.task_id.nunique(), 30, f"{s} tasks")
        assert_equal(set(sub.groupby("cell_id").size().tolist()), {8}, f"{s} repetitions")
        assert_equal(int(sub.action_harmonized.sum()), expected_actions[s], f"{s} actions")
        assert_equal(int(sub.action_raw.sum()), expected_raw_actions[s], f"{s} raw actions")
        assert_equal(int(sub.verifier_pass.sum()), expected_passes[s], f"{s} passes")
    assert_equal(int(((rows.action_harmonized == 0) & (rows.verifier_pass == 1)).sum()), 0,
                 "pass without harmonized action")
    assert_equal(len(d["contradictions"]), 12, "GLM contradiction count")
    controls = d["controls"]
    assert_equal(len(controls), 33, "control attempts")
    assert_equal(int((controls.verifier_entered == 1).sum()), 21, "verifier-reached controls")
    assert_equal(int((controls.infrastructure_failure == 1).sum()), 12, "pre-verifier controls")


def generate_numbers(d: dict[str, pd.DataFrame]) -> None:
    rows = d["rows"]
    macros: list[str] = [
        "% Generated by scripts/build_derived.py. Do not edit by hand.",
        macro("TotalRows", "2,400"),
        macro("TotalCells", "300"),
        macro("TasksPerStratum", "30"),
        macro("RepetitionsPerCell", "8"),
    ]
    prefixes = {
        "deepseek_clean": "Clean",
        "deepseek_extension": "Extension",
        "glm_supplementary": "GLM",
    }
    for s in STRATUM_ORDER:
        sub = rows[rows.stratum == s]
        p = prefixes[s]
        n = len(sub)
        actions = int(sub.action_harmonized.sum())
        raw_actions = int(sub.action_raw.sum())
        passes = int(sub.verifier_pass.sum())
        families = int(sub.task_family.nunique())
        cells = int(sub.cell_id.nunique())
        a_rows, a_cells, a_tasks, a_families = support_profile(sub, "action_harmonized")
        p_rows, p_cells, p_tasks, p_families = support_profile(sub, "verifier_pass")
        macros.extend([
            macro(f"{p}Rows", f"{n:,}"),
            macro(f"{p}Cells", str(cells)),
            macro(f"{p}Families", str(families)),
            macro(f"{p}RawActions", str(raw_actions)),
            macro(f"{p}Actions", str(actions)),
            macro(f"{p}Passes", str(passes)),
            macro(f"{p}ActionRate", pct(actions, n)),
            macro(f"{p}PassRate", pct(passes, n)),
            macro(f"{p}Yield", pct(passes, actions)),
            macro(f"{p}ActionCells", str(a_cells)),
            macro(f"{p}ActionTasks", str(a_tasks)),
            macro(f"{p}ActionFamilies", str(a_families)),
            macro(f"{p}PassCells", str(p_cells)),
            macro(f"{p}PassTasks", str(p_tasks)),
            macro(f"{p}PassFamilies", str(p_families)),
        ])
    clean = rows[rows.stratum == "deepseek_clean"]
    extension = rows[rows.stratum == "deepseek_extension"]
    ds = pd.concat([clean, extension], ignore_index=True)
    ds_action = support_profile(ds, "action_harmonized")
    ds_pass = support_profile(ds, "verifier_pass")
    macros.extend([
        macro("DeepSeekActions", str(ds_action[0])),
        macro("DeepSeekActionCells", str(ds_action[1])),
        macro("DeepSeekActionTasks", str(ds_action[2])),
        macro("DeepSeekActionFamilies", str(ds_action[3])),
        macro("DeepSeekPasses", str(ds_pass[0])),
        macro("DeepSeekPassCells", str(ds_pass[1])),
        macro("DeepSeekPassTasks", str(ds_pass[2])),
        macro("DeepSeekPassFamilies", str(ds_pass[3])),
    ])
    macros.extend([
        macro("ContradictionRows", str(len(d["contradictions"]))),
        macro("ControlAttempts", str(len(d["controls"]))),
        macro("PreVerifierControlFailures", str(int((d["controls"].infrastructure_failure == 1).sum()))),
        macro("VerifierReachedControls", str(int((d["controls"].verifier_entered == 1).sum()))),
    ])
    controls = d["controls"]
    reached = controls[controls.verifier_entered == 1]
    for ctype, p in [("gold_reference", "Gold"), ("no_op", "NoOp"), ("reference_derived_mutant", "Mutant")]:
        sub = reached[reached.control_type == ctype]
        expected = int((sub.observed_result == sub.expected_result).sum())
        macros.extend([
            macro(f"{p}Controls", str(len(sub))),
            macro(f"{p}Expected", str(expected)),
        ])
    provider = d["provider"]
    macros.extend([
        macro("ProviderMapped", f"{int(provider.rows_mapped_to_provider_metadata.sum()):,}"),
        macro("ProviderDated", f"{int(provider.rows_with_provider_date.sum()):,}"),
        macro("RequestHashed", f"{int(provider.rows_with_request_hash.sum()):,}"),
        macro("ResponseHashed", f"{int(provider.rows_with_response_hash.sum()):,}"),
        macro("PromptHashed", f"{int(provider.rows_with_prompt_hash.sum()):,}"),
        macro("ResultHashed", f"{int(provider.rows_with_result_row_hash.sum()):,}"),
    ])
    # Important finite-population endpoints.
    opp = d["opportunity"]
    opp = opp[opp.method == "SUBSET_AVERAGED_WITHOUT_REPLACEMENT"]
    for s in STRATUM_ORDER:
        for metric, mprefix in [("action_harmonized", "ActionDiscovery"), ("verifier_pass", "PassDiscovery")]:
            for k in [1, 2, 4, 8]:
                val = float(opp[(opp.stratum == s) & (opp.metric == metric) & (opp.k == k)].discovery_rate.iloc[0])
                kname = {1: "One", 2: "Two", 4: "Four", 8: "Eight"}[k]
                macros.append(macro(f"{prefixes[s]}{mprefix}K{kname}", f"{100*val:.2f}"))
    write(NUMBERS, "\n".join(macros))


def generate_tables(d: dict[str, pd.DataFrame]) -> None:
    rows = d["rows"]
    # Study strata
    strata_rows = []
    relations = {
        "deepseek_clean": "Base task surface",
        "deepseek_extension": "Task-ID-disjoint extension",
        "glm_supplementary": "Same task IDs as clean",
    }
    for s in STRATUM_ORDER:
        sub = rows[rows.stratum == s]
        strata_rows.append(
            f"{STRATUM_LABELS[s]} & {relations[s]} & {sub.model_route.nunique()} & "
            f"{sub.task_id.nunique()} / {sub.task_family.nunique()} & "
            f"{sub.cell_id.nunique()} $\\times$ 8 & {len(sub):,} \\\\"
        )
    write(TABLES / "table_strata.tex", r"""
\begin{table}[H]
\centering
\caption{Study strata. Tasks/families reports the number of task instances and retained task-family identifiers. Each cell contains eight model executions.}
\label{tab:strata}
\small
\begin{tabularx}{\linewidth}{@{}lXrrrr@{}}
\toprule
Stratum & Task relation & Routes & Tasks/families & Cells $\times$ reps. & Rows \\
\midrule
""" + "\n".join(strata_rows) + r"""
\bottomrule
\end{tabularx}
\end{table}
""")

    # Construct audit table
    glm = rows[rows.stratum == "glm_supplementary"]
    raw_prof = support_profile(glm, "action_raw")
    harm_prof = support_profile(glm, "action_harmonized")
    delta = tuple(h-r for h, r in zip(harm_prof, raw_prof))
    write(TABLES / "table_construct_audit.tex", rf"""
\begin{{table}}[H]
\centering
\caption{{Effect of the GLM field-integrity reconciliation across support units. The twelve disputed rows remain in the immutable raw data.}}
\label{{tab:construct-audit}}
\small
\begin{{tabular}}{{@{{}}lrrrr@{{}}}}
\toprule
Action field & Positive rows & Positive cells & Positive tasks & Positive families \\
\midrule
Raw historical field & {raw_prof[0]} & {raw_prof[1]} & {raw_prof[2]} & {raw_prof[3]} \\
Harmonized construct & {harm_prof[0]} & {harm_prof[1]} & {harm_prof[2]} & {harm_prof[3]} \\
Change & {delta[0]} & {delta[1]} & {delta[2]} & {delta[3]} \\
\bottomrule
\end{{tabular}}
\end{{table}}
""")

    # Criterion table
    crit_rows = []
    for s in STRATUM_ORDER:
        sub = rows[rows.stratum == s]
        actions = int(sub.action_harmonized.sum())
        passes = int(sub.verifier_pass.sum())
        a0p1 = int(((sub.action_harmonized == 0) & (sub.verifier_pass == 1)).sum())
        a1p0 = int(((sub.action_harmonized == 1) & (sub.verifier_pass == 0)).sum())
        p_tasks = sub.loc[sub.verifier_pass == 1, "task_id"].nunique()
        crit_rows.append(
            f"{STRATUM_LABELS[s]} & {len(sub):,} & {actions} & {passes} & {a0p1} & {a1p0} & "
            f"{pct(passes, actions)}\\% & {p_tasks}/30 \\\\"
        )
    write(TABLES / "table_criterion.tex", r"""
\begin{table}[H]
\centering
\caption{Execution-level relation between the harmonized governed-action construct $A$ and verifier pass $P$. Conditional endpoint yield is $\Pr(P=1\mid A=1)$ as a descriptive fraction within each stratum.}
\label{tab:criterion}
\small
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}lrrrrrrr@{}}
\toprule
Stratum & Rows & $A{=}1$ & $P{=}1$ & $A{=}0,P{=}1$ & $A{=}1,P{=}0$ & Yield & Pass tasks \\
\midrule
""" + "\n".join(crit_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Opportunity summary
    opp = d["opportunity"]
    opp = opp[opp.method == "SUBSET_AVERAGED_WITHOUT_REPLACEMENT"]
    opp_rows = []
    for s in STRATUM_ORDER:
        for metric, label in [("action_harmonized", "Governed action"), ("verifier_pass", "Verifier pass")]:
            vals = []
            for k in [1, 2, 4, 8]:
                v = float(opp[(opp.stratum == s) & (opp.metric == metric) & (opp.k == k)].discovery_rate.iloc[0])
                vals.append(f"{100*v:.2f}\\%")
            opp_rows.append(f"{STRATUM_LABELS[s]} & {label} & " + " & ".join(vals) + r" \\")
    write(TABLES / "table_opportunity.tex", r"""
\begin{table}[H]
\centering
\caption{Observed-opportunity discovery. Each entry averages the exact probability that a size-$k$ subset of a cell's eight retained outcomes contains at least one positive observation.}
\label{tab:opportunity}
\small
\begin{tabular}{@{}llrrrr@{}}
\toprule
Stratum & Signal & $k=1$ & $k=2$ & $k=4$ & $k=8$ \\
\midrule
""" + "\n".join(opp_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Support profiles
    support_rows = []
    for s in STRATUM_ORDER:
        sub = rows[rows.stratum == s]
        for signal, label in [("action_harmonized", "Governed action"), ("verifier_pass", "Verifier pass")]:
            prof = support_profile(sub, signal)
            support_rows.append(
                f"{STRATUM_LABELS[s]} & {label} & {prof[0]} & {prof[1]}/{sub.cell_id.nunique()} & "
                f"{prof[2]}/30 & {prof[3]}/{sub.task_family.nunique()} \\\\"
            )
    write(TABLES / "table_support.tex", r"""
\begin{table}[H]
\centering
\caption{Support profiles across nested reporting units. A cell, task, or family is positive when it contains at least one positive execution row.}
\label{tab:support}
\small
\begin{tabular}{@{}llrrrr@{}}
\toprule
Stratum & Signal & Rows & Cells & Tasks & Families \\
\midrule
""" + "\n".join(support_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Controls
    controls = d["controls"]
    reached = controls[controls.verifier_entered == 1]
    control_rows = []
    labels = {
        "gold_reference": ("Gold/reference", "Pass"),
        "no_op": ("No-op", "Fail"),
        "reference_derived_mutant": ("Reference-derived mutant", "Fail"),
    }
    for ctype in ["gold_reference", "no_op", "reference_derived_mutant"]:
        sub = reached[reached.control_type == ctype]
        label, expected = labels[ctype]
        observed = int((sub.observed_result == sub.expected_result).sum())
        control_rows.append(f"{label} & {len(sub)} & {expected} & {observed}/{len(sub)} & 0 " + r"\\")
    write(TABLES / "table_controls.tex", r"""
\begin{table}[H]
\centering
\caption{Verifier-reached endpoint controls. Twelve earlier attempts that stopped at a host-mount boundary are recorded separately as infrastructure events.}
\label{tab:controls}
\small
\begin{tabular}{@{}lrrrr@{}}
\toprule
Control & Runs & Expected & Expected observed & Replay disagreement \\
\midrule
""" + "\n".join(control_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Full opportunity table
    full_rows = []
    for k in range(1, 9):
        vals = []
        for s in STRATUM_ORDER:
            for metric in ["action_harmonized", "verifier_pass"]:
                v = float(opp[(opp.stratum == s) & (opp.metric == metric) & (opp.k == k)].discovery_rate.iloc[0])
                vals.append(f"{100*v:.2f}")
        full_rows.append(f"{k} & " + " & ".join(vals) + r" \\")
    write(TABLES / "table_opportunity_full.tex", r"""
\begin{table}[H]
\centering
\caption{Full observed-opportunity discovery table (percent). $A$ denotes harmonized governed action and $P$ denotes verifier pass.}
\label{tab:opportunity-full}
\small
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}rrrrrrr@{}}
\toprule
$k$ & Clean $A$ & Clean $P$ & Extension $A$ & Extension $P$ & GLM $A$ & GLM $P$ \\
\midrule
""" + "\n".join(full_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Route/arm table
    st = d["stratified"]
    st_rows = []
    for _, r in st.iterrows():
        label = STRATUM_LABELS[str(r["pool"])]
        model = str(r["model"]).replace("deepseek-v4-", "")
        arm = "single-shot" if r["arm"] == "single_shot_v3" else "staged"
        a = int(r["action_harmonized"])
        p = int(r["answer_success"])
        st_rows.append(
            f"{label} & {tex_escape(model)} & {arm} & {int(r['rows'])} & {a} ({pct(a, int(r['rows']))}\\%) & "
            f"{p} ({pct(p, int(r['rows']))}\\%) & {pct(p, a)}\\% \\\\"
        )
    write(TABLES / "table_stratified.tex", r"""
\begin{table}[H]
\centering
\caption{Descriptive route-by-arm summaries. The historical routes and prompt arms define measurement strata; the table is not a causal comparison of methods.}
\label{tab:stratified}
\small
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}lllrrrr@{}}
\toprule
Pool & Route & Arm & Rows & Actions & Passes & Yield \\
\midrule
""" + "\n".join(st_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Provider coverage
    provider = d["provider"]
    prov_rows = []
    for _, r in provider.iterrows():
        s = str(r["stratum"])
        prov_rows.append(
            f"{STRATUM_LABELS[s]} & {int(r['total_rows'])} & {int(r['rows_mapped_to_provider_metadata'])} & "
            f"{int(r['rows_with_request_hash'])} & {int(r['rows_with_response_hash'])} & "
            f"{int(r['rows_with_prompt_hash'])} & {int(r['rows_with_result_row_hash'])}" + r" \\"
        )
    write(TABLES / "table_provider.tex", r"""
\begin{table}[H]
\centering
\caption{Coverage of retained provenance fields. Every provider-linked row contains a server date and a hashed provider call or request identifier.}
\label{tab:provider}
\small
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
Stratum & Rows & Provider-linked & Request hash & Response hash & Prompt hash & Result hash \\
\midrule
""" + "\n".join(prov_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    # Canonical result-row windows
    windows = d["windows"]
    win_rows = []
    for _, r in windows.iterrows():
        s = str(r["stratum"])
        first = str(r["min_execution_timestamp_utc"]).replace("T", " ").replace("Z", " UTC")
        last = str(r["max_execution_timestamp_utc"]).replace("T", " ").replace("Z", " UTC")
        win_rows.append(f"{STRATUM_LABELS[s]} & {first} & {last}" + r" \\" )

    write(TABLES / "table_run_windows.tex", r"""
\begin{table}[H]
\centering
\caption{Canonical result-row timestamp windows. Provider event timestamps are retained separately where available.}
\label{tab:run-windows}
\small
\begin{tabularx}{\linewidth}{@{}lXX@{}}
\toprule
Stratum & First retained row & Last retained row \\
\midrule
""" + "\n".join(win_rows) + r"""
\bottomrule
\end{tabularx}
\end{table}
""")

    # Positive task concentration
    conc = pd.read_csv(DATA / "pass_concentration_by_task.csv")
    conc = conc[conc.pass_count > 0].copy()
    conc_rows = []
    for _, r in conc.iterrows():
        conc_rows.append(
            f"{STRATUM_LABELS[str(r['stratum'])]} & \\texttt{{{tex_escape(r['task_id'])}}} & "
            f"{int(r['pass_count'])} & {int(r['action_count'])} & {100*float(r['share_of_stratum_passes']):.2f}\\% \\\\"
        )
    write(TABLES / "table_positive_tasks.tex", r"""
\begin{table}[H]
\centering
\caption{Task instances supporting verifier passes.}
\label{tab:positive-tasks}
\small
\begin{tabular}{@{}llrrr@{}}
\toprule
Stratum & Task & Pass rows & Action rows & Share of stratum passes \\
\midrule
""" + "\n".join(conc_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    d = load()
    validate(d)
    if not args.check_only:
        generate_numbers(d)
        generate_tables(d)
    print("All claim-bearing checks passed.")


if __name__ == "__main__":
    main()
