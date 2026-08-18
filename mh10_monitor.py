#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 打包入口：等价于 `python -m monitor`。"""

import sys

from monitor.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
