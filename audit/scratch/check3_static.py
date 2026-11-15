import ast, sys
from pathlib import Path

src = Path('c:/VSC_Projects/PokerBots/audit/ship_extract')
FORBIDDEN_WRITE = {'socket', 'subprocess', 'urllib', 'http', 'ftplib', 'multiprocessing'}

findings = []
for mod in sorted(src.glob('*.py')):
    text = mod.read_text(encoding='utf-8')
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in FORBIDDEN_WRITE:
                    findings.append(f'{mod.name}:{node.lineno} import {alias.name}')
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split('.')[0] in FORBIDDEN_WRITE:
                findings.append(f'{mod.name}:{node.lineno} from {node.module}')
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == 'open':
                for a in node.args[1:]:
                    if isinstance(a, ast.Constant) and 'w' in str(a.value):
                        findings.append(f'{mod.name}:{node.lineno} open write-mode')
            elif isinstance(fn, ast.Attribute):
                if fn.attr in ('makedirs', 'mkdir', 'savez', 'save', 'savetxt', 'tofile'):
                    findings.append(f'{mod.name}:{node.lineno} .{fn.attr}(...)')

for mod in sorted(src.glob('*.py')):
    text = mod.read_text()
    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s.startswith('#'):
            for kw in ['tempfile', 'socket', 'subprocess']:
                if kw in line:
                    findings.append(f'{mod.name}:{lineno} {kw}: {s[:70]}')

print('CHECK 3 STATIC SCAN:')
if findings:
    for f in findings:
        print(f'  FINDING: {f}')
    sys.exit(1)
else:
    print('  PASS: No file-write, socket, subprocess, tempfile, makedirs in ship_extract/')
