from dataclasses import dataclass, field


@dataclass
class InviteStats:
    revenue: dict[str, float] = field(default_factory=dict)
    users_count: int = 0
    trial_users_count: int = 0
    paid_users_count: int = 0
    repeat_customers_count: int = 0
