"""hpc_dashboard.py — Streamlit dashboard for the live state of any Slurm HPC.

Works on any Slurm cluster: whatever partitions and nodes `sinfo` reports is
what it shows — nothing is hardcoded. Nodes and partitions are listed in
natural numeric order (gpu-1 < gpu-2 < gpu-10 < node-2 < node-10).

Three tabs (pie charts first, numbers below):
  Partitions — pie charts of per-partition CPU / memory allocation and node
               states, queue status tiles, then per-partition numbers and the
               node table.
  Nodes      — pie charts of one chosen node's memory (allocated vs free)
               and CPU allocation, then numbers and the jobs on the node
               with requested vs measured memory.
               Everything comes from Slurm itself (sinfo / scontrol / sstat
               / sacct) — no SSH to the compute nodes.
  Top jobs   — a pie of the most resource-hungry running jobs, then the
               full table.

Run on a Slurm login node (sinfo / scontrol / squeue must be on PATH):

    streamlit run hpc_dashboard.py
"""

import re
import subprocess
from collections import defaultdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

REFRESH_SECONDS = 30

TOP_JOB_COLORS = [
    "#993b3b",  # #1 top consumer (deep dull crimson)
    "#b84a4a",  # #2 (medium dull red)
    "#c96565",  # #3 (muted rose)
    "#a85848",  # #4 (warm rust)
    "#854848",  # #5 (dusky maroon)
]

# ---------------------------------------------------------------------------
# Chart palette — muted, dark-mode-native colors with low glare:
#   dull crimson = allocated / in use, muted sage/emerald = free,
#   deep slate = the unattributable rest.
# ---------------------------------------------------------------------------
SURFACE = "#0e1117"   # matches Streamlit dark background for clean slice gaps
INK = "#f3f4f6"       # crisp off-white for chart titles
INK2 = "#9ca3af"      # soft cool-gray for subplot titles, legends & center text
MUTED = "#6b7280"     # subtle labels
GRID = "#262b36"      # deep slate-gray for "other / unaccounted" remainder slice
GOOD = "#2e8b68"      # dull sage-emerald: free / available
CRIT = "#b84a4a"      # dull terracotta-crimson: allocated / in use


