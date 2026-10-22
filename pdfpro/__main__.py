"""Allow ``python -m pdfpro [file.pdf]``."""

from .bootstrap import check_environment

check_environment()

from .ui.app import main  # noqa: E402  (import after the environment check)

main()
