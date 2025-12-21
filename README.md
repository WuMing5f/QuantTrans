# QuantTrader - 量化交易系统

基于 Django 的量化交易系统，支持美股（yfinance）和 A股（akshare）数据获取，提供技术指标计算和回测功能。

## 技术栈

- **Django**: Web框架
- **yfinance**: 美股数据获取
- **akshare**: A股数据获取
- **pandas**: 数据处理
- **pandas_ta**: 技术指标计算
- **backtrader**: 回测引擎

## 项目结构

```
QuantTrader/
├── manage.py
├── requirements.txt
├── config/                 # Django 项目配置
│   ├── settings.py         # 包含 INSTALLED_APPS 和 DB 配置
│   └── urls.py
├── apps/
│   ├── data_master/        # [模块1] 数据管理 (核心)
│   │   ├── models.py       # Instrument, Candle 定义
│   │   ├── providers/      # 数据源适配器工厂
│   │   │   ├── base.py     # 抽象基类
│   │   │   ├── us_yahoo.py # yfinance 实现
│   │   │   └── cn_akshare.py # AkShare 实现
│   │   └── management/commands/sync_data.py # 数据同步命令
│   │
│   ├── analysis/           # [模块2] 指标计算
│   │   └── indicators.py   # 封装 pandas_ta 计算逻辑
│   │
│   ├── backtest/           # [模块3] 回测引擎
│   │   ├── engine.py       # Backtrader 驱动器
│   │   ├── strategies.py   # 交易策略 (如 MACD, 双均线)
│   │   └── feeds.py        # Django ORM 到 Backtrader 的数据转换
│   │
│   └── dashboard/          # [模块4] Web 界面
│       ├── views.py        # 控制器
│       └── templates/      # HTML 页面
```

## 安装步骤

### 1. 创建虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows
```

### 2. 安装依赖

**注意**：
- `pandas-ta` 需要 Python 3.11+，如果使用 Python 3.9-3.10，系统会自动使用兼容模式（使用 pandas/numpy 手动计算指标）
- 推荐使用 Python 3.11+ 以获得更好的性能

```bash
# 使用 pip3（推荐）
pip3 install -r requirements.txt

# 或者在虚拟环境中
pip install -r requirements.txt
```

**如果遇到 `pip: command not found`**：
- macOS/Linux 通常需要使用 `pip3` 而不是 `pip`
- 或者使用完整路径：`python3 -m pip install -r requirements.txt`

### 2. 初始化数据库

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. 创建超级用户（可选，用于访问Django Admin）

```bash
python manage.py createsuperuser
```

## 使用方法

### 1. 同步数据

#### 同步美股数据

```bash
python manage.py sync_data --symbol AAPL --market US --start 2020-01-01 --end 2024-01-01 --name "Apple Inc."
```

#### 同步A股ETF数据

```bash
python manage.py sync_data --symbol 510300 --market CN --start 2020-01-01 --end 2024-01-01 --name "沪深300ETF"
```

**参数说明：**
- `--symbol`: 股票代码（如 AAPL, 510300）
- `--market`: 市场类型（US 或 CN）
- `--start`: 开始日期（格式：YYYY-MM-DD）
- `--end`: 结束日期（格式：YYYY-MM-DD）
- `--name`: 标的名称（可选）

### 2. 运行回测

在 Django shell 中运行：

```python
python manage.py shell
```

```python
from apps.backtest.engine import run_backtest

# 双均线策略回测
result = run_backtest(
    symbol='AAPL',
    strategy_name='macross',
    start_date='2020-01-01',
    end_date='2024-01-01',
    initial_cash=100000,
    fast_period=5,
    slow_period=20,
    commission=0.001
)

print(result)
```

**可用策略：**
- `macross`: 双均线策略
- `macd`: MACD策略

**回测结果包含：**
- `initial_cash`: 初始资金
- `final_value`: 最终资产
- `total_return`: 总收益率（%）
- `sharpe_ratio`: 夏普比率
- `max_drawdown`: 最大回撤
- 等其他指标

### 3. 计算技术指标

```python
from apps.analysis.indicators import IndicatorEngine
import pandas as pd

# 假设你有一个包含OHLCV数据的DataFrame
df = pd.DataFrame(...)  # 包含 date, open, high, low, close, volume 列

# 注入技术指标
df_with_indicators = IndicatorEngine.inject_indicators(df, market='US')

# 现在DataFrame包含以下指标：
# - SMA_5, SMA_20, SMA_60 (移动平均线)
# - BBL_20_2.0, BBM_20_2.0, BBU_20_2.0 (布林带)
# - MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9 (MACD)
# - RSI_14 (RSI)
# - STOCHk_9_3_3, STOCHd_9_3_3, KDJ_J (KDJ指标)
```

### 4. 数据可视化

启动Web服务器：

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/ 查看仪表盘

**可视化功能**：
- **K线图**：展示价格走势（蜡烛图）
- **移动平均线**：MA5、MA20、MA60
- **布林带**：价格通道指标
- **MACD指标**：趋势跟踪指标
- **RSI指标**：相对强弱指标
- **成交量**：交易量柱状图

在首页点击任意标的的"查看图表"按钮即可查看详细的技术指标图表。

### 5. Django管理界面

访问 http://127.0.0.1:8000/admin/ 访问Django管理界面

首次使用需要创建超级用户：
```bash
python manage.py createsuperuser
```

## 数据模型

### Instrument（标的）
- `symbol`: 股票代码（唯一）
- `market`: 市场类型（US/CN）
- `name`: 名称

### Candle（K线数据）
- `instrument`: 关联的标的
- `date`: 日期
- `open`, `high`, `low`, `close`: 开盘、最高、最低、收盘价
- `volume`: 成交量
- `amount`: 成交额
- `turnover`: 换手率（%）

## 开发说明

### 添加新的数据源

1. 在 `apps/data_master/providers/` 目录下创建新的provider类
2. 继承 `DataProvider` 基类
3. 实现 `fetch_history` 方法
4. 在 `providers/__init__.py` 中注册新的provider

### 添加新的策略

1. 在 `apps/backtest/strategies.py` 中添加新的策略类
2. 继承 `bt.Strategy`
3. 在 `apps/backtest/engine.py` 的 `strategies` 字典中注册

### 添加新的技术指标

在 `apps/analysis/indicators.py` 的 `IndicatorEngine.inject_indicators` 方法中添加指标计算逻辑。

## 注意事项

1. **数据源限制**：
   - yfinance 和 akshare 可能有访问频率限制
   - 建议批量同步数据时适当延时

2. **A股数据**：
   - 当前实现使用 `ak.fund_etf_hist_em` 获取ETF数据
   - 如需获取个股数据，可能需要调整 `cn_akshare.py` 中的实现

3. **回测性能**：
   - 大量数据回测可能需要较长时间
   - 建议先用小数据集测试策略

4. **数据库**：
   - 默认使用 SQLite，生产环境建议使用 PostgreSQL 或 MySQL

## 许可证

MIT License

