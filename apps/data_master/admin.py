from django.contrib import admin
from .models import Instrument, Candle, CandleMinute


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'market', 'name', 'category', 'created_at', 'updated_at')
    list_filter = ('market', 'category', 'created_at')
    search_fields = ('symbol', 'name', 'category')


@admin.register(Candle)
class CandleAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'date', 'open', 'high', 'low', 'close', 'volume')
    list_filter = ('instrument__market', 'date')
    search_fields = ('instrument__symbol',)
    date_hierarchy = 'date'


@admin.register(CandleMinute)
class CandleMinuteAdmin(admin.ModelAdmin):
    list_display = ('instrument', 'datetime', 'interval', 'open', 'high', 'low', 'close', 'volume')
    list_filter = ('instrument__market', 'interval', 'datetime')
    search_fields = ('instrument__symbol',)
    date_hierarchy = 'datetime'

