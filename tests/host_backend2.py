# in tests/host_backend.py
import uvicorn
import os
import sys
from pathlib import Path

# Set TEST_MODE to True BEFORE anything else is imported
os.environ['TEST_MODE'] = 'True'

# --- The rest of your script ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("--- Running with LOCAL TEST DATABASE ---")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    src_path = str(PROJECT_ROOT / "src")

    uvicorn.run(
        "src.efficient_tutor_backend.main:app",
        host="127.0.0.1",
        port=port,
        reload=True,
        reload_dirs=[src_path]
    )
