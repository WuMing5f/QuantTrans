from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('etf/', views.etf_overview, name='etf_overview'),
    path('us-stocks/', views.us_stocks_overview, name='us_stocks_overview'),
    path('chart/<str:symbol>/', views.chart_view, name='chart'),
    path('api/data/<str:symbol>/', views.get_chart_data, name='chart_data'),
]

