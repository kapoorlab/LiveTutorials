#!/usr/bin/env python3
"""Show available CPU and GPU nodes on the cluster."""

import subprocess
import sys

def get_node_info():
    """Get node information from sinfo."""
    cmd = "sinfo -N -o '%n %C %G %m %T' --noheader"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error running sinfo. Are you on the cluster?")
        sys.exit(1)
    return result.stdout.strip().split('\n')

def state_base(state):
    """Strip Slurm's one-character state flags: idle*, allocated~, ..."""
    return state.rstrip('*~@#$%!')

def is_usable(state):
    """A node with free CPUs is still unusable if admin took it out."""
    return not any(s in state_base(state).lower()
                   for s in ('down', 'drain', 'fail', 'maint', 'unknown', 'power'))

def parse_nodes(lines):
    """Parse sinfo output into node info."""
    nodes = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue

        node = parts[0]
        cpus = parts[1]  # allocated/idle/other/total
        gres = parts[2]
        memory = parts[3]
        state = parts[4]

        # Parse CPUs
        cpu_parts = cpus.split('/')
        allocated = int(cpu_parts[0])
        idle = int(cpu_parts[1])
        total = int(cpu_parts[3])

        # Parse GPU
        gpu = None
        gpu_count = 0
        if 'gpu:' in gres:
            gpu_part = gres.split('gpu:')[1].split(',')[0]
            if ':' in gpu_part:
                gpu_info = gpu_part.split(':')
                gpu = gpu_info[0]
                gpu_count = int(gpu_info[1].split('(')[0])

        nodes.append({
            'name': node,
            'allocated': allocated,
            'idle': idle,
            'total': total,
            'gpu': gpu,
            'gpu_count': gpu_count,
            'memory_mb': int(memory),
            'state': state
        })

    return nodes

def print_table(nodes, show_gpu_only=False):
    """Print nodes in a table format."""
    if show_gpu_only:
        nodes = [n for n in nodes if n['gpu']]

    # Sort by idle CPUs descending
    nodes = sorted(nodes, key=lambda x: x['idle'], reverse=True)

    print(f"{'Node':<12} {'Idle/Total CPUs':<16} {'GPU':<20} {'Memory':<10} {'State':<10}")
    print("-" * 70)

    for n in nodes:
        gpu_str = f"{n['gpu']} x{n['gpu_count']}" if n['gpu'] else "-"
        mem_gb = n['memory_mb'] // 1000
        print(f"{n['name']:<12} {n['idle']:>4}/{n['total']:<10} {gpu_str:<20} {mem_gb}GB{'':<5} {n['state']:<10}")

def main():
    show_gpu = '--gpu' in sys.argv or '-g' in sys.argv
    show_cpu = '--cpu' in sys.argv or '-c' in sys.argv

    if not show_gpu and not show_cpu:
        show_all = True
    else:
        show_all = False

    lines = get_node_info()
    nodes = parse_nodes(lines)

    # Nodes with free CPUs that the scheduler may actually place work on.
    # Drained/down nodes report idle CPUs too — never recommend those.
    available = [n for n in nodes if n['idle'] > 0 and is_usable(n['state'])]
    # Best first: fully idle nodes, then by number of idle CPUs.
    available.sort(key=lambda n: (state_base(n['state']) != 'idle', -n['idle']))

    if show_gpu or show_all:
        print("\n=== GPU NODES ===\n")
        gpu_nodes = [n for n in available if n['gpu']]
        if gpu_nodes:
            print_table(gpu_nodes)
        else:
            print("No GPU nodes with free slots")

    if show_cpu or show_all:
        print("\n=== CPU-ONLY NODES ===\n")
        cpu_nodes = [n for n in available if not n['gpu']]
        if cpu_nodes:
            print_table(cpu_nodes)
        else:
            print("No CPU-only nodes with free slots")

    print("\n--- Quick commands ---")
    if available:
        gpu_node = next((n for n in available if n['gpu']), None)
        cpu_node = next((n for n in available if not n['gpu']), None)

        if gpu_node:
            print(f"GPU: srun --nodelist={gpu_node['name']} --gres=gpu:1 --pty bash")
        if cpu_node:
            print(f"CPU: srun --nodelist={cpu_node['name']} --pty bash")
    print()

if __name__ == "__main__":
    main()
