import dj_database_url


def database_configuration(database_url, *, debug=False):
    if not database_url:
        return None
    return dj_database_url.parse(
        database_url,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=not debug,
    )
