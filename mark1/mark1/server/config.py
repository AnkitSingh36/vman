"""Local-demo configuration; operational pilot mode is intentionally unavailable."""
from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database: Path = ROOT / "out" / "mark1.sqlite"
    contracts: Path = ROOT / "docs/specs/Mark1-Team-Spec/contracts"
    mode: str = "demo"
    max_image_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 16_000_000
    image_side: int = 2048
    inference_timeout: float = 60
    max_inferences: int = 24
    max_view_failures: int = 3
    lease_seconds: int = 15

    def __post_init__(self):
        if self.mode != "demo":
            raise ValueError("Only synthetic local demo mode is implemented; pilot mode is disabled.")
        if not 0 < self.lease_seconds <= 15 or not 0 < self.inference_timeout <= 60:
            raise ValueError("Invalid freshness or inference limit")
        if not 0 <= self.max_inferences <= 24 or not 1 <= self.max_view_failures <= 3:
            raise ValueError("Session budgets cannot exceed the published contract")
        if not 0 < self.max_image_bytes <= 10 * 1024 * 1024 or not 0 < self.max_pixels <= 16_000_000:
            raise ValueError("Image limits exceed the tested demo boundary")
        if not 0 < self.image_side <= 2048:
            raise ValueError("Invalid downsampling limit")

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        database = Path(os.getenv("MARK1_DB", "out/mark1.sqlite"))
        if not database.is_absolute():
            database = ROOT / database
        return cls(database=database, mode=os.getenv("MARK1_MODE", "demo"))