# ---------------------------------------------------------------------------
# Slurm data layer (cached so the page does not hammer the scheduler)
# ---------------------------------------------------------------------------
def run_slurm_command(cmd, timeout=60):
    """Run a command, return stdout (or '' on failure)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def parse_gres(gres):
    """[(type, count), ...] from a GRES string.

    Handles 'gpu:A100:4', 'gpu:a100.80gb:4(S:0-1)', 'gpu:H100.80gb:8',
    'gpu:4', 'gpu:1,gpu:B200:2', '(null)'.
    """
    out = []
    if not gres or gres in ("(null)", "N/A", ""):
        return out
    for part in gres.split(","):
        part = part.strip()
        if not part.startswith("gpu:"):
            continue
        m = re.match(r"gpu:(?:([^:]+):)?(\d+)", part)
        if m:
            gtype = (m.group(1) or "gpu").lower()
            out.append((gtype, int(m.group(2))))
    return out


def tres_value(tres, field):
    """'cpu=30,mem=550G,gres/gpu=4' -> value for `field` (mem -> '550G')."""
    if not tres or tres in ("(null)", "N/A"):
        return None
    for part in tres.split(","):
        key, _, value = part.partition("=")
        if key.strip() == field:
            return value.strip()
    return None


def mem_str_to_gb(text):
    """'550G' / '512000M' / '2T' -> GB (float), or None if unparseable.

    A bare number is read as KB (sstat / sacct MaxRSS convention).
    """
    if not text:
        return None
    m = re.match(r"^([\d.]+)([KMGT]?)i?B?$", text.strip())
    if not m:
        return None
    value = float(m.group(1))
    factor = {"": 1 / (1024 ** 2), "K": 1 / (1024 ** 2),
              "M": 1 / 1024, "G": 1.0, "T": 1024.0}[m.group(2)]
    return value * factor


def slurm_mem_field_to_gb(text):
    """squeue %m / scontrol MinMemory value -> GB, or None when unset.

    Handles '100G', '51200M', '2T' and bare MB numbers ('51200'), plus
    '0', '(null)' and '' which all mean "no --mem requested".
    """
    if text is None:
        return None
    t = str(text).strip()
    if t in ("", "0", "(null)", "N/A", "unset"):
        return None
    m = re.match(r"^([\d.]+)\s*([KMGT]?)(?:i?B)?$", t, re.IGNORECASE)
    if not m:
        return None
    value = float(m.group(1))
    factor = {"": 1 / 1024.0, "K": 1 / (1024 ** 2),
              "M": 1 / 1024.0, "G": 1.0, "T": 1024.0}[m.group(2).upper()]
    return value * factor


def scontrol_min_memory(line):
    """(node_mem_gb, per_cpu_gb) from one `scontrol show job -o` line.

    MinMemory can be '100G' (per node), '1024c' (per CPU, old format) or
    '0' (unset); MinCPUsMemory is the per-CPU form in newer Slurm.
    """
    node_mem, per_cpu = None, None

    mm = re.search(r"MinMemory=(\S+)", line)
    if mm:
        t = mm.group(1)
        if t.endswith("c"):
            per_cpu = slurm_mem_field_to_gb(t[:-1])
        else:
            node_mem = slurm_mem_field_to_gb(t)

    mc = re.search(r"MinCPUsMemory=(\S+)", line)
    if mc:
        per_cpu = slurm_mem_field_to_gb(mc.group(1)) or per_cpu

    return node_mem, per_cpu


def mb_to_gb(mb):
    try:
        return int(mb) / 1024.0
    except (ValueError, TypeError):
        return None


def gpus_str(gpu_dict):
    if not gpu_dict:
        return "-"
    return ", ".join(f"{n}× {t.upper()}" for t, n in sorted(gpu_dict.items()))


def by_node(item):
    return item["node"]


def by_count_desc(item):
    return -item[1]


def node_sort_key(name):
    """Natural numeric order for any node name: gpu-1 < gpu-2 < gpu-10."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def _split_hostlist(hostlist):
    """Split on top-level commas only — commas inside [...] are ranges."""
    parts, depth, cur = [], 0, ""
    for ch in hostlist:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return parts


def expand_hostlist(hostlist):
    """Expand a Slurm hostlist: 'node-[1-3,5],gpu-1' -> individual names."""
    hosts = []
    for part in _split_hostlist(hostlist):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*)\[(.*)\]$", part)
        if not m:
            hosts.append(part)
            continue
        prefix, ranges = m.group(1), m.group(2)
        for r in ranges.split(","):
            if "-" in r:
                a, b = r.split("-")
                for i in range(int(a), int(b) + 1):
                    hosts.append(f"{prefix}{str(i).zfill(len(a))}")
            elif r:
                hosts.append(prefix + r)
    return hosts


def state_group(state):
    """Normalize an sinfo state to allocated / mixed / idle / other."""
    s = re.split(r"[*~#%@+]", state)[0]
    return s if s in ("allocated", "mixed", "idle") else "other"


