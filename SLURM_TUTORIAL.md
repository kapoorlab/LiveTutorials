# Slurm commands for monitoring an HPC

The commands used by the HPC monitoring scripts —
[`tutorials/hpc_dashboard.py`](tutorials/hpc_dashboard.py) and the
`hpc_info` / node-checker / job-checker / accounting tooling. Every
command runs on a **login node**: none need root and none SSH into
compute nodes, the controller already knows everything.

---

## 1. How Slurm is organized

| Daemon | Role | Your window into it |
|---|---|---|
| `slurmctld` | the scheduler: every job, node, partition | `squeue`, `sinfo`, `scontrol` |
| `slurmd` (per node) | agent on each compute node; reports real free memory | `%e` of sinfo, `sstat` |
| `slurmdbd` | accounting database | `sacct`, `sacctmgr` |

Vocabulary: **partition** = queue over a set of nodes; **TRES** =
trackable resource (`cpu`, `mem`, `gres/gpu`); **job** = a reservation of
TRES.

`/etc/slurm/slurm.conf` holds the cluster's contract — the resource keys
the node checker reads:

| Key | Controls |
|---|---|
| `ClusterName` | identity |
| `SelectType`, `SelectTypeParameters` | how consumable resources are accounted (CR_Core_Memory…) |
| `GresTypes` | which GRES (gpu,mps,…) exist cluster-wide |
| `MaxJobCount`, `MaxArraySize` | scheduler limits |
| `DefMemPerCPU`, `MaxMemPerCPU`, `DefMemPerNode`, `MaxMemPerNode` | memory defaults and ceilings |
| `TaskPlugin` | process isolation (cgroup = enforced limits) |
| `AccountingStorageType`, `AccountingStorageTRES` | whether `sstat`/`sacct` collect memory at all |

If `AccountingStorageTRES` lacks `mem`, every measured-memory feature
(`sstat` MaxRSS) returns nothing — a cluster configuration, not a bug.

## 2. sinfo — node and partition inventory

The dashboard's node table (one line per node, fields below):

```bash
sinfo -h -N -o "%N|%P|%C|%m|%e|%G|%l|%T"
```

```
cpu-1|main*|8/0/0/16|2000000|150000|gpu:a100.80gb:4(S:0-1)|7-00:00:00|idle
gpu-1|gpu*|4/0/0/8|1000000|800000|gpu:h100.80gb:2|7-00:00:00|mixed
```

| Field | Meaning |
|---|---|
| `%N` | node name |
| `%P` | partition (`*` = the default partition; strip before comparing) |
| `%C` | CPUs as `allocated/idle/other/total` |
| `%m` | configured memory, **MB** |
| `%e` | **free** memory right now, **MB** — reported by the node itself |
| `%G` | GPUs (GRES) |
| `%l` | partition time limit |
| `%T` | state: `idle` `allocated` `mixed` `down` `drained` … |

Variants used by the scripts:

```bash
sinfo -h -N -o "%N|%P|%c|%m|%G|%l|%T"   # inventory without %e (hpc_info)
sinfo -N -o '%n %C %G %m %T' --noheader # quick scan: name, CPUs, GPUs, MB, state (free-node finder)
sinfo -h                                # "is the controller up?" probe
```

Reading rules:
- A node in several partitions prints **once per partition** — merge rows.
- State flags append: `allocated*` (default partition), `idle~` (powered
  off), `mixed@` (starting a job). Strip, then classify: `idle` = free;
  `allocated`/`mixed` = busy; `down`/`drained`/`draining` = needs admin.
- `real (%m) − free (%e)` is *used*, and is **not** all jobs — the kernel
  grabs spare RAM for page cache and reclaims it on demand.
- GRES strings pack type, memory, count and a sharing suffix
  (`gpu:a100.80gb:4(S:0-1)`) — parse with a regex that stops before the
  suffix, and count GPUs over **unique** nodes so nodes in two partitions
  are not double-counted.

## 3. scontrol show node — what the scheduler promised

```bash
scontrol show node cpu-1        # one node, human-readable block
scontrol show node -o           # one line per node — parse-friendly
```

```
NodeName=cpu-1 ... State=idle ... RealMemory=2000000
  CfgTRES=cpu=16,mem=2000000M,billing=20
  AllocTRES=cpu=8,mem=100G,gres/gpu=4
  Gres=gpu:a100.80gb:4(S:0-1) ...
```

| Field | Meaning |
|---|---|
| `RealMemory` | RAM installed (MB) |
| `CfgTRES` | resources configured on the node |
| `AllocTRES` | the **sum of every running job's request** — the promise |
| `State` | with the reason in `Reason=` |
| `Gres` | GPU inventory of the node |
| `ActiveFeatures`, `AvailableFeatures`, `Partitions` | what jobs may request |

Node classification used by the checker:

```
DRAIN/DOWN in state  → broken       (read Reason)
ALLOC/MIXED in state → busy
otherwise            → free
```

## 4. squeue — running and waiting jobs

The dashboard's job table:

```bash
squeue -h -t RUNNING -o "%i|%u|%j|%N|%P|%C|%m|%b|%M|%L"
```

```
10020_74|alice|train|cpu-1|main|10|100G||10:00|20:00
2001|bob|sim|gpu-[1-4]|gpu|4|51200||1:00:00|3:00:00
```

| Field | Meaning |
|---|---|
| `%i` | job id — array jobs print `arrayid_task`, e.g. `10020_74` |
| `%u` / `%j` | user / job name |
| `%N` | node list — **compressed**: `gpu-[1-4]`, `cpu-[1-3,5],admin-1` |
| `%P` | partition |
| `%C` | CPUs |
| `%m` | requested memory — *usually* plain MB, but see §5 |
| `%b` | GRES (GPUs) |
| `%M` / `%L` | runtime / time left |

