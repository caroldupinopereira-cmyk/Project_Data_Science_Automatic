with open(r"c:\Users\Hype\OneDrive\Documents\Kuliah\Pa Bakti\Semester 2\DS_Generator_Week15_Kelompok2 - Copy\frontend\static\css\style.css", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if any(k in line for k in ["ov-viz-row", "ov-kpi", "chart-card", "layout"]):
        # print with replacement/ignore or write to text file
        line_clean = line.encode('ascii', errors='ignore').decode('ascii').strip()
        print(f"Line {idx+1}: {line_clean}")
