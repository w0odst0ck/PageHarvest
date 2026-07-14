"""
PageHarvest 价格监控模块

追踪选品结果的价格变化，为后续比较和时机判断提供数据基础。

使用：
    # 全部平台选品数据入库
    python -m monitor.ingest_cli ingest --platform all

    # 单平台
    python -m monitor.ingest_cli ingest --platform 1688

    # 查看入库记录
    python -m monitor.ingest_cli status

    # 查看最新快照
    python -m monitor.ingest_cli snapshots
"""
