#!/bin/bash
# Oracle: install the reference calculator over the legacy implementation.
set -euo pipefail
cp /solution/sw/__init__.py /solution/sw/potential.py /solution/sw/calculator.py /app/sw/
chmod a+r /app/sw/*.py
cd /app && python3 examples/cell_choice.py