@st.cache_data(ttl=REFRESH_SECONDS)
def collect_nodes():
    """One dict per node: CPUs, memory (real / allocated / free), GPUs, state.

    sinfo gives per-node CPUs ('alloc/idle/other/total'), config memory and
    FREE physical memory (%e — the number that decides how slow a new job
    runs); scontrol gives the ALLOCATED memory (AllocTRES mem=...) — what
    the jobs asked for with --mem and the scheduler reserved for them.
    """
    raw = run_slurm_command(["sinfo", "-h", "-N", "-o", "%N|%P|%C|%m|%e|%G|%l|%T"])
    scontrol_raw = run_slurm_command(["scontrol", "show", "node", "-o"])

    alloc_mem = {}
    for line in scontrol_raw.splitlines():
        node_match = re.search(r"NodeName=(\S+)", line)
        if not node_match:
            continue
        node = node_match.group(1)
        alloc_mem[node] = mem_str_to_gb(_tres_mem(line))

    nodes = []
    seen = set()
    for line in raw.splitlines():
        f = line.split("|")
        if len(f) < 8:
            continue
        node, part, cpus, mem, free, gres, tlimit, state = (x.strip() for x in f[:8])
        part = part.rstrip("*")
        if node in seen:
            # node appears once per partition — merge partitions into the row
            for existing in nodes:
                if existing["node"] == node and part not in existing["partitions"]:
                    existing["partitions"].append(part)
            continue
        seen.add(node)
        cpu_parts = cpus.split("/")
        alloc = int(cpu_parts[0]) if cpu_parts[0].isdigit() else 0
        idle = int(cpu_parts[1]) if cpu_parts[1].isdigit() else 0
        total = int(cpu_parts[3]) if len(cpu_parts) > 3 and cpu_parts[3].isdigit() else 0
        nodes.append({
            "node": node,
            "partitions": [part],
            "state": state,
            "state_group": state_group(state),
            "cpus_alloc": alloc,
            "cpus_idle": idle,
            "cpus_total": total,
            "mem_real_gb": mb_to_gb(mem),
            "mem_free_gb": mb_to_gb(free),
            "mem_alloc_gb": alloc_mem.get(node),
            "gpus": dict(parse_gres(gres)),
            "timelimit": tlimit or "-",
        })
    return nodes


def _tres_mem(scontrol_line):
    """mem=... out of the AllocTRES=... inside a one-line scontrol node row."""
    tres_match = re.search(r"AllocTRES=(\S+)", scontrol_line)
    if not tres_match:
        return None
    return tres_value(tres_match.group(1), "mem")


@st.cache_data(ttl=REFRESH_SECONDS)
def collect_job_mem_scontrol():
    """JobId -> {'mem_gb': --mem per node, 'per_cpu_gb': --mem-per-cpu}."""
    raw = run_slurm_command(["scontrol", "show", "job", "-o"])
    out = {}
    for line in raw.splitlines():
        m = re.search(r"JobId=(\S+)", line)
        if not m:
            continue
        node_mem, per_cpu = scontrol_min_memory(line)
        out[m.group(1)] = {"mem_gb": node_mem, "per_cpu_gb": per_cpu}
    return out


def job_mem_fields(job_id, squeue_mem_text, cpus, scontrol_mem):
    """(mem_gb numeric, mem_str display) for one job."""
    ctrl = scontrol_mem.get(job_id) or {}
    node_mem = ctrl.get("mem_gb")
    per_cpu = ctrl.get("per_cpu_gb")
    if node_mem is None:
        node_mem = slurm_mem_field_to_gb(squeue_mem_text)
    if node_mem is not None:
        return node_mem, f"{node_mem:,.0f} GB"
    if per_cpu is not None:
        total = per_cpu * cpus
        return total, f"{per_cpu:,.0f} GB/CPU × {cpus} = {total:,.0f} GB"
    return 0.0, "no --mem requested"


@st.cache_data(ttl=REFRESH_SECONDS)
def collect_jobs():
    """All RUNNING jobs: id, user, name, node, partition, CPUs, requested memory, GPUs, runtime."""
    raw = run_slurm_command(["squeue", "-h", "-t", "RUNNING",
              "-o", "%i|%u|%j|%N|%P|%C|%m|%b|%M|%L"])
    scontrol_mem = collect_job_mem_scontrol()
    jobs = []
    for line in raw.splitlines():
        f = line.split("|")
        if len(f) < 10:
            continue
        job_id, user, name, node, part, cpus, mem, gres, runtime, left = (
            x.strip() for x in f[:10])
        part = part.rstrip("*")
        cpus_n = int(cpus) if cpus.isdigit() else 0
        mem_gb, mem_str = job_mem_fields(job_id, mem, cpus_n, scontrol_mem)
        jobs.append({
            "job": job_id,
            "user": user,
            "name": name,
            "node": node,
            "partition": part,
            "cpus": cpus_n,
            "mem_gb": mem_gb,
            "mem_str": mem_str,
            "gpus": dict(parse_gres(gres)),
            "gpu_str": gpus_str(dict(parse_gres(gres))),
            "runtime": runtime,
            "time_left": left,
        })
    return jobs


