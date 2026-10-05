"""Compatibility entry; the maintained MEMS generator lives in mems_comb_drive/."""
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
if len(sys.argv) < 2:
    sys.argv.append(str(HERE / 'out'))
runpy.run_path(str(HERE / 'mems_comb_drive/demo_chip.py'), run_name='__main__')
