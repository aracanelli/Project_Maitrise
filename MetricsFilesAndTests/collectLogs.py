# Import necessary libraries
import git
from git import Repo
import os
import re

# List of URLs to Java repositories on GitHub
java_repo_urls = [
    'https://github.com/agateau/pixelwheels.git',
    'https://github.com/jcarolus/android-chess.git'
]

logging_statements = [
    "System\.out\.println",
    "System\.err\.println",
    "log\.debug",
    "log\.info",
    "log\.warn",
    "log\.error",
    "log\.fatal"
]

log_regex = re.compile(r"\b(" + "|".join(logging_statements) + r")\b", re.IGNORECASE)

# Loop through each URL
for url in java_repo_urls:
    # Clone the repository using GitPython
    repo = Repo.clone_from(url, 'temp')

    # Loop through each file in the repository
    for filename in repo.tree().blobs:
        # Check if the file is a Java file
        if filename.endswith('.java'):
            # Read the file
            file = repo.tree().blobs[filename]
            file_lines = file.data_stream.read().decode('utf-8')

            # Search the file for logging statements
            if 'logger' in file_lines or 'Logger' in file_lines:
                print(f'Logging statements found in {filename}')

    # Clean up by deleting the temporary local repository
    os.remove('temp')