@st.cache_data(ttl=REFRESH_SECONDS)
def count_pending_jobs():
    """Partition -> number of PENDING jobs."""
    raw = run_slurm_command(["squeue", "-h", "-t", "PENDING", "-o", "%P"])
    counts = defaultdict(int)
    for line in raw.splitlines():
        p = line.strip().rstrip("*")
        if p:
            counts[p] += 1
    return dict(counts)


@st.cache_data(ttl=REFRESH_SECONDS)
def get_actual_job_memory(jobs):
    """Actual RSS memory per running job, from Slurm accounting — no SSH."""
    job_memory = {}
    if not jobs:
        return job_memory

    job_ids = ",".join(str(j["job"]) for j in jobs)
    raw_sstat = run_slurm_command(
        ["sstat", "-j", job_ids, "--format=JobID,MaxRSS", "-P", "--noheadings"])
    for line in raw_sstat.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            job_id = parts[0].strip().split(".")[0]  # Remove .batch suffix
            max_rss = parts[1].strip()
            if max_rss and max_rss not in ("", "(null)"):
                mem_gb = mem_str_to_gb(max_rss)
                if mem_gb is not None:
                    job_memory[job_id] = max(job_memory.get(job_id, 0), mem_gb)

    missing = [j for j in jobs if str(j["job"]) not in job_memory]
    if missing:
        ids = ",".join(str(j["job"]) for j in missing)
        raw_sacct = run_slurm_command(
            ["sacct", "-j", ids, "-X", "-o", "JobID,MaxRSS",
             "--parsable2", "--noheader"])
        for line in raw_sacct.splitlines():
            parts = line.split("|")
            if len(parts) >= 2:
                job_id = parts[0].strip().split(".")[0]
                max_rss = parts[1].strip()
                if max_rss and max_rss not in ("", "0", "(null)"):
                    mem_gb = mem_str_to_gb(max_rss)
                    if mem_gb is not None:
                        job_memory[job_id] = max(job_memory.get(job_id, 0), mem_gb)

    return job_memory


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def _pie_layout(fig, title, height):
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=INK), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  size=12, color=INK2),
        margin=dict(l=8, r=8, t=48, b=8, pad=4),
        height=height,
        showlegend=False,
        uniformtext=dict(minsize=10, mode="hide"),
    )
    fig.update_annotations(font=dict(size=12, color=INK2))


def pie_grid(specs, title, slice_names, slice_colors, cols=None, unit=""):
    """Grid of small donut pies: specs = [(label, [values])]."""
    if not specs:
        specs = [("no data", [1])]
    n = len(specs)
    if cols is None:
        cols = min(4, n)
    cols = max(1, min(cols, n))
    rows = (n + cols - 1) // cols
    fig = make_subplots(
        rows=rows, cols=cols,
        specs=[[{"type": "domain"}] * cols for _ in range(rows)],
        subplot_titles=[label for label, _ in specs],
        vertical_spacing=0.14 / rows)
    unit_suffix = f" {unit}" if unit else ""
    for i, (_, values) in enumerate(specs):
        r, c = divmod(i, cols)
        fig.add_trace(go.Pie(
            values=values, labels=slice_names, sort=False,
            legendgroup="slices",
            marker=dict(colors=slice_colors[:len(values)],
                        line=dict(width=2, color=SURFACE)),
            hole=0.48,
            textposition="inside",
            insidetextfont=dict(color="#f9fafb", size=11),
            texttemplate="%{percent:.0%}",
            hovertemplate="%{label}: %{value:,.0f}" + unit_suffix +
                          " (%{percent:.0%})<extra></extra>",
            showlegend=(i == 0)), row=r + 1, col=c + 1)

    _pie_layout(fig, title, height=max(300, 320 * rows + 70))
    fig.update_layout(
        legend=dict(orientation="h", yanchor="top", y=-0.05, x=0,
                    xanchor="left", font=dict(size=11, color=INK2)),
        margin=dict(l=8, r=8, t=48, b=56, pad=4))
    return fig


