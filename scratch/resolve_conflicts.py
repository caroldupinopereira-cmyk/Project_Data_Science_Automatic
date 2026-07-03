import sys
import os

def resolve_file(filepath):
    print(f"Resolving conflicts in {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    new_lines = []
    
    in_conflict = False
    in_ours = False
    in_theirs = False
    
    conflict_count = 0
    
    ours_block = []
    theirs_block = []
    
    for idx, line in enumerate(lines):
        if line.startswith("<<<<<<<"):
            in_conflict = True
            in_ours = True
            in_theirs = False
            ours_block = []
            theirs_block = []
            conflict_count += 1
            continue
        elif line.startswith("======="):
            in_ours = False
            in_theirs = True
            continue
        elif line.startswith(">>>>>>>"):
            in_conflict = False
            in_theirs = False
            # Resolve by choosing the 'theirs' block (remote version)
            new_lines.extend(theirs_block)
            continue
            
        if in_conflict:
            if in_ours:
                ours_block.append(line)
            elif in_theirs:
                theirs_block.append(line)
        else:
            new_lines.append(line)
            
    print(f"Found and resolved {conflict_count} conflict blocks.")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(new_lines) + "\n")

if __name__ == "__main__":
    resolve_file("app.py")
    resolve_file("backend/report_generator.py")
