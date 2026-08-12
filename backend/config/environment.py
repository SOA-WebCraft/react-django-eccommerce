import dj_database_url
from urllib.parse import urlparse


def allowed_hosts(configured_hosts, platform_hostname='', trusted_origins=''):
    hosts = [
        host.strip()
        for host in configured_hosts.split(',')
        if host.strip()
    ]
    hostname = platform_hostname.strip()
    if hostname and hostname not in hosts:
        hosts.append(hostname)
    for origin in trusted_origins.split(','):
        origin_hostname = urlparse(origin.strip()).hostname
        if origin_hostname and origin_hostname not in hosts:
            hosts.append(origin_hostname)
    return hosts


def database_configuration(database_url, *, debug=False):
    if not database_url:
        return None
    return dj_database_url.parse(
        database_url,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=not debug,
    )