Variants used by the scripts:

```bash
squeue -h -t PENDING -o "%P"              # one partition name per queued job → queue depth
squeue -h -p gpu -t RUNNING -o '%A'       # running job ids of one partition (GPU logger)
```

A pending job's reason (`squeue -o "%i %R"`) answers "why is it waiting":
`Resources`, `Priority`, `QOSMaxJobsPerUserLimit`, `ReqNodeNotAvail`.

## 5. scontrol show job — the request, exactly as stored

```bash
scontrol show job -o            # every job, one line each
scontrol show job 10020_74      # one job in full
scontrol show jobid 10020_74    # same, older spelling
```

| Output | Meaning |
|---|---|
| `MinMemory=100G` | `--mem 100G` — 100 GB **per node** |
| `MinMemory=1024c` | old per-CPU form: `--mem-per-cpu 1G` |
| `MinMemory=0 MinCPUsMemory=5G` | newer per-CPU form |
| `MinMemory=0` | the job requested **no** memory |
| `TresPerNode=gres:gpu:1` | GPUs requested |
| `RunTime=` / `StartTime=` / `EndTime=` | elapsed / reservation window |
| `Command=`, `WorkDir=` | what was submitted, from where |

**The unit trap:** `squeue %m` looks like a plain MB number and a naive
`int(mem)/1024` "works" — until a job submits `#SBATCH --mem 100G` and the
parser silently shows **0 GB for every job**. Rules: prefer
`scontrol show job -o` over `%m`; multiply a per-CPU request by the job's
CPU count; never render "no request" as `0 GB` — show the words.

## 6. sstat — live memory per running job

```bash
sstat -j 10020_74 --format=JobID,MaxRSS -P --noheadings
```

```
10020_74.batch|67108864K
```

- Reports actual RSS **from the node itself** via the controller — no SSH.
- One line **per job step** (`.batch`, `.0`, …): take the max per job id
  after stripping the suffix.
- Values arrive as `2097152K`, `1.5G`, or a bare **KB** number — note the
  unit convention difference from the scheduler fields (bare = MB there,
  bare = KB here).
- Empty output = the cluster's accounting does not collect it; show
  "unknown", never zero.

## 7. sacct — history and measured usage

```bash
# measured memory of a job (fallback when sstat returns nothing)
sacct -j 10020_74 -X -o JobID,MaxRSS --parsable2 --noheader

# a user's recent jobs (job checker)
sacct -u alice --starttime now-24hours --format=JobID --noheader -X
sacct -u alice --starttime now-24hours \
    --format=JobID,JobName,State,ExitCode,Start,End,NodeList -X -P

# usage of a partition in a date window (accounting reports)
sacct --starttime=2026-11-01 --endtime=2026-11-30 \
    --format=User,TotalCPU -a --partition=main --noheader --parsable2
sacct --starttime=2026-11-01 --endtime=2026-11-30 \
    --format=User,TotalCPU,Submit,JobID --parsable2 -a --partition=main --noheader

# job ids of a partition since a date
sacct --starttime=2026-11-01 --format=JobID -a --partition=main --noheader --parsable2
```

Options that matter: `-X` = allocation records only (skip step lines);
`-P`/`--parsable2` = `|`-separated, no headers; `-a` = all users; `-S`/
`--starttime` and `-E`/`--endtime` = the window; `now-24hours` works as a
relative start.

`State` values worth knowing: `RUNNING`, `COMPLETED`, `FAILED`,
`TIMEOUT`, `OUT_OF_MEMORY` — OOM kills land in `OUT_OF_MEMORY`, the first
place to look when a user says "my job died". Monthly and yearly reports
are the same command with a wider window, aggregated per user or
partition.

## 8. sacctmgr — who may run what

```bash
sacctmgr -nP show associations user=alice format=Account,Partition,QOS
```

Access = account + partition + QOS. A pending job with a `QOS*Limit*`
reason is limited here, not by resources. Quota and balance tools are
cluster-specific — probe with `command -v` before promising them to
users:

```bash
show-quota                       # HPC storage quota (some clusters)
sbalance                         # compute-balance / credits (some clusters)
lfs quota -uh $USER /scratch     # Lustre scratch quota
```

## 9. srun and scancel — acting through the scheduler

```bash
srun -p gpu -w gpu-1 -J gputest nvidia-smi       # one-shot GPU probe on a node
srun --nodelist=gpu-1 --gres=gpu:1 --pty bash    # interactive shell with a GPU
srun --nodelist=cpu-1 --pty bash                 # interactive shell, CPU node
scancel -n gputest -u alice                       # kill by job name and user
```

`srun -w <node> --pty bash` is the safe admin way to land on a node — it
goes through the scheduler, unlike SSH, which many clusters forbid.

## 10. Reading memory like a sysadmin

Three different numbers, all correct:

1. **real** (`sinfo %m`, `RealMemory`) — RAM installed.
2. **allocated** (`AllocTRES`, `MinMemory`) — what jobs asked for and the
   scheduler reserved. May exceed what processes actually touch.
3. **free** (`sinfo %e`) — what the node reports as available.

The gap between `real − free` and job usage is mostly **page cache**,
reclaimed automatically when jobs need it. High used + low free on an
idle node is *normal*. The alarm case is jobs that **measured** (sstat /
sacct) far more than they **requested** — OOM risk for neighbours on
nodes without cgroup enforcement.
