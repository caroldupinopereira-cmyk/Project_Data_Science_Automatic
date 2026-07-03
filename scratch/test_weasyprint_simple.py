import sys
try:
    import weasyprint
    print("weasyprint imported successfully! Version:", weasyprint.__version__)
    
    # Try generating a simple PDF
    html_content = "<h1>Hello Antigravity</h1><p>Test WeasyPrint on this machine.</p>"
    weasyprint.HTML(string=html_content).write_pdf("scratch/test_weasyprint_output.pdf")
    print("Successfully generated scratch/test_weasyprint_output.pdf")
except Exception as e:
    import traceback
    print("ERROR importing or running weasyprint:")
    traceback.print_exc()

try:
    from flask import send_file
    print("flask.send_file imported successfully!")
except Exception as e:
    print("ERROR importing flask.send_file:", e)
