#!/usr/bin/env python3
import sys
import subprocess

if len(sys.argv) < 2:
    print("usage: {} field_name".format(sys.argv[0]))
    sys.exit(0)

field_name = sys.argv[1]
cmdline = 'grep -r -o -h --exclude-dir \"venv\" --include \"*.py\" -E \"{}\.\w+\" .'.format(field_name)
output = subprocess.run(cmdline, shell=True, stdout=subprocess.PIPE)
matchStr = str(output.stdout, 'utf-8')
matches = matchStr.split('\n')
fields = set([match.split('.')[1] for match in matches if len(match.split('.')) > 1])
fields = set(sorted(fields, key=str.lower))
for field in fields:
    print(field)
