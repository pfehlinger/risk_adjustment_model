import logging
import os
from pathlib import Path

log = logging.getLogger()


class Config:

    def __init__(self) -> None:
        # Change this to figure it out, hard coding for building purposes
        self.local_path = Path(r'C:\Users\Philissa\Documents\development\risk_adjustment_scoring')