from datetime import UTC, datetime, timedelta


def get_current_timestamp() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def add_days_to_timestamp(timestamp: int, days: int) -> int:
    new_datetime = datetime.fromtimestamp(timestamp / 1000, tz=UTC) + timedelta(days=days)
    return int(new_datetime.timestamp() * 1000)


def days_to_timestamp(days: int) -> int:
    return add_days_to_timestamp(get_current_timestamp(), days)
