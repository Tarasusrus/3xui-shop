from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services import (
        InviteStatsService,
        NotificationService,
        PaymentStatsService,
        PlanService,
        ReferralService,
        ServerPoolService,
        SubscriptionService,
        VPNService,
    )

from dataclasses import dataclass


@dataclass
class ServicesContainer:
    server_pool: ServerPoolService
    plan: PlanService
    vpn: VPNService
    notification: NotificationService
    referral: ReferralService
    subscription: SubscriptionService
    payment_stats: PaymentStatsService
    invite_stats: InviteStatsService