def allocation_pies(rows, title, cols=None, unit=""):
    """[(label, used, total)] -> one donut per label: allocated (red) vs free."""
    specs = [(label, [max(0, used), max(0, total - used)])
             for label, used, total in rows]
    return pie_grid(specs, title, ("allocated", "free"),
                    (CRIT, GOOD), cols=cols, unit=unit)


def share_pie(labels, values, title, center_top="", center_sub="",
              colors=None, unit=""):
    """Large telemetry-style donut with right-aligned legend and compact center KPI."""
    unit_suffix = f" {unit}" if unit else ""
    fig = go.Figure(go.Pie(
        values=values,
        labels=labels,
        sort=False,
        domain=dict(x=[0.0, 0.64], y=[0.06, 0.94]),
        marker=dict(
            colors=(colors or [CRIT] * len(labels))[:len(labels)],
            line=dict(width=3, color=SURFACE),
        ),
        hole=0.66,
        textposition="inside",
        insidetextfont=dict(color="#f9fafb", size=11),
        texttemplate="%{percent:.0%}",
        hovertemplate="<b>%{label}</b><br>%{value:,.0f}" + unit_suffix +
                      " (%{percent:.0%})<extra></extra>",
        showlegend=True,
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=INK), x=0, y=0.97),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            size=12,
            color=INK2,
        ),
        margin=dict(l=4, r=4, t=44, b=12),
        height=330,
        uniformtext=dict(minsize=10, mode="hide"),
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=0.68,
            font=dict(size=12, color=INK),
            itemsizing="constant",
        ),
    )

    if center_top:
        center_html = (
            f"<b style='font-size:15px;color:{INK}'>{center_top}</b>"
            + (f"<br><span style='font-size:11px;color:{INK2}'>{center_sub}</span>"
               if center_sub else "")
        )
        # Pin annotation to exact horizontal center of domain [0.0, 0.64] -> x=0.32
        fig.add_annotation(
            text=center_html,
            x=0.32,
            y=0.50,
            xref="paper",
            yref="paper",
            xanchor="center",
            yanchor="middle",
            showarrow=False,
        )

    return fig


def section(title, caption=None):
    """A cleanly separated section header used across all tabs."""
    st.divider()
    st.subheader(title)
    if caption:
        st.caption(caption)


