from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from markets.models import HedgePair, Instrument


ZERO = Decimal("0")
DECIMAL_MIN = Decimal("0.000000000000000001")
PRICE_MIN = Decimal("0.000000000001")


class BotRun(models.Model):
    class Mode(models.TextChoices):
        BACKTEST = "BACKTEST", "Backtest"
        PAPER = "PAPER", "Paper"

    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    mode = models.CharField(max_length=8, choices=Mode)
    status = models.CharField(max_length=9, choices=Status, default=Status.CREATED)
    account_tier = models.CharField(max_length=64)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    initial_capital = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    entry_rate_threshold = models.DecimalField(max_digits=24, decimal_places=18)
    exit_rate_threshold = models.DecimalField(max_digits=24, decimal_places=18)
    maximum_position_size = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    maximum_orderbook_age_seconds = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(mode__in=("BACKTEST", "PAPER")),
                name="trading_bot_run_valid_mode",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=(
                        "CREATED",
                        "RUNNING",
                        "COMPLETED",
                        "FAILED",
                        "CANCELLED",
                    )
                ),
                name="trading_bot_run_valid_status",
            ),
            models.CheckConstraint(
                condition=Q(initial_capital__gt=0),
                name="trading_bot_run_positive_capital",
            ),
            models.CheckConstraint(
                condition=Q(maximum_position_size__gt=0),
                name="trading_bot_run_positive_position_size",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mode} run {self.pk or 'unsaved'}"


class Position(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        FAILED = "FAILED", "Failed"

    bot_run = models.ForeignKey(
        BotRun,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    hedge_pair = models.ForeignKey(
        HedgePair,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    target_notional = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=7, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=("PENDING", "OPEN", "CLOSED", "FAILED")),
                name="trading_position_valid_status",
            ),
            models.CheckConstraint(
                condition=Q(target_notional__gt=0),
                name="trading_position_positive_notional",
            ),
        ]
        indexes = [
            models.Index(
                fields=("bot_run", "status"),
                name="trading_pos_run_status_idx",
            ),
        ]

    @property
    def net_pnl(self):
        if not self.pk:
            return ZERO
        leg_pnl = sum(
            (
                (leg.gross_realized_pnl or ZERO)
                - (leg.entry_fee_amount or ZERO)
                - (leg.exit_fee_amount or ZERO)
                for leg in self.legs.all()
            ),
            ZERO,
        )
        funding_pnl = sum(
            (payment.amount for payment in self.funding_payments.all()),
            ZERO,
        )
        return leg_pnl + funding_pnl

    def clean(self):
        super().clean()
        if self.status not in {self.Status.OPEN, self.Status.CLOSED}:
            return
        if not self.pk:
            raise ValidationError(
                {"status": "Save a pending position and its two legs before opening it."}
            )

        legs = list(self.legs.all())
        expected = {
            (self.hedge_pair.spot_instrument_id, PositionLeg.Side.BUY),
            (self.hedge_pair.perpetual_instrument_id, PositionLeg.Side.SELL),
        }
        actual = {(leg.instrument_id, leg.side) for leg in legs}
        if len(legs) != 2 or actual != expected:
            raise ValidationError(
                {
                    "status": (
                        "An open or closed position requires exactly one BUY spot leg "
                        "and one SELL perpetual leg from its hedge pair."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Position {self.pk or 'unsaved'} ({self.status})"


class PositionLeg(models.Model):
    class Side(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="legs",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="position_legs",
    )
    side = models.CharField(max_length=4, choices=Side)
    quantity = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    entry_price = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        validators=[MinValueValidator(PRICE_MIN)],
    )
    exit_price = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        null=True,
        blank=True,
        validators=[MinValueValidator(PRICE_MIN)],
    )
    entry_fee_rate = models.DecimalField(max_digits=24, decimal_places=18)
    exit_fee_rate = models.DecimalField(
        max_digits=24,
        decimal_places=18,
        null=True,
        blank=True,
    )
    entry_fee_amount = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        default=ZERO,
    )
    exit_fee_amount = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        default=ZERO,
    )
    gross_realized_pnl = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        default=ZERO,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("position", "instrument"),
                name="trading_leg_position_instrument_uniq",
            ),
            models.CheckConstraint(
                condition=Q(side__in=("BUY", "SELL")),
                name="trading_leg_valid_side",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="trading_leg_positive_quantity",
            ),
            models.CheckConstraint(
                condition=Q(entry_price__gt=0),
                name="trading_leg_positive_entry_price",
            ),
            models.CheckConstraint(
                condition=Q(exit_price__isnull=True) | Q(exit_price__gt=0),
                name="trading_leg_positive_exit_price",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.position_id or not self.instrument_id:
            return

        hedge_pair = self.position.hedge_pair
        if self.instrument_id == hedge_pair.spot_instrument_id:
            expected_side = self.Side.BUY
        elif self.instrument_id == hedge_pair.perpetual_instrument_id:
            expected_side = self.Side.SELL
        else:
            raise ValidationError(
                {"instrument": "The instrument is not part of the position hedge pair."}
            )

        if self.side != expected_side:
            raise ValidationError(
                {"side": f"This v1 instrument leg must use side {expected_side}."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.side} {self.instrument}"


class FundingPayment(models.Model):
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="funding_payments",
    )
    settled_at = models.DateTimeField()
    funding_rate = models.DecimalField(max_digits=24, decimal_places=18)
    eligible_notional = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    amount = models.DecimalField(max_digits=38, decimal_places=18)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(eligible_notional__gt=0),
                name="trading_funding_positive_notional",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Position {self.position_id} funding @ {self.settled_at.isoformat()}"
