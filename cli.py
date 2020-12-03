#!/usr/bin/env python3

from pathlib import Path

from avinfo import common
from avinfo.__main__ import main

if __name__ == "__main__":
    common.log_file = Path(__file__).with_name(common.log_file)
    main()
