# ETF和美股概览功能说明

## 功能概述

系统现在提供了完整的ETF和美股龙头股票概览功能，可以：
- 批量同步A股ETF数据
- 批量同步美股龙头股票数据（受yfinance速率限制影响）
- 查看ETF和美股的整体情况
- 查看每个标的的详细图表和技术指标

## 已实现的ETF列表

### A股ETF（9个）

1. **510300** - 沪深300ETF
2. **510500** - 中证500ETF
3. **159919** - 沪深300ETF（深市）
4. **159915** - 创业板ETF
5. **512100** - 1000ETF
6. **159901** - 深证100ETF
7. **510050** - 50ETF
8. **512000** - 券商ETF
9. **515050** - 5G ETF

### 美股龙头股票（14个，待数据同步）

涵盖各个领域的龙头企业：

**科技类**：
- AAPL - Apple Inc. (苹果)
- MSFT - Microsoft Corporation (微软)
- GOOGL - Alphabet Inc. (谷歌)
- META - Meta Platforms Inc. (Meta)
- NVDA - NVIDIA Corporation (英伟达)

**电商/零售**：
- AMZN - Amazon.com Inc. (亚马逊)
- BABA - Alibaba Group (阿里巴巴)

**新能源**：
- TSLA - Tesla Inc. (特斯拉)

**金融**：
- JPM - JPMorgan Chase & Co. (摩根大通)
- V - Visa Inc. ( Visa)
- MA - Mastercard Incorporated (万事达)

**医疗**：
- JNJ - Johnson & Johnson (强生)

**娱乐**：
- DIS - The Walt Disney Company (迪士尼)
- NFLX - Netflix Inc. (奈飞)

## 使用方法

### 1. 批量同步数据

#### 同步A股ETF（推荐，限制较少）
```bash
python manage.py batch_sync --type etf --days 7 --delay 2
```

#### 同步美股（可能遇到速率限制）
```bash
python manage.py batch_sync --type us_stocks --days 7 --delay 10
```

#### 同步所有数据
```bash
python manage.py batch_sync --type all --days 7 --delay 5
```

**参数说明**：
- `--type`: 同步类型（etf/us_stocks/all）
- `--days`: 同步最近多少天的数据（默认7天）
- `--delay`: 每次请求之间的延迟时间（秒，默认2秒）

### 2. 查看概览页面

#### A股ETF概览
访问：http://127.0.0.1:8000/etf/

显示内容：
- 代码和名称
- 最新收盘价
- 涨跌幅（百分比）
- 最高价/最低价
- 平均成交量
- 数据条数
- 最新数据日期
- 查看图表链接

#### 美股概览
访问：http://127.0.0.1:8000/us-stocks/

显示内容与ETF概览类似

### 3. 查看单个标的图表

从概览页面点击"查看图表"按钮，或直接访问：
- ETF图表：http://127.0.0.1:8000/chart/510300/
- 美股图表：http://127.0.0.1:8000/chart/AAPL/

图表包含：
- K线图（蜡烛图）
- 移动平均线（MA5、MA20、MA60）
- 布林带
- MACD指标
- RSI指标
- 成交量

## 每日更新建议

### 方案1：手动更新（简单）

每天收盘后手动执行：
```bash
python manage.py batch_sync --type etf --days 7 --delay 2
```

### 方案2：定时任务（自动化）

使用cron定时任务每天自动更新：

1. 编辑crontab：
```bash
crontab -e
```

2. 添加任务（每天16:00更新）：
```bash
0 16 * * 1-5 cd /Users/zhiyiwu/Desktop/Coding/AICoding/AIProject/StockTrans && source venv/bin/activate && python manage.py batch_sync --type etf --days 7 --delay 2
```

### 方案3：使用更新脚本

创建 `update_daily.py` 脚本（参考 `每日数据更新说明.md`），然后设置定时任务执行。

## 当前数据状态

### A股ETF
- ✅ 已成功同步9个ETF
- ✅ 每个ETF都有最近一周的数据
- ✅ 可以正常查看概览和图表

### 美股
- ⚠️ 受yfinance速率限制影响，暂时无法批量同步
- 💡 建议：
  1. 等待速率限制解除后重试
  2. 使用VPN更换IP地址
  3. 分批更新，每天更新部分股票
  4. 考虑使用付费API替代

## 功能特点

1. **批量操作**：一次性同步多个标的
2. **自动去重**：不会创建重复数据
3. **错误处理**：单个标的失败不影响其他标的
4. **统计信息**：自动计算涨跌幅、最高最低价等
5. **可视化**：提供完整的图表和技术指标展示

## 扩展说明

### 添加更多ETF或股票

编辑 `apps/data_master/management/commands/batch_sync.py`：

1. 在 `CN_ETFS` 列表中添加更多ETF：
```python
CN_ETFS = [
    ('510300', '沪深300ETF'),
    ('新的代码', '新的名称'),
    # ...
]
```

2. 在 `US_STOCKS` 列表中添加更多股票：
```python
US_STOCKS = [
    ('AAPL', 'Apple Inc.', '科技'),
    ('新的代码', '新的名称', '行业分类'),
    # ...
]
```

### 自定义同步范围

可以修改 `batch_sync.py` 中的列表，选择想要同步的标的。

## 注意事项

1. **数据源限制**：
   - A股数据（akshare）：限制较少，可以频繁更新
   - 美股数据（yfinance）：有严格限制，需要控制频率

2. **数据时效性**：
   - 建议在交易日收盘后更新
   - 使用`--days`参数可以获取更多历史数据

3. **网络环境**：
   - 某些地区可能无法直接访问yfinance
   - 可能需要使用代理或VPN

4. **数据质量**：
   - 系统会自动计算技术指标
   - 建议至少有60条数据以显示完整的技术指标

