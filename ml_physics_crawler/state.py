import json
from dataclasses import asdict
from pathlib import Path

from .models import PaperRecord


STATE_DIRNAME = ".ml_physics_crawler_state"


def build_state_dir(output_file: str) -> Path:
    path = Path(output_file).resolve()
    state_dir = path.parent / STATE_DIRNAME / path.stem
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def build_records_cache_filename(output_file: str) -> str:
    return str(build_state_dir(output_file) / "records.json")


def build_run_state_filename(output_file: str) -> str:
    return str(build_state_dir(output_file) / "run_state.json")


def has_cached_records(cache_file: str) -> bool:
    path = Path(cache_file)
    return path.exists() and path.stat().st_size > 2


def load_records_cache(cache_file: str) -> list[PaperRecord]:
    path = Path(cache_file)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return [PaperRecord(**item) for item in data]


def save_records_cache(records: list[PaperRecord], cache_file: str) -> str:
    with open(cache_file, "w", encoding="utf-8") as file:
        json.dump([asdict(record) for record in records], file, ensure_ascii=False, indent=2)
        file.write("\n")
    return cache_file


def load_run_state(state_file: str) -> dict:
    path = Path(state_file)
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_run_state(state: dict, state_file: str) -> str:
    with open(state_file, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return state_file
