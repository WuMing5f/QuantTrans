from django.apps import AppConfig


class DataMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.data_master'
    verbose_name = '数据管理'

