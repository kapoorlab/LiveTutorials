
import subprocess
import re
import os

class SlurmNodeChecker:
    def __init__(self, nodes):
        
        """
        Iniitialize the node checker for SLURM nodes of the HPC
        
        Args:
           
           nodes: List of nodes to check
           
        """
        
        self.nodes = nodes 
        
    
    def run_command(self, command):
        
        """
        Execute a shell command and return output
        
        Args:
        
            command: Command to execute (string or list)
        """
        
        try:
            
            if isinstance(command, str):
                command = command.split()
                
            result = subprocess.run(
                command,
                capture_output=True,
                text =True,
                timeout=30
            )    
            
            return result.returncode == 0, result.stdout, result.stderr 
        
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            
            return False, "", str(e)
        
    
    def parse_scontrol_output(self, output):
        
        """
        Parse scontrol show node output
        
        Args:
          
          output: Raw output from scontrol
          
        Returns:
        
        dict: Parsed node information  
        """
        
        
        info = {}
        patterns = {
            'ActiveFeatures': r'ActiveFeatures=(\S+)',
            'AvailableFeatures':r'AvailableFeatures=(\S+)',
            'Gres': r'Gres=(\S+)',
            'State': r'State=(\S+)',
            'Partitions': r'Partitions=(\S+)',
            'AllocTRES': r'AllocTRES=(\S+)',
            'CfgTRES': r'CfgTRES=(\S+)',
            # configured memory inside CfgTRES: mem=2048000M or mem/2048000M
            'mem': r'mem[=/](\d+)'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                info[key] = match.group(1).strip()
            else:
                info[key] = 'N/A'

        # an idle node has no AllocTRES at all (Slurm prints 'AllocTRES='
        # with nothing after it) — that is '(none)', not missing data
        if info.get('AllocTRES') == 'N/A' and 'AllocTRES=' in output:
            info['AllocTRES'] = '(none)'

        return info
        
            
    def get_detailed_node_info(self, node):
        
        """
        Get detailed node information using scontrol
        """
        
        command = ['scontrol', 'show', 'node', node]
        
        success, output, error = self.run_command(command)
        
        if not success:
            return {
                
                'Node': node,
                'Node State': 'NOT_FOUND',
                'Reason': 'Node not found, please make ensure correct node name',
                'error': error
            }
            
        return self.parse_scontrol_output(output)    
    
    def check_all_nodes(self):
        
        """
        Check nodes for their status
        
        Returns:
        
            dict: Results organized by nodes
        """
        
        results = {
            'nodes': {},
            'summary': {
                'busy': 0,
                'drained': 0,
                'all_free_idle': 0,
            }
        }

        for node in self.nodes:
            info = self.get_detailed_node_info(node)
            results['nodes'][node] = info

            state = info.get('State', 'N/A').upper()
            if 'DRAIN' in state or 'DOWN' in state:
                results['summary']['drained'] += 1
            elif 'ALLOC' in state or 'MIXED' in state:
                results['summary']['busy'] += 1
            else:
                results['summary']['all_free_idle'] += 1

        return results

    def parse_slurm_conf(self, conf_path=None):
        """
        Parse slurm.conf and return resource-related configuration entries.

        The path defaults to the SLURM_CONF environment variable (the
        standard Slurm override) and falls back to /etc/slurm/slurm.conf.
        """
        conf_path = conf_path or os.environ.get(
            "SLURM_CONF", "/etc/slurm/slurm.conf")
        resource_keys = {
            'ClusterName', 'SelectType', 'SelectTypeParameters',
            'GresTypes', 'MaxJobCount', 'MaxArraySize',
            'DefMemPerCPU', 'MaxMemPerCPU', 'DefMemPerNode', 'MaxMemPerNode',
            'CPUFreqDef', 'CpuFreqGovernors',
            'TaskPlugin', 'PropagateResourceLimits',
            'AccountingStorageType', 'AccountingStorageTRES',
        }

        conf = {}
        try:
            with open(conf_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, _, value = line.partition('=')
                        key = key.strip()
                        if key in resource_keys:
                            conf[key] = value.strip()
        except FileNotFoundError:
            conf['error'] = f'slurm.conf not found at {conf_path}'
        except PermissionError:
            conf['error'] = f'No permission to read {conf_path}'

        return conf


def main():

    # discover the node list from sinfo — works on any cluster
    checker = SlurmNodeChecker([])
    ok, out, _ = checker.run_command(["sinfo", "-h", "-N", "-o", "%N"])
    nodes = []
    if ok:
        for line in out.splitlines():
            name = line.strip()
            if name and name not in nodes:
                nodes.append(name)
    if not nodes:
        print("No nodes found — are you on a Slurm login node?")
        return
    checker.nodes = nodes

    print(f"=== SLURM Cluster Node Status ({len(nodes)} nodes) ===\n")

    results = checker.check_all_nodes()

    for node, info in results['nodes'].items():
        print(f"Node: {node}")
        for key, val in info.items():
            print(f"  {key}: {val}")
        print()

    summary = results['summary']
    print(f"Summary — All-Free/Idle (no jobs, no issues): {summary['all_free_idle']}  Busy (jobs running): {summary['busy']}  Drained/Down: {summary['drained']}")

    print("\n=== SLURM Config Resource Info ===\n")
    conf = checker.parse_slurm_conf()
    if 'error' in conf:
        print(f"  {conf['error']}")
    else:
        for key, val in conf.items():
            print(f"  {key}: {val}")


if __name__ == '__main__':
    main()