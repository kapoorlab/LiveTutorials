"""cluster_data.py — the fictional kapoorlabs-fr cluster used by the fake
Slurm commands in this directory.

kapoorlabs (France) runs GPU nodes named after their GPUs: h100-*, h200-*,
b200-*, plus two plain CPU nodes. Everything the tutorial scripts ask
sinfo / squeue / scontrol / sstat / sacct / sacctmgr for is answered from
this module.
"""

CLUSTER = "kapoorlabs-fr"

# node, partition, cpus (alloc/idle/other/total), mem MB, free MB,
# gres, timelimit, state, real_memory_mb, alloc_tres_mem
NODES = [
    ("h100-1", "h100*",  "16/16/0/32",  2048000,  800000, "gpu:h100.80gb:8(S:0-1)", "7-00:00:00", "mixed",      2048000, "512G"),
    ("h100-2", "h100*",  "32/0/0/32",   2048000,  400000, "gpu:h100.80gb:8(S:0-1)", "7-00:00:00", "allocated*", 2048000, "768G"),
    ("h100-3", "h100*",  "32/0/0/32",   2048000, 1900000, "gpu:h100.80gb:8(S:0-1)", "7-00:00:00", "allocated",  2048000, "1T"),
    ("h100-4", "h100*",  "0/32/0/32",   2048000, 2000000, "gpu:h100.80gb:8(S:0-1)", "7-00:00:00", "idle",       2048000, "0"),
    ("h200-1", "h200*", "24/24/0/48",  3072000,  500000, "gpu:h200.141gb:8",       "7-00:00:00", "mixed",      3072000, "1T"),
    ("h200-2", "h200*", "48/0/0/48",   3072000, 2900000, "gpu:h200.141gb:8",       "7-00:00:00", "allocated",  3072000, "1.5T"),
    ("h200-3", "h200*", "0/48/0/48",   3072000, 3050000, "gpu:h200.141gb:8",       "7-00:00:00", "idle",       3072000, "0"),
    ("b200-1", "b200*", "32/32/0/64",  4096000,  100000, "gpu:b200.192gb:8",       "14-00:00:00", "mixed",     4096000, "2T"),
    ("b200-2", "b200*", "0/64/0/64",   4096000, 4000000, "gpu:b200.192gb:8",       "14-00:00:00", "drained",    4096000, "0"),
    ("cpu-1",  "cpu*",   "64/64/0/128", 1024000,  300000, "(null)",                "3-00:00:00", "mixed",      1024000, "512G"),
    ("cpu-2",  "cpu*",   "0/128/0/128", 1024000, 1000000, "(null)",                "3-00:00:00", "idle",       1024000, "0"),
]

NODE_REASON = {"b200-2": "firmware update [admin@2026-11-20]"}

# job, user, name, nodelist, partition, cpus, requested mem (squeue %m),
# gres, runtime, time left, min_memory (scontrol), per_cpu, gpus,
# state (RUNNING/PENDING), maxrss (sstat, accounting)
JOBS = [
    ("10020_74", "varun", "pretrain",  "h100-[1-2]", "h100", 16, "100G",  "gpu:2", "10:00", "20:00", "100G",  None,   2, "RUNNING", "67108864K"),
    ("2001",     "sofie",   "finetune",  "h100-2",     "h100",  8, "51200", "gpu:1", "1:00:00", "3:00:00", "51200", None,  1, "RUNNING", "5242880K"),
    ("3003",     "varun", "sim",       "h200-1",     "h200", 12, "0",     "gpu:2", "5:00", "6:00", "0", "5120",   2, "RUNNING", "31457280K"),
    ("4004",     "sofie",   "infer",     "b200-1",     "b200", 32, "200G",  "gpu:4", "3:00", "4:00", "200G", None,   4, "RUNNING", "137438953472K"),
    ("5005",     "admin", "bench",     "h200-2",     "h200", 24, "100G",  "gpu:2", "2:00:00", "5:00:00", "100G", None,  2, "RUNNING", "52428800K"),
    ("6006",     "snooby",  "data-prep", "cpu-1",       "cpu", 32, "256G",  "",     "12:00:00", "2-00:00:00", "256G", None, 0, "RUNNING", "214748364800K"),
    ("7007",     "admin", "eval",      "cpu-1",       "cpu",  8, "0",     "",     "4:00:00", "10:00:00", "0", None, 0, "RUNNING", "10485760K"),
    ("8008",     "snooby",  "train-xl",  "b200-1",     "b200", 16, "500G",  "gpu:8", "1:00:00", "13:00:00", "500G", None, 8, "RUNNING", "241591910400K"),
]

# queue depth: partition -> pending jobs
PENDING = {"h100": 4, "h200": 2, "b200": 1, "cpu": 3}

# finished history for sacct (the job checker + accounting reports)
# job, user, name, partition, state, exitcode, total_cpu, node, maxrss
HISTORY = [
    ("9001", "varun", "pretrain",   "h100", "COMPLETED",     "0:0",     "160:00:00", "h100-1", "104857600K"),
    ("9002", "varun", "pretrain",   "h100", "FAILED",        "1:0",     "00:30:00",  "h100-1", "52428800K"),
    ("9003", "sofie",   "finetune",   "h200", "OUT_OF_MEMORY", "0:125",   "12:00:00",  "h200-1", "300647710720K"),
    ("9004", "admin", "bench",      "b200", "TIMEOUT",       "0:0",     "168:00:00", "b200-1", "104857600K"),
    ("9005", "snooby",  "data-prep",  "cpu",  "COMPLETED",     "0:0",     "96:00:00",  "cpu-1",  "53687091200K"),
    ("9006", "sofie",   "infer",      "h100", "COMPLETED",     "0:0",     "48:00:00",  "h100-2", "20971520K"),
    ("9007", "admin", "eval",       "cpu",  "COMPLETED",     "0:0",     "08:00:00",  "cpu-1",  "10485760K"),
    ("9008", "varun", "sim",        "h200", "COMPLETED",     "0:0",     "24:00:00",  "h200-1", "209715200K"),
]

# sacctmgr associations: user -> (account, partition, qos)
ASSOCIATIONS = {
    "varun": ("kapoorlabs", "ALL", "normal"),
    "sofie":   ("kapoorlabs", "ALL", "normal"),
    "admin": ("kapoorlabs-gpu", "h100,h200,b200", "high"),
    "snooby":  ("kapoorlabs-cpu", "cpu", "normal"),
}


def running_jobs():
    return [j for j in JOBS if j[13] == "RUNNING"]


def job_by_id(job_id):
    for j in JOBS:
        if j[0] == job_id:
            return j
    for j in HISTORY:
        if j[0] == job_id:
            return j
    return None
