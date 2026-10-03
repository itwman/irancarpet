try:  # استفاده از PyMySQL به‌جای mysqlclient (نصب ساده‌تر روی سرور)
    import pymysql

    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover
    pass
