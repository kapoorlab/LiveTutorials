#!/usr/bin/env python3
"""
hpc_info.py — summarise the compute resources of any Slurm HPC cluster.

Parses `sinfo` (nodes, CPUs, memory, GPUs/GRES, time limits) and reports:
  - per-partition: node count, total CPUs, GPU counts by type, memory, time limit
  - cluster GPU totals by type (counted over UNIQUE nodes, so overlapping
    partitions don't double-count)
  - your account's Slurm access (account / partition / QOS) via sacctmgr
  - optional quota / balance (show-quota, sbalance) IF those commands exist

Configuration is a hydra config (conf/hpc_info.yaml) backed by a dataclass;
override anything on the command line. Run on the login node of any Slurm
cluster:

    python hpc_info.py                     # full summary
    python hpc_info.py gpu_only=true        # only GPU partitions
    python hpc_info.py extras=true          # also try show-quota / sbalance
    python hpc_info.py user=varun           # inspect a specific user's access
"""
import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass

import hydra


@dataclass
class HpcInfoConfig:
    """conf/hpc_info.yaml is an instance of this dataclass."""
    gpu_only: bool = False
    extras: bool = False
    user: str = ""



def sh(cmd):
    """Run a command, return stdout (or '' on failure)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def parse_gpus(gres):
    """Extract [(type, count), ...] from a Slurm GRES string.

    Handles: 'gpu:A100:4', 'gpu:a100.80gb:4(S:0-1)', 'gpu:H100.80gb:8',
    'gpu:4', 'gpu:l40s:4,mps:200', '(null)'.
    """
    out = []
    if not gres or gres in ("(null)", "N/A"):
        return out
    for part in gres.split(","):
        part = part.strip()
        if not part.startswith("gpu:"):
            continue
        m = re.match(r"gpu:(?:([^:]+):)?(\d+)", part)  # \d+ stops before any (S:..)
        if m:
            gtype = (m.group(1) or "gpu").lower()
            out.append((gtype, int(m.group(2))))
    return out


def mb_to_gb(mb):
    try:
        return int(mb) / 1024.0
    except (ValueError, TypeError):
        return None


def collect():
    """Return (partitions, node_gpus) parsed from `sinfo -N`.

    partitions[name] = {nodes, cpus, gpus{type:count}, mem_gb[list], time}
    node_gpus[node]  = {type: count}   (unique nodes, for cluster totals)
    """
    # -N: one row per node per partition; '|' delimiter avoids width truncation.
    raw = sh(["sinfo", "-h", "-N", "-o", "%N|%P|%c|%m|%G|%l|%T"])
    parts = defaultdict(lambda: {"nodes": 0, "cpus": 0,
                                 "gpus": defaultdict(int), "mem_gb": [], "time": ""})
    node_gpus = {}
    for line in raw.splitlines():
        f = line.split("|")
        if len(f) < 7:
            continue
        node, part, cpus, mem, gres, tlimit, state = (x.strip() for x in f[:7])
        part = part.rstrip("*")  # '*' just marks the default partition
        gpus = parse_gpus(gres)

        p = parts[part]
        p["nodes"] += 1
        p["cpus"] += int(cpus) if cpus.isdigit() else 0
        gb = mb_to_gb(mem)
        if gb is not None:
            p["mem_gb"].append(gb)
        if not p["time"]:
            p["time"] = tlimit
        for gtype, n in gpus:
            p["gpus"][gtype] += n

        node_gpus.setdefault(node, {gtype: n for gtype, n in gpus})
    return parts, node_gpus


def fmt_gpus(gpu_dict):
    if not gpu_dict:
        return "-"
    return ", ".join(f"{n}× {t.upper()}" for t, n in sorted(gpu_dict.items()))


def fmt_mem(mem_gb):
    if not mem_gb:
        return "-"
    lo, hi = min(mem_gb), max(mem_gb)
    return f"{lo:.0f}" if abs(hi - lo) < 1 else f"{lo:.0f}-{hi:.0f}"


def print_partitions(parts, gpu_only):
    rows = []
    for name in sorted(parts):
        p = parts[name]
        if gpu_only and not p["gpus"]:
            continue
        rows.append((name, str(p["nodes"]), str(p["cpus"]),
                     fmt_gpus(p["gpus"]), fmt_mem(p["mem_gb"]), p["time"] or "-"))
    if not rows:
        print("  (no partitions found — is `sinfo` on PATH / are you on a login node?)")
        return
    head = ("PARTITION", "NODES", "CPUS", "GPUs", "MEM(GB)", "TIMELIMIT")
    widths = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    line = lambda r: "  ".join(c.ljust(widths[i]) for i, c in enumerate(r))
    print(line(head))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))


def print_cluster_totals(node_gpus):
    totals = defaultdict(int)
    for node, gd in node_gpus.items():
        for t, n in gd.items():
            totals[t] += n
    print(f"\nCluster GPU totals (unique nodes): "
          f"{sum(totals.values())} GPUs" if totals else "\nCluster GPU totals: none")
    for t, n in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}× {t.upper()}")


def print_user_access(user):
    out = sh(["sacctmgr", "-nP", "show", "associations",
              f"user={user}", "format=Account,Partition,QOS"])
    print(f"\nYour Slurm access (user={user}):")
    if not out.strip():
        print("  (sacctmgr unavailable or no associations)")
        return
    for row in out.splitlines():
        acct, part, qos = (row.split("|") + ["", "", ""])[:3]
        print(f"  account={acct or '-':<12} partition={part or 'ALL':<14} qos={qos or '-'}")


def print_extras():
    print("\nQuota / balance (if the cluster provides them):")
    found = False
    for cmd in ("show-quota", "sbalance", "lfs quota"):
        exe = cmd.split()[0]
        if shutil.which(exe):
            found = True
            print(f"\n$ {cmd}")
            print(sh(cmd.split()).rstrip() or "  (no output)")
    if not found:
        print("  none of show-quota / sbalance / lfs found on this cluster")


@hydra.main(config_path="conf", config_name="hpc_info", version_base=None)
def main(cfg: HpcInfoConfig):
    user = cfg.user or os.environ.get("USER", "")

    if not shutil.which("sinfo"):
        print("sinfo not found — run this on a Slurm login node.")
        return

    parts, node_gpus = collect()
    print("=" * 70)
    print("  PARTITIONS")
    print("=" * 70)
    print_partitions(parts, cfg.gpu_only)
    print_cluster_totals(node_gpus)
    print_user_access(user)
    if cfg.extras:
        print_extras()


if __name__ == "__main__":
    main()
