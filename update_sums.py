import hashlib
import glob

files = (
    glob.glob('tools/*.py') +
    glob.glob('tools/*.c') +
    glob.glob('tools/*.js') +
    glob.glob('adapters/*.py') +
    glob.glob('contracts/*.json') +
    glob.glob('schemas/*.json')
)

lines = []
for f in files:
    with open(f, 'rb') as fd:
        data = fd.read()
    h = hashlib.sha256(data).hexdigest()
    lines.append(f"{h} *{f.replace(chr(92), '/')}")

lines.sort()
with open('SOURCE_SHA256SUMS.txt', 'w', newline='\n') as fd:
    fd.write('\n'.join(lines) + '\n')
