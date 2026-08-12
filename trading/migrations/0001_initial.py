import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('markets', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BotRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('BACKTEST', 'Backtest'), ('PAPER', 'Paper')], max_length=8)),
                ('status', models.CharField(choices=[('CREATED', 'Created'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='CREATED', max_length=9)),
                ('account_tier', models.CharField(max_length=64)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('initial_capital', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('entry_rate_threshold', models.DecimalField(decimal_places=18, max_digits=24)),
                ('exit_rate_threshold', models.DecimalField(decimal_places=18, max_digits=24)),
                ('maximum_position_size', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('maximum_orderbook_age_seconds', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.CheckConstraint(condition=models.Q(('mode__in', ('BACKTEST', 'PAPER'))), name='trading_bot_run_valid_mode'), models.CheckConstraint(condition=models.Q(('status__in', ('CREATED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'))), name='trading_bot_run_valid_status'), models.CheckConstraint(condition=models.Q(('initial_capital__gt', 0)), name='trading_bot_run_positive_capital'), models.CheckConstraint(condition=models.Q(('maximum_position_size__gt', 0)), name='trading_bot_run_positive_position_size')],
            },
        ),
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_notional', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('OPEN', 'Open'), ('CLOSED', 'Closed'), ('FAILED', 'Failed')], default='PENDING', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bot_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='positions', to='trading.botrun')),
                ('hedge_pair', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='positions', to='markets.hedgepair')),
            ],
        ),
        migrations.CreateModel(
            name='FundingPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('settled_at', models.DateTimeField()),
                ('funding_rate', models.DecimalField(decimal_places=18, max_digits=24)),
                ('eligible_notional', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('amount', models.DecimalField(decimal_places=18, max_digits=38)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='funding_payments', to='trading.position')),
            ],
        ),
        migrations.CreateModel(
            name='PositionLeg',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('side', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell')], max_length=4)),
                ('quantity', models.DecimalField(decimal_places=18, max_digits=38, validators=[django.core.validators.MinValueValidator(Decimal('1E-18'))])),
                ('entry_price', models.DecimalField(decimal_places=12, max_digits=30, validators=[django.core.validators.MinValueValidator(Decimal('1E-12'))])),
                ('exit_price', models.DecimalField(blank=True, decimal_places=12, max_digits=30, null=True, validators=[django.core.validators.MinValueValidator(Decimal('1E-12'))])),
                ('entry_fee_rate', models.DecimalField(decimal_places=18, max_digits=24)),
                ('exit_fee_rate', models.DecimalField(blank=True, decimal_places=18, max_digits=24, null=True)),
                ('entry_fee_amount', models.DecimalField(decimal_places=18, default=Decimal('0'), max_digits=38)),
                ('exit_fee_amount', models.DecimalField(decimal_places=18, default=Decimal('0'), max_digits=38)),
                ('gross_realized_pnl', models.DecimalField(decimal_places=18, default=Decimal('0'), max_digits=38)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='position_legs', to='markets.instrument')),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='legs', to='trading.position')),
            ],
        ),
        migrations.AddIndex(
            model_name='position',
            index=models.Index(fields=['bot_run', 'status'], name='trading_pos_run_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='position',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ('PENDING', 'OPEN', 'CLOSED', 'FAILED'))), name='trading_position_valid_status'),
        ),
        migrations.AddConstraint(
            model_name='position',
            constraint=models.CheckConstraint(condition=models.Q(('target_notional__gt', 0)), name='trading_position_positive_notional'),
        ),
        migrations.AddConstraint(
            model_name='positionleg',
            constraint=models.UniqueConstraint(fields=('position', 'instrument'), name='trading_leg_position_instrument_uniq'),
        ),
        migrations.AddConstraint(
            model_name='positionleg',
            constraint=models.CheckConstraint(condition=models.Q(('side__in', ('BUY', 'SELL'))), name='trading_leg_valid_side'),
        ),
        migrations.AddConstraint(
            model_name='positionleg',
            constraint=models.CheckConstraint(condition=models.Q(('quantity__gt', 0)), name='trading_leg_positive_quantity'),
        ),
        migrations.AddConstraint(
            model_name='positionleg',
            constraint=models.CheckConstraint(condition=models.Q(('entry_price__gt', 0)), name='trading_leg_positive_entry_price'),
        ),
        migrations.AddConstraint(
            model_name='positionleg',
            constraint=models.CheckConstraint(condition=models.Q(('exit_price__isnull', True), ('exit_price__gt', 0), _connector='OR'), name='trading_leg_positive_exit_price'),
        ),
        migrations.AddConstraint(
            model_name='fundingpayment',
            constraint=models.CheckConstraint(condition=models.Q(('eligible_notional__gt', 0)), name='trading_funding_positive_notional'),
        ),
    ]
