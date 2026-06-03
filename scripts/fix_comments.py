"""Fix corrupted comment dividers in prometheus_engine.py."""
import re, sys
path = r'C:\Users\integ\Documents\Claude\Projects\Drop shipping\prometheus_engine.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = []
for line in lines:
    # Fix lines like: # ?? Some text ?????????????????????????????????????????????????
    # Replace with:   # -- Some text --------------------------------------------------
    if re.match(r'^# \?\? .+ \?+\s*$', line):
        # Extract the label text
        m = re.match(r'^# \?\? (.+?) \?+\s*$', line)
        if m:
            label = m.group(1).rstrip()
            divider = '# -- ' + label + ' ' + '-' * max(0, 75 - len(label) - 6)
            line = divider + '\n'
    # Fix lines like: # ?? Runway ML Gen-4 Turbo ? AI Video Generation ????????????????
    elif re.match(r'^# \?\? .+', line):
        m = re.match(r'^# \?\? (.+)', line)
        if m:
            label = m.group(1).strip().rstrip('?').strip()
            divider = '# -- ' + label + ' ' + '-' * max(0, 75 - len(label) - 6)
            line = divider + '\n'
    fixed.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(fixed)
print('Comment dividers fixed.')
