import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('markets', '0001_enable_btree_gist'),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=32, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Exchange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive')], default='ACTIVE', max_length=8)),
                ('metadata_json', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.CheckConstraint(condition=models.Q(('status__in', ('ACTIVE', 'INACTIVE'))), name='markets_exchange_valid_status')],
            },
        ),
        migrations.CreateModel(
            name='Instrument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exchange_symbol', models.CharField(max_length=100)),
                ('type', models.CharField(choices=[('SPOT', 'Spot'), ('PERPETUAL', 'Perpetual')], max_length=10)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('SUSPENDED', 'Suspended'), ('DELISTED', 'Delisted')], default='ACTIVE', max_length=9)),
                ('contract_multiplier', models.DecimalField(decimal_places=18, default=Decimal('1'), max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('price_tick', models.DecimalField(decimal_places=12, max_digits=30, validators=[django.core.validators.MinValueValidator(Decimal('1E-12'))])),
                ('quantity_step', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('minimum_quantity', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('minimum_notional', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('funding_interval_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('base_asset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='base_instruments', to='markets.asset')),
                ('exchange', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='instruments', to='markets.exchange')),
                ('quote_asset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='quote_instruments', to='markets.asset')),
                ('settlement_asset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='settled_instruments', to='markets.asset')),
            ],
        ),
        migrations.CreateModel(
            name='HedgePair',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('perpetual_instrument', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='perpetual_hedge_pairs', to='markets.instrument')),
                ('spot_instrument', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='spot_hedge_pairs', to='markets.instrument')),
            ],
        ),
        migrations.CreateModel(
            name='FundingRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('observed_at', models.DateTimeField()),
                ('settlement_at', models.DateTimeField()),
                ('rate', models.DecimalField(decimal_places=18, max_digits=24)),
                ('is_final', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='funding_rates', to='markets.instrument')),
            ],
        ),
        migrations.CreateModel(
            name='InstrumentFee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_tier', models.CharField(max_length=64)),
                ('maker_rate', models.DecimalField(decimal_places=18, max_digits=24)),
                ('taker_rate', models.DecimalField(decimal_places=18, max_digits=24)),
                ('effective_from', models.DateTimeField()),
                ('effective_to', models.DateTimeField(blank=True, null=True)),
                ('metadata_json', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_schedules', to='markets.instrument')),
            ],
        ),
        migrations.CreateModel(
            name='OrderBookSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('captured_at', models.DateTimeField()),
                ('exchange_sequence', models.CharField(blank=True, max_length=128, null=True)),
                ('checksum', models.CharField(blank=True, max_length=128, null=True)),
                ('depth_per_side', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_book_snapshots', to='markets.instrument')),
            ],
            options={
                'ordering': ('instrument', 'captured_at'),
            },
        ),
        migrations.CreateModel(
            name='OrderBookLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('side', models.CharField(choices=[('BID', 'Bid'), ('ASK', 'Ask')], max_length=3)),
                ('level_index', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('price', models.DecimalField(decimal_places=12, max_digits=30, validators=[django.core.validators.MinValueValidator(Decimal('1E-12'))])),
                ('quantity', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='levels', to='markets.orderbooksnapshot')),
            ],
            options={
                'ordering': ('snapshot', 'side', 'level_index'),
            },
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.UniqueConstraint(fields=('exchange', 'exchange_symbol'), name='markets_instrument_exchange_symbol_uniq'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('type__in', ('SPOT', 'PERPETUAL'))), name='markets_instrument_valid_type'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ('ACTIVE', 'SUSPENDED', 'DELISTED'))), name='markets_instrument_valid_status'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('contract_multiplier__gt', 0)), name='markets_instrument_positive_multiplier'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('price_tick__gt', 0)), name='markets_instrument_positive_price_tick'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('quantity_step__gt', 0)), name='markets_instrument_positive_qty_step'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('minimum_quantity__gt', 0)), name='markets_instrument_positive_min_qty'),
        ),
        migrations.AddConstraint(
            model_name='instrument',
            constraint=models.CheckConstraint(condition=models.Q(('minimum_notional__gt', 0)), name='markets_instrument_positive_min_notional'),
        ),
        migrations.AddConstraint(
            model_name='hedgepair',
            constraint=models.UniqueConstraint(fields=('spot_instrument', 'perpetual_instrument'), name='markets_hedge_pair_instruments_uniq'),
        ),
        migrations.AddIndex(
            model_name='fundingrate',
            index=models.Index(fields=['instrument', 'settlement_at'], name='markets_funding_settlement_idx'),
        ),
        migrations.AddIndex(
            model_name='fundingrate',
            index=models.Index(fields=['instrument', 'observed_at'], name='markets_funding_observed_idx'),
        ),
        migrations.AddConstraint(
            model_name='fundingrate',
            constraint=models.UniqueConstraint(fields=('instrument', 'observed_at', 'settlement_at'), name='markets_funding_instrument_times_uniq'),
        ),
        migrations.AddConstraint(
            model_name='fundingrate',
            constraint=models.CheckConstraint(condition=models.Q(('observed_at__lte', models.F('settlement_at'))), name='markets_funding_observed_before_settlement'),
        ),
        migrations.AddIndex(
            model_name='instrumentfee',
            index=models.Index(fields=['instrument', 'account_tier', 'effective_from'], name='markets_fee_effective_idx'),
        ),
        migrations.AddConstraint(
            model_name='instrumentfee',
            constraint=models.CheckConstraint(condition=models.Q(('effective_to__isnull', True), ('effective_to__gt', models.F('effective_from')), _connector='OR'), name='markets_fee_valid_period'),
        ),
        migrations.AddConstraint(
            model_name='instrumentfee',
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(expressions=(('instrument', '='), ('account_tier', '='), (models.Func(models.F('effective_from'), models.F('effective_to'), django.contrib.postgres.fields.ranges.RangeBoundary(), function='TSTZRANGE', output_field=django.contrib.postgres.fields.ranges.DateTimeRangeField()), '&&')), name='markets_fee_period_no_overlap'),
        ),
        migrations.AddConstraint(
            model_name='orderbooksnapshot',
            constraint=models.UniqueConstraint(fields=('instrument', 'captured_at'), name='markets_snapshot_instrument_time_uniq'),
        ),
        migrations.AddConstraint(
            model_name='orderbooksnapshot',
            constraint=models.CheckConstraint(condition=models.Q(('depth_per_side__gt', 0)), name='markets_snapshot_positive_depth'),
        ),
        migrations.AddConstraint(
            model_name='orderbooklevel',
            constraint=models.UniqueConstraint(fields=('snapshot', 'side', 'level_index'), name='markets_level_snapshot_side_index_uniq'),
        ),
        migrations.AddConstraint(
            model_name='orderbooklevel',
            constraint=models.CheckConstraint(condition=models.Q(('side__in', ('BID', 'ASK'))), name='markets_level_valid_side'),
        ),
        migrations.AddConstraint(
            model_name='orderbooklevel',
            constraint=models.CheckConstraint(condition=models.Q(('level_index__gt', 0)), name='markets_level_positive_index'),
        ),
        migrations.AddConstraint(
            model_name='orderbooklevel',
            constraint=models.CheckConstraint(condition=models.Q(('price__gt', 0)), name='markets_level_positive_price'),
        ),
        migrations.AddConstraint(
            model_name='orderbooklevel',
            constraint=models.CheckConstraint(condition=models.Q(('quantity__gt', 0)), name='markets_level_positive_quantity'),
        ),
    ]
