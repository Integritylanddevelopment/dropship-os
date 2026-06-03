"""Remove all emojis from prometheus_engine.py — Windows cp1252 fix."""
path = r'C:\Users\integ\Documents\Claude\Projects\Drop shipping\prometheus_engine.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

replacements = [
    ('\U0001f4cb', '[LIST]'),
    ('✅', '[OK]'),
    ('⚠️', '[WARN]'),
    ('⚠', '[WARN]'),
    ('❌', '[ERROR]'),
    ('\U0001f3ac', '[VIDEO]'),
    ('\U0001f4dd', '[SCRIPT]'),
    ('\U0001f3a4', '[MIC]'),
    ('\U0001f39a️', '[MIX]'),
    ('\U0001f39a', '[MIX]'),
    ('✂️', '[CUT]'),
    ('✂', '[CUT]'),
    ('\U0001f525', '[FIRE]'),
    ('\U0001f4c1', '[FOLDER]'),
    ('\U0001f3b5', '[MUSIC]'),
    ('\U0001f4c4', '[FILE]'),
    ('\U0001f4ca', '[CHART]'),
    ('\U0001f4be', '[SAVE]'),
    ('\U0001f517', '[LINK]'),
]
for emoji, text in replacements:
    code = code.replace(emoji, text)

# Catch anything remaining that cp1252 can't handle
lines = code.split('\n')
fixed = []
for line in lines:
    try:
        line.encode('cp1252')
        fixed.append(line)
    except UnicodeEncodeError:
        safe = ''.join(c if ord(c) < 128 else '?' for c in line)
        fixed.append(safe)
        print(f'Sanitized line: {safe[:80]}')

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed))
print('Done — all emojis replaced in prometheus_engine.py')
