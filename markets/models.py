from decimal import Decimal

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Func, Q


DECIMAL_MIN = Decimal("0.000000000000000001")
PRICE_MIN = Decimal("0.000000000001")


class Exchange(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=8, choices=Status, default=Status.ACTIVE)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=("ACTIVE", "INACTIVE")),
                name="markets_exchange_valid_status",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Asset(models.Model):
    symbol = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.symbol


class Instrument(models.Model):
    class Type(models.TextChoices):
        SPOT = "SPOT", "Spot"
        PERPETUAL = "PERPETUAL", "Perpetual"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        DELISTED = "DELISTED", "Delisted"

    exchange = models.ForeignKey(
        Exchange,
        on_delete=models.PROTECT,
        related_name="instruments",
    )
    base_asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="base_instruments",
    )
    quote_asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="quote_instruments",
    )
    settlement_asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="settled_instruments",
    )
    exchange_symbol = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=Type)
    status = models.CharField(max_length=9, choices=Status, default=Status.ACTIVE)
    contract_multiplier = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        default=Decimal("1"),
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    price_tick = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        validators=[MinValueValidator(PRICE_MIN)],
    )
    quantity_step = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    minimum_quantity = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    minimum_notional = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    funding_interval_minutes = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("exchange", "exchange_symbol"),
                name="markets_instrument_exchange_symbol_uniq",
            ),
            models.CheckConstraint(
                condition=Q(type__in=("SPOT", "PERPETUAL")),
                name="markets_instrument_valid_type",
            ),
            models.CheckConstraint(
                condition=Q(status__in=("ACTIVE", "SUSPENDED", "DELISTED")),
                name="markets_instrument_valid_status",
            ),
            models.CheckConstraint(
                condition=Q(contract_multiplier__gt=0),
                name="markets_instrument_positive_multiplier",
            ),
            models.CheckConstraint(
                condition=Q(price_tick__gt=0),
                name="markets_instrument_positive_price_tick",
            ),
            models.CheckConstraint(
                condition=Q(quantity_step__gt=0),
                name="markets_instrument_positive_qty_step",
            ),
            models.CheckConstraint(
                condition=Q(minimum_quantity__gt=0),
                name="markets_instrument_positive_min_qty",
            ),
            models.CheckConstraint(
                condition=Q(minimum_notional__gt=0),
                name="markets_instrument_positive_min_notional",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.exchange.name}:{self.exchange_symbol}"


class HedgePair(models.Model):
    spot_instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="spot_hedge_pairs",
    )
    perpetual_instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="perpetual_hedge_pairs",
    )
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("spot_instrument", "perpetual_instrument"),
                name="markets_hedge_pair_instruments_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.spot_instrument_id and self.spot_instrument.type != Instrument.Type.SPOT:
            errors["spot_instrument"] = "The spot instrument must have type SPOT."
        if (
            self.perpetual_instrument_id
            and self.perpetual_instrument.type != Instrument.Type.PERPETUAL
        ):
            errors["perpetual_instrument"] = (
                "The perpetual instrument must have type PERPETUAL."
            )
        if self.spot_instrument_id and self.perpetual_instrument_id:
            if self.spot_instrument.base_asset_id != self.perpetual_instrument.base_asset_id:
                errors["perpetual_instrument"] = "Both instruments must share a base asset."
            if self.spot_instrument.exchange_id != self.perpetual_instrument.exchange_id:
                errors["perpetual_instrument"] = "Both instruments must share an exchange."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.spot_instrument} / {self.perpetual_instrument}"


class InstrumentFee(models.Model):
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="fee_schedules",
    )
    account_tier = models.CharField(max_length=64)
    maker_rate = models.DecimalField(max_digits=24, decimal_places=18)
    taker_rate = models.DecimalField(max_digits=24, decimal_places=18)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=F("effective_from")),
                name="markets_fee_valid_period",
            ),
            ExclusionConstraint(
                name="markets_fee_period_no_overlap",
                expressions=(
                    ("instrument", RangeOperators.EQUAL),
                    ("account_tier", RangeOperators.EQUAL),
                    (
                        Func(
                            F("effective_from"),
                            F("effective_to"),
                            RangeBoundary(),
                            function="TSTZRANGE",
                            output_field=DateTimeRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=("instrument", "account_tier", "effective_from"),
                name="markets_fee_effective_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError(
                {"effective_to": "The end must be later than the start."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.instrument} ({self.account_tier})"


class OrderBookSnapshot(models.Model):
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="order_book_snapshots",
    )
    captured_at = models.DateTimeField()
    exchange_sequence = models.CharField(max_length=128, null=True, blank=True)
    checksum = models.CharField(max_length=128, null=True, blank=True)
    depth_per_side = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instrument", "captured_at"),
                name="markets_snapshot_instrument_time_uniq",
            ),
            models.CheckConstraint(
                condition=Q(depth_per_side__gt=0),
                name="markets_snapshot_positive_depth",
            ),
        ]
        ordering = ("instrument", "captured_at")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.instrument} @ {self.captured_at.isoformat()}"


class OrderBookLevel(models.Model):
    class Side(models.TextChoices):
        BID = "BID", "Bid"
        ASK = "ASK", "Ask"

    snapshot = models.ForeignKey(
        OrderBookSnapshot,
        on_delete=models.CASCADE,
        related_name="levels",
    )
    side = models.CharField(max_length=3, choices=Side)
    level_index = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(
        max_digits=30,
        decimal_places=12,
        validators=[MinValueValidator(PRICE_MIN)],
    )
    quantity = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(DECIMAL_MIN)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("snapshot", "side", "level_index"),
                name="markets_level_snapshot_side_index_uniq",
            ),
            models.CheckConstraint(
                condition=Q(side__in=("BID", "ASK")),
                name="markets_level_valid_side",
            ),
            models.CheckConstraint(
                condition=Q(level_index__gt=0),
                name="markets_level_positive_index",
            ),
            models.CheckConstraint(
                condition=Q(price__gt=0),
                name="markets_level_positive_price",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="markets_level_positive_quantity",
            ),
        ]
        ordering = ("snapshot", "side", "level_index")

    def clean(self):
        super().clean()
        if self.snapshot_id and self.level_index > self.snapshot.depth_per_side:
            raise ValidationError(
                {"level_index": "The level index exceeds the snapshot depth per side."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.side} {self.level_index}: {self.price} x {self.quantity}"


class FundingRate(models.Model):
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="funding_rates",
    )
    observed_at = models.DateTimeField()
    settlement_at = models.DateTimeField()
    rate = models.DecimalField(max_digits=24, decimal_places=18)
    is_final = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instrument", "observed_at", "settlement_at"),
                name="markets_funding_instrument_times_uniq",
            ),
            models.CheckConstraint(
                condition=Q(observed_at__lte=F("settlement_at")),
                name="markets_funding_observed_before_settlement",
            ),
        ]
        indexes = [
            models.Index(
                fields=("instrument", "settlement_at"),
                name="markets_funding_settlement_idx",
            ),
            models.Index(
                fields=("instrument", "observed_at"),
                name="markets_funding_observed_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.instrument_id and self.instrument.type != Instrument.Type.PERPETUAL:
            errors["instrument"] = "Funding rates require a perpetual instrument."
        if self.observed_at and self.settlement_at and self.observed_at > self.settlement_at:
            errors["observed_at"] = "Observation cannot occur after settlement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.instrument} @ {self.settlement_at.isoformat()}: {self.rate}"
