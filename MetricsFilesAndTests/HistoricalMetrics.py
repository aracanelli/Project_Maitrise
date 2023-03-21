import subprocess
import re

def get_file_history(file_path, repo_path, commit_id, parent_id):
    """
    This function gets the development history of the specified file
    """
    cmd = f"git -C {repo_path} log --all --pretty=format:'%h %an %ad %s' {commit_id}..{parent_id} -- {file_path}"
    output = subprocess.check_output(cmd, shell=True, text=True)
    commits = []
    for line in output.strip().split('\n'):
        commit_id, author, date, message = re.match(r'^(\S+)\s+(\S+)\s+(.*)\s+(.*)$', line).groups()
        commits.append({'id': commit_id, 'author': author, 'date': date, 'message': message})
    return commits

def count_revisions(file_history):
    """
    This function counts the number of revisions in the development history of the containing file
    """
    return len(file_history)

def count_lines_of_code(file_history):
    """
    This function counts the total number of lines of code changed in the development history of the containing file
    """
    total_lines_of_code = 0
    for commit in file_history:
        cmd = f"git -C {repo_path} diff --shortstat {commit['id']}^ {commit['id']} -- {file_path}"
        output = subprocess.check_output(cmd, shell=True, text=True)
        lines_added, lines_deleted = re.match(r'^\s*(\d+)\D+(\d+)\D*', output).groups()
        total_lines_of_code += int(lines_added) + int(lines_deleted)
    return total_lines_of_code

def count_logs_changed(file_history, logging_statement):
    """
    This function counts the total number of logs changed in the development history of the containing file
    """
    total_logs_changed = 0
    for commit in file_history:
        logs_changed = len(re.findall(logging_statement, commit['message']))
        total_logs_changed += logs_changed
    return total_logs_changed

def count_log_revisions(file_history, logging_statement):
    """
    This function counts the number of revisions involving log changes in the development history of the containing file
    """
    log_revisions = 0
    for commit in file_history:
        logs_changed = len(re.findall(logging_statement, commit['message']))
        if logs_changed > 0:
            log_revisions += 1
    return log_revisions