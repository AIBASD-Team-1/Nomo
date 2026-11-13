import subprocess
import sys
import webbrowser
from pathlib import Path

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "--cov=.",
        "--cov-branch",
        "--cov-report=term",
        "--cov-report=html"
    ]
)

if result.returncode == 0:
    project_root = Path(__file__).parent.parent
    report = project_root / "htmlcov" / "index.html"
    print(f"Opening: {report}")
    webbrowser.open(report.resolve().as_uri())

sys.exit(result.returncode)

