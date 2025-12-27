from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('strategy-monitor/', views.strategy_monitor, name='strategy_monitor'),
    path('strategy-monitor/<str:strategy_name>/', views.strategy_monitor, name='strategy_monitor_detail'),
    path('etf/', views.etf_overview, name='etf_overview'),
    path('us-stocks/', views.us_stocks_overview, name='us_stocks_overview'),
    path('chart/<str:symbol>/', views.chart_view, name='chart'),
    path('api/data/<str:symbol>/', views.get_chart_data, name='chart_data'),
    path('backtest/', views.backtest_view, name='backtest'),
    path('api/backtest/', views.run_backtest_api, name='backtest_api'),
    path('api/optimize-strategy/', views.optimize_strategy_api, name='optimize_strategy_api'),
    path('batch-optimize/', views.batch_optimize_view, name='batch_optimize'),
    path('api/batch-optimize/', views.batch_optimize_api, name='batch_optimize_api'),
]