def queue_tiles(part_names, pending, running):
    """One status tile per partition queue, in a row."""
    def status(q, r):
        if q <= 0:
            return "#161b22", "#9ca3af", "free", "1px solid #30363d"
        if q <= max(r, 1):
            return GOOD, "#f9fafb", "not busy", "none"
        return CRIT, "#f9fafb", "busy", "none"

    items = [(p, *status(pending.get(p, 0), running.get(p, 0)))
             for p in part_names]
    per_row = 6
    for start in range(0, len(items), per_row):
        chunk = items[start:start + per_row]
        cols = st.columns(len(chunk))
        for col, (name, bg, fg, label, border) in zip(cols, chunk):
            col.markdown(
                f'<div style="background-color:{bg};color:{fg};'
                f'border:{border};padding:14px 8px;border-radius:8px;'
                f'text-align:center;font-weight:600;">{name}'
                f'<div style="font-weight:400;font-size:13px;'
                f'margin-top:4px;">{label}</div></div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    st.set_page_config(page_title="HPC Resource Dashboard", layout="wide")
    st.title("HPC Resource Dashboard")

    left, right = st.columns([3, 1])
    with left:
        st.caption("live from slurm")
    with right:
        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()

    if not run_slurm_command(["sinfo", "-h"]):
        st.error("sinfo not found — run this app on a Slurm login node.")
        st.stop()

    nodes = collect_nodes()
    jobs = collect_jobs()
    actual_mem = get_actual_job_memory(jobs)

    # -----------------------------------------------------------------------
    # Tab 1 — partition overview (charts first, numbers below)
    # -----------------------------------------------------------------------
    tab_partitions, tab_nodes, tab_jobs = st.tabs(
        ["Partitions", "Nodes", "Top jobs"])

    with tab_partitions:
        partitions = defaultdict(list)
        for n in nodes:
            for p in n["partitions"]:
                partitions[p].append(n)

        gpu_totals = defaultdict(int)
        for n in nodes:
            for t, count in n["gpus"].items():
                gpu_totals[t] += count

        part_names = sorted(partitions)

        # ---- charts ----
        st.subheader("Partition health")
        st.caption("red = allocated / in use, green = free")

        cpu_rows, mem_rows = [], []
        state_specs = []
        running_counts = {}
        pending = count_pending_jobs()
        for pname in part_names:
            p_nodes = partitions[pname]
            cpus_total = sum(n["cpus_total"] for n in p_nodes)
            cpus_alloc = sum(n["cpus_alloc"] for n in p_nodes)
            mem_real = sum(n["mem_real_gb"] or 0 for n in p_nodes)
            mem_alloc = sum(n["mem_alloc_gb"] or 0 for n in p_nodes)
            cpu_rows.append((pname, cpus_alloc, cpus_total))
            mem_rows.append((pname, mem_alloc, mem_real))
            n_idle = sum(1 for n in p_nodes if n["state_group"] == "idle")
            # binary: a node is either free (idle) or allocated (anything
            # with jobs on it, including partially-allocated mixed nodes)
            state_specs.append((pname, [len(p_nodes) - n_idle, n_idle]))
            running_counts[pname] = sum(1 for j in jobs
                                        if j["partition"] == pname)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(allocation_pies(cpu_rows, "CPUs allocated",
                                            cols=2, unit="CPUs"),
                            width="stretch")
        with c2:
            st.plotly_chart(allocation_pies(mem_rows, "Memory allocated",
                                            cols=2, unit="GB"),
                            width="stretch")

        st.plotly_chart(pie_grid(state_specs, "Nodes by state",
                                 ("allocated", "free"),
                                 (CRIT, GOOD), cols=4, unit="nodes"),
                        width="stretch")

        st.caption("queue status — red = busy, green = not busy, dark = free")
        queue_tiles(part_names, pending, running_counts)

        # ---- numbers below ----
        section("Partition details", "numbers behind the charts above")

        for pname in part_names:
            p_nodes = partitions[pname]
            cpus_total = sum(n["cpus_total"] for n in p_nodes)
            cpus_alloc = sum(n["cpus_alloc"] for n in p_nodes)
            mem_real = sum(n["mem_real_gb"] or 0 for n in p_nodes)
            mem_alloc = sum(n["mem_alloc_gb"] or 0 for n in p_nodes)
            p_gpus = defaultdict(int)
            for n in p_nodes:
                for t, count in n["gpus"].items():
                    p_gpus[t] += count

            st.subheader(f"Partition {pname}")

            c1, c2, c3 = st.columns(3)
            c1.metric("Nodes", len(p_nodes))
            c2.metric("CPUs", f"{cpus_alloc} / {cpus_total}")
            c3.metric("Memory", f"{mem_alloc:,.0f} / {mem_real:,.0f} GB")

            with st.expander("GPUs", expanded=False):
                st.write(gpus_str(dict(p_gpus)))

            rows = []
            for n in sorted(p_nodes, key=by_node):
                rows.append({
                    "node": n["node"],
                    "state": n["state"],
                    "CPUs": f"{n['cpus_alloc']}/{n['cpus_total']}",
                    "mem real (GB)": f"{(n['mem_real_gb'] or 0):.0f}",
                    "mem alloc (GB)": f"{n['mem_alloc_gb'] or 0:.0f}",
                    "mem free (GB)": f"{n['mem_free_gb'] or 0:.0f}",
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

            tight = [n["node"] for n in p_nodes
                     if n["mem_free_gb"] is not None and n["mem_real_gb"]
                     and n["mem_free_gb"] < 0.1 * n["mem_real_gb"]]
            if tight:
                st.warning(f"nearly full node(s): {', '.join(tight)} — jobs placed "
                           "here get their allocation on paper but the physical "
                           "memory is already taken, so they run slow.")

        section("Cluster GPU totals (unique nodes)")
        if gpu_totals:
            with st.expander("GPUs", expanded=False):
                for t, count in sorted(gpu_totals.items(), key=by_count_desc):
                    st.write(f"{count}× {t.upper()}")
        else:
            st.write("no GPUs found")

        if actual_mem:
            section("Memory eaters (measured vs requested)")
            eater_rows = []
            for job_id, actual_gb in sorted(actual_mem.items(),
                                            key=lambda x: -x[1])[:15]:
                job = next((j for j in jobs
                            if str(j["job"]) == str(job_id)), None)
                if job:
                    reported = job["mem_gb"]
                    if actual_gb > reported * 2 or reported == 0:
                        eater_rows.append({
                            "job": job_id,
                            "user": job["user"],
                            "name": job["name"],
                            "node": job["node"],
                            "requested": job["mem_str"],
                            "measured (GB)": f"{actual_gb:,.0f}",
                            "ratio": f"{actual_gb / reported:.0f}x"
                                     if reported > 0 else "N/A",
                        })
            if eater_rows:
                st.dataframe(pd.DataFrame(eater_rows), width="stretch",
                             hide_index=True)
                st.caption("jobs using 2x or more of their requested memory, "
                           "or jobs that requested none")

    # -----------------------------------------------------------------------
    # Tab 2 — node detail (charts first, numbers below)
    # -----------------------------------------------------------------------
    with tab_nodes:
        node_names = sorted({n["node"] for n in nodes}, key=node_sort_key)
        chosen = st.selectbox("Node", node_names)
        info = next(n for n in nodes if n["node"] == chosen)
        node_jobs = [j for j in jobs if chosen in expand_hostlist(j["node"])]

        # ---- charts side by side ----
        st.subheader(f"{chosen}")

        real_gb = info["mem_real_gb"] or 0
        free_gb = info["mem_free_gb"] or 0
        alloc_gb = info["mem_alloc_gb"] or 0
        pc1, pc2 = st.columns(2)
        with pc1:
            with st.container(border=True):
                st.plotly_chart(share_pie(
                    ["allocated", "free", "unaccounted"],
                    [alloc_gb, free_gb, max(0.0, real_gb - alloc_gb - free_gb)],
                    f"{chosen} — Memory",
                    center_top=f"{real_gb:,.0f} GB",
                    center_sub="total",
                    colors=[CRIT, GOOD, GRID], unit="GB"),
                    width="stretch")
        with pc2:
            with st.container(border=True):
                cpu_other = max(0, info["cpus_total"] - info["cpus_alloc"]
                                - info["cpus_idle"])
                st.plotly_chart(share_pie(
                    ["allocated", "idle", "other"],
                    [info["cpus_alloc"], info["cpus_idle"], cpu_other],
                    f"{chosen} — CPUs",
                    center_top=f"{info['cpus_total']}",
                    center_sub="CPUs",
                    colors=[CRIT, GOOD, GRID], unit="CPUs"),
                    width="stretch")
        st.caption("red = allocated, green = free, slate = unaccounted "
                   "(allocated + free vs the real total)")

        # ---- numbers below ----
        section("Details")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("State", info["state"])
        c2.metric("CPUs", f"{info['cpus_alloc']} / {info['cpus_total']}")
        c3.metric("Mem Allocated", f"{alloc_gb:,.0f} / {real_gb:,.0f} GB")
        c4.metric("Mem Free", f"{free_gb:,.0f} GB")

        with st.expander("GPUs & time limit", expanded=False):
            st.write(f"**GPUs:** {gpus_str(info['gpus'])} · "
                     f"**Max time:** {info['timelimit']}")

        section(f"Running jobs on {chosen}")
        if node_jobs:
            n_job_rows = []
            for j in sorted(node_jobs, key=lambda x: -x["cpus"]):
                act_gb = actual_mem.get(str(j["job"]))
                n_job_rows.append({
                    "job": j["job"],
                    "user": j["user"],
                    "name": j["name"],
                    "CPUs": j["cpus"],
                    "GPUs": j["gpu_str"],
                    "mem requested": j["mem_str"],
                    "mem measured (GB)": f"{act_gb:,.1f}" if act_gb is not None else "-",
                    "runtime": j["runtime"],
                    "time left": j["time_left"],
                })
            st.dataframe(pd.DataFrame(n_job_rows), width="stretch",
                         hide_index=True)
        else:
            st.info(f"No running jobs currently assigned to {chosen}.")

    # -----------------------------------------------------------------------
    # Tab 3 — top jobs (pie of top consumers first, full table below)
    # -----------------------------------------------------------------------
    with tab_jobs:
        st.subheader("Most resource-hungry running jobs")

        if not jobs:
            st.info("No running jobs in the monitored partitions.")
        else:
            metric_choice = st.radio(
                "Rank top 5 jobs by",
                ["CPUs", "Requested Memory (GB)", "Measured Memory (GB)"],
                horizontal=True,
            )

            def job_metric_val(j):
                if metric_choice == "CPUs":
                    return j["cpus"]
                if metric_choice == "Requested Memory (GB)":
                    return j["mem_gb"]
                return actual_mem.get(str(j["job"]), 0.0)

            ranked = sorted(jobs, key=job_metric_val, reverse=True)
            top_n = ranked[:5]
            rest = ranked[5:]

            labels = [f"#{idx + 1} {j['user']} ({j['job']})"
                      for idx, j in enumerate(top_n)]
            values = [job_metric_val(j) for j in top_n]

            rest_total = sum(job_metric_val(j) for j in rest)
            if rest_total > 0:
                labels.append(f"Other jobs ({len(rest)})")
                values.append(rest_total)

            total_val = sum(values)
            unit = "CPUs" if metric_choice == "CPUs" else "GB"
            slice_colors = TOP_JOB_COLORS[:len(top_n)] + ([GRID] if rest_total > 0 else [])

            if total_val > 0:
                with st.container(border=True):
                    st.plotly_chart(
                        share_pie(
                            labels,
                            values,
                            f"Top 5 jobs share of active {metric_choice.lower()}",
                            center_top=f"{total_val:,.0f}",
                            center_sub=unit,
                            colors=slice_colors,
                            unit=unit,
                        ),
                        width="stretch",
                    )
            else:
                st.info(f"No non-zero usage recorded for {metric_choice.lower()}.")

            section("All running jobs", "sorted by node name, then CPUs")
            sorted_jobs = sorted(
                jobs,
                key=lambda j: (node_sort_key(j["node"]), -j["cpus"]),
            )
            all_rows = []
            for j in sorted_jobs:
                act_gb = actual_mem.get(str(j["job"]))
                all_rows.append({
                    "node": j["node"],
                    "partition": j["partition"],
                    "job": j["job"],
                    "user": j["user"],
                    "name": j["name"],
                    "CPUs": j["cpus"],
                    "GPUs": j["gpu_str"],
                    "mem requested": j["mem_str"],
                    "mem measured (GB)": f"{act_gb:,.1f}" if act_gb is not None else "-",
                    "runtime": j["runtime"],
                    "time left": j["time_left"],
                })
            st.dataframe(pd.DataFrame(all_rows), width="stretch",
                         hide_index=True)
