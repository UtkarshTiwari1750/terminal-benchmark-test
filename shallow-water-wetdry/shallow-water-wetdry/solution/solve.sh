#!/bin/bash
# Oracle: replace the legacy solver with the reference scheme.
set -euo pipefail
cp /solution/oracle_solver.py /app/swe/solver.py
chmod a+r /app/swe/solver.py
cd /app && python3 -c "import swe; print('oracle installed:', swe.simulate.__module__)"
