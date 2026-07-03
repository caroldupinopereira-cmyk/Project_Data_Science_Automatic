import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
in_conflict = False
ours_lines = []
theirs_lines = []
current_block = []

for idx, line in enumerate(lines):
    if line.startswith("<<<<<<<"):
        in_conflict = True
        current_block = [f"--- Conflict {idx+1} ---", line]
        ours_lines = []
        theirs_lines = []
    elif line.startswith("======="):
        current_block.append("=======")
        in_conflict = False
        in_theirs = True
    elif line.startswith(">>>>>>>"):
        current_block.append("\n".join(theirs_lines))
        current_block.append(line)
        print("\n".join(current_block))
        print("---------------------\n")
        in_conflict = False
        in_theirs = False
    else:
        if in_conflict:
            ours_lines.append(f"{idx+1}: {line}")
        elif 'in_theirs' in locals() and in_theirs:
            theirs_lines.append(f"{idx+1}: {line}")
