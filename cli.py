#!/usr/bin/env python3

from pathlib import Path
from avinfo.__main__ import main
from avinfo import common

if __name__ == "__main__":
    common.logFile = Path(__file__).with_name(common.logFile)
    main()
