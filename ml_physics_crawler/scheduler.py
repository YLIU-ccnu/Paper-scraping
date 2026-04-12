from datetime import datetime, timedelta, timezone

from .state import build_run_state_filename, load_run_state


def should_run_scheduled_update(
    output_file: str,
    interval_days: int,
    now: datetime | None = None,
) -> bool:
    if interval_days <= 0:
        raise ValueError("interval_days must be greater than 0")

    current_time = now or datetime.now(timezone.utc)
    run_state = load_run_state(build_run_state_filename(output_file))
    last_successful_run_at = run_state.get("last_successful_run_at")
    if not last_successful_run_at:
        return True

    last_run_time = datetime.fromisoformat(last_successful_run_at)
    return current_time - last_run_time >= timedelta(days=interval_days)
