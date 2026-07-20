"""平台注册表"""

PLATFORMS = [
    {
        'name': '1688',
        'module_path': 'platforms.alibaba_1688',
        'enabled': True,
        'tier': 1,
        'status': 'active',
    },
    {
        'name': '震坤行',
        'module_path': 'platforms.zkh',
        'enabled': True,
        'tier': 1,
        'status': 'active',
    },
    {
        'name': '京东工业品',
        'module_path': 'platforms.jd_industrial',
        'enabled': False,
        'tier': 2,
        'status': 'planned',
    },
    {
        'name': '工品汇',
        'module_path': 'platforms.gongpinhui',
        'enabled': False,
        'tier': 3,
        'status': 'planned',
    },
    {
        'name': '西域',
        'module_path': 'platforms.ehsy',
        'enabled': False,
        'tier': 3,
        'status': 'planned',
    },
]


def get_active():
    """获取已启用的平台列表"""
    return [p for p in PLATFORMS if p['enabled']]


def get_all():
    """获取所有已注册平台（含未启用）"""
    return PLATFORMS
