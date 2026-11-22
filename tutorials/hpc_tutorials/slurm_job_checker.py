#!/usr/bin/env python3
"""
SLURM Job Status Checker

This script checks job status for specific users using sacct and scontrol,
identifying failed, unkillable, or still-running jobs.

Configuration is a hydra config (conf/job_checker.yaml) backed by a
dataclass; override anything on the command line:

    python slurm_job_checker.py
    python slurm_job_checker.py users=[varun,sofie]
    python slurm_job_checker.py hours=48
    python slurm_job_checker.py output=results.txt
"""

import subprocess
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

import hydra


@dataclass
class JobCheckerConfig:
    """conf/job_checker.yaml is an instance of this dataclass."""
    users: list = field(default_factory=lambda: ["varun", "sofie"])
    hours: int = 24
    output: str = ""



class SlurmJobChecker:
    def __init__(self, users, hours=24):
        """
        Initialize the job checker.
        
        Args:
            users: List of usernames to check
            hours: Number of hours to look back (default: 24)
        """
        self.users = users
        self.hours = hours
        self.jobs_data = defaultdict(dict)
        
    def run_command(self, command):
        """
        Execute a shell command and return output.
        
        Args:
            command: Command to execute (string or list)
        
        Returns:
            tuple: (success: bool, output: str, error: str)
        """
        try:
            if isinstance(command, str):
                command = command.split()
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def get_job_ids(self, username):
        """
        Get all job IDs for a user from the last N hours.
        
        Args:
            username: Username to query
        
        Returns:
            list: List of job IDs
        """
        command = [
            'sacct',
            '-u', username,
            '--starttime', f'now-{self.hours}hours',
            '--format=JobID',
            '--noheader',
            '-X'  # Only parent jobs, not job steps
        ]
        
        success, output, error = self.run_command(command)
        
        if not success:
            print(f"Error getting jobs for {username}: {error}")
            return []
        
        # Parse job IDs
        job_ids = []
        for line in output.strip().split('\n'):
            if line.strip():
                job_ids.append(line.strip())
        
        return job_ids
    
    def get_job_basic_info(self, username):
        """
        Get basic job information using sacct.
        
        Args:
            username: Username to query
        
        Returns:
            dict: Job ID -> basic info mapping
        """
        command = [
            'sacct',
            '-u', username,
            '--starttime', f'now-{self.hours}hours',
            '--format=JobID,JobName,State,ExitCode,Start,End,NodeList',
            '-X',
            '-P'  # Parsable format
        ]
        
        success, output, error = self.run_command(command)
        
        if not success:
            print(f"Error getting job info for {username}: {error}")
            return {}
        
        jobs = {}
        lines = output.strip().split('\n')
        
        for line in lines[1:]:  # Skip header
            if not line.strip():
                continue
            
            parts = line.split('|')
            if len(parts) >= 7:
                job_id = parts[0].strip()
                jobs[job_id] = {
                    'job_name': parts[1].strip(),
                    'state': parts[2].strip(),
                    'exit_code': parts[3].strip(),
                    'start_time': parts[4].strip(),
                    'end_time': parts[5].strip(),
                    'node_list': parts[6].strip(),
                }
        
        return jobs
    
    def parse_scontrol_output(self, output):
        """
        Parse scontrol show job output.
        
        Args:
            output: Raw output from scontrol
        
        Returns:
            dict: Parsed job information
        """
        info = {}
        
        # Common patterns
        patterns = {
            'JobId': r'JobId=(\d+)',
            'JobName': r'JobName=(\S+)',
            'UserId': r'UserId=(\S+)',
            'JobState': r'JobState=(\S+)',
            'Reason': r'Reason=([^\n]+?)(?:\s+\w+=|\n|$)',
            'NodeList': r'NodeList=(\S+)',
            'ExitCode': r'ExitCode=(\S+)',
            'StartTime': r'StartTime=(\S+)',
            'EndTime': r'EndTime=(\S+)',
            'RunTime': r'RunTime=(\S+)',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                info[key] = match.group(1).strip()
            else:
                info[key] = 'N/A'
        
        return info
    
    def get_detailed_job_info(self, job_id):
        """
        Get detailed job information using scontrol.
        
        Args:
            job_id: Job ID to query
        
        Returns:
            dict: Detailed job information
        """
        command = ['scontrol', 'show', 'job', job_id]
        
        success, output, error = self.run_command(command)
        
        if not success:
            # Job might be too old or already cleaned up
            return {
                'JobId': job_id,
                'JobState': 'NOT_FOUND',
                'Reason': 'Job not found in scontrol (possibly too old)',
                'error': error
            }
        
        return self.parse_scontrol_output(output)
    
    def categorize_job(self, job_info, detailed_info):
        """
        Categorize job based on its state and details.
        
        Args:
            job_info: Basic job info from sacct
            detailed_info: Detailed info from scontrol
        
        Returns:
            dict: Categorization with flags
        """
        state = job_info.get('state', 'UNKNOWN').upper()
        detailed_state = detailed_info.get('JobState', 'UNKNOWN').upper()
        reason = detailed_info.get('Reason', '').lower()
        
        categories = {
            'is_running': False,
            'is_failed': False,
            'is_unkillable': False,
            'is_problematic': False,
            'category': 'UNKNOWN'
        }
        
        # Check if running
        if state in ['RUNNING', 'PENDING'] or detailed_state in ['RUNNING', 'PENDING']:
            categories['is_running'] = True
            categories['category'] = 'RUNNING'
        
        # Check if failed
        if state in ['FAILED', 'TIMEOUT', 'CANCELLED', 'NODE_FAIL', 'BOOT_FAIL']:
            categories['is_failed'] = True
            categories['category'] = 'FAILED'
        
        # Check for kill-related issues
        kill_patterns = ['kill', 'unkillable', 'unable to kill', 'kill task failed']
        if any(pattern in reason for pattern in kill_patterns):
            categories['is_unkillable'] = True
            categories['is_problematic'] = True
            categories['category'] = 'UNKILLABLE'
        
        # Check for other problematic states
        problem_states = ['NODE_FAIL', 'BOOT_FAIL', 'OUT_OF_MEMORY']
        if state in problem_states or detailed_state in problem_states:
            categories['is_problematic'] = True
            if categories['category'] == 'UNKNOWN':
                categories['category'] = 'PROBLEMATIC'
        
        # Check exit code
        exit_code = job_info.get('exit_code', '0:0')
        if exit_code != '0:0' and not exit_code.startswith('0:'):
            categories['is_failed'] = True
            if categories['category'] == 'UNKNOWN':
                categories['category'] = 'FAILED'
        
        # Default to completed if nothing else matches
        if categories['category'] == 'UNKNOWN' and state in ['COMPLETED']:
            categories['category'] = 'COMPLETED'
        
        return categories
    
    def check_all_users(self):
        """
        Check jobs for all users.
        
        Returns:
            dict: Results organized by user and category
        """
        results = {
            'users': {},
            'summary': {
                'total_jobs': 0,
                'running': 0,
                'failed': 0,
                'unkillable': 0,
                'problematic': 0,
                'completed': 0
            }
        }
        
        for username in self.users:
            print(f"\n{'='*70}")
            print(f"Checking user: {username}")
            print('='*70)
            
            # Get job IDs
            job_ids = self.get_job_ids(username)
            print(f"Found {len(job_ids)} jobs in last {self.hours} hours")
            
            if not job_ids:
                results['users'][username] = {
                    'jobs': [],
                    'count': 0,
                    'categories': {}
                }
                continue
            
            # Get basic info
            basic_info = self.get_job_basic_info(username)
            
            # Analyze each job
            user_results = {
                'jobs': [],
                'count': len(job_ids),
                'categories': defaultdict(list)
            }
            
            for i, job_id in enumerate(job_ids, 1):
                print(f"  [{i}/{len(job_ids)}] Checking job {job_id}...", end=' ')
                sys.stdout.flush()
                
                job_basic = basic_info.get(job_id, {})
                job_detailed = self.get_detailed_job_info(job_id)
                
                # Categorize
                categories = self.categorize_job(job_basic, job_detailed)
                
                job_data = {
                    'job_id': job_id,
                    'basic': job_basic,
                    'detailed': job_detailed,
                    'categories': categories
                }
                
                user_results['jobs'].append(job_data)
                user_results['categories'][categories['category']].append(job_data)
                
                # Update summary
                results['summary']['total_jobs'] += 1
                if categories['is_running']:
                    results['summary']['running'] += 1
                if categories['is_failed']:
                    results['summary']['failed'] += 1
                if categories['is_unkillable']:
                    results['summary']['unkillable'] += 1
                if categories['is_problematic']:
                    results['summary']['problematic'] += 1
                if categories['category'] == 'COMPLETED':
                    results['summary']['completed'] += 1
                
                print(f"[{categories['category']}]")
            
            results['users'][username] = user_results
        
        return results
    
    def print_results(self, results):
        """
        Print formatted results.
        
        Args:
            results: Results dictionary from check_all_users
        """
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        summary = results['summary']
        print(f"Total jobs checked: {summary['total_jobs']}")
        print(f"  Running:      {summary['running']}")
        print(f"  Failed:       {summary['failed']}")
        print(f"  Unkillable:   {summary['unkillable']}")
        print(f"  Problematic:  {summary['problematic']}")
        print(f"  Completed:    {summary['completed']}")
        
        # Detailed results per user
        for username, user_data in results['users'].items():
            print(f"\n{'='*70}")
            print(f"USER: {username}")
            print('='*70)
            
            if user_data['count'] == 0:
                print("  No jobs found")
                continue
            
            # Print by category
            for category in ['UNKILLABLE', 'FAILED', 'RUNNING', 'PROBLEMATIC', 'COMPLETED']:
                jobs_in_category = user_data['categories'].get(category, [])
                
                if not jobs_in_category:
                    continue
                
                print(f"\n{category} JOBS ({len(jobs_in_category)}):")
                print("-" * 70)
                
                for job_data in jobs_in_category:
                    job_id = job_data['job_id']
                    basic = job_data['basic']
                    detailed = job_data['detailed']
                    
                    print(f"\n  Job ID: {job_id}")
                    print(f"    Name:       {basic.get('job_name', detailed.get('JobName', 'N/A'))}")
                    print(f"    State:      {basic.get('state', 'N/A')}")
                    print(f"    Exit Code:  {basic.get('exit_code', 'N/A')}")
                    print(f"    Node:       {basic.get('node_list', detailed.get('NodeList', 'N/A'))}")
                    print(f"    Start:      {basic.get('start_time', 'N/A')}")
                    print(f"    End:        {basic.get('end_time', 'N/A')}")
                    
                    reason = detailed.get('Reason', 'None')
                    if reason and reason != 'None':
                        print(f"    Reason:     {reason}")
                    
                    # Highlight unkillable jobs
                    if job_data['categories']['is_unkillable']:
                        print(f"    ⚠️  WARNING: This job could not be killed!")
    
    def export_to_file(self, results, filename='job_check_results.txt'):
        """
        Export results to a text file.
        
        Args:
            results: Results dictionary
            filename: Output filename
        """
        with open(filename, 'w') as f:
            f.write(f"SLURM Job Check Results\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Users: {', '.join(self.users)}\n")
            f.write(f"Time range: Last {self.hours} hours\n")
            f.write("\n" + "="*70 + "\n")
            
            # Write summary
            f.write("SUMMARY\n")
            f.write("="*70 + "\n")
            summary = results['summary']
            f.write(f"Total jobs: {summary['total_jobs']}\n")
            f.write(f"  Running:      {summary['running']}\n")
            f.write(f"  Failed:       {summary['failed']}\n")
            f.write(f"  Unkillable:   {summary['unkillable']}\n")
            f.write(f"  Problematic:  {summary['problematic']}\n")
            f.write(f"  Completed:    {summary['completed']}\n")
            
            # Write detailed info
            for username, user_data in results['users'].items():
                f.write(f"\n{'='*70}\n")
                f.write(f"USER: {username}\n")
                f.write('='*70 + "\n")
                
                if user_data['count'] == 0:
                    f.write("  No jobs found\n")
                    continue
                
                for category in ['UNKILLABLE', 'FAILED', 'RUNNING', 'PROBLEMATIC', 'COMPLETED']:
                    jobs_in_category = user_data['categories'].get(category, [])
                    
                    if not jobs_in_category:
                        continue
                    
                    f.write(f"\n{category} JOBS ({len(jobs_in_category)}):\n")
                    f.write("-" * 70 + "\n")
                    
                    for job_data in jobs_in_category:
                        job_id = job_data['job_id']
                        basic = job_data['basic']
                        detailed = job_data['detailed']
                        
                        f.write(f"\nJob ID: {job_id}\n")
                        f.write(f"  Name:       {basic.get('job_name', detailed.get('JobName', 'N/A'))}\n")
                        f.write(f"  State:      {basic.get('state', 'N/A')}\n")
                        f.write(f"  Exit Code:  {basic.get('exit_code', 'N/A')}\n")
                        f.write(f"  Node:       {basic.get('node_list', detailed.get('NodeList', 'N/A'))}\n")
                        f.write(f"  Start:      {basic.get('start_time', 'N/A')}\n")
                        f.write(f"  End:        {basic.get('end_time', 'N/A')}\n")
                        
                        reason = detailed.get('Reason', 'None')
                        if reason and reason != 'None':
                            f.write(f"  Reason:     {reason}\n")
        
        print(f"\nResults exported to: {filename}")


@hydra.main(config_path="conf", config_name="job_checker", version_base=None)
def main(cfg: JobCheckerConfig):
    """Check SLURM job status for the configured users."""
    print("SLURM Job Status Checker")
    print("="*70)
    print(f"Users: {', '.join(cfg.users)}")
    print(f"Time range: Last {cfg.hours} hours")
    print("="*70)

    # Create checker and run
    checker = SlurmJobChecker(list(cfg.users), cfg.hours)
    results = checker.check_all_users()

    # Print results
    checker.print_results(results)

    # Export if requested
    if cfg.output:
        checker.export_to_file(results, cfg.output)

    # Return exit code based on problems found
    if results['summary']['unkillable'] > 0:
        print("\n⚠️  WARNING: Unkillable jobs detected!")
        sys.exit(1)
    elif results['summary']['problematic'] > 0:
        print("\n⚠️  WARNING: Problematic jobs detected!")
        sys.exit(1)
    else:
        print("\n✓ No critical issues found")
        sys.exit(0)


if __name__ == '__main__':
    main()
