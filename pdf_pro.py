#!/usr/bin/env python3
"""PDF PRO launcher — ``python pdf_pro.py [file.pdf]``."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdfpro.bootstrap import check_environment  # noqa: E402

check_environment()

from pdfpro.ui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
