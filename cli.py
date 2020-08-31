#!/usr/bin/env python3

import os.path
from avinfo.__main__ import main
from avinfo import common

if __name__ == "__main__":
    common.logFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), common.logFile)
    main()
