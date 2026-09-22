import os
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
import django

django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = ['*']

from django.test import Client
from django.urls import get_resolver


def walk(resolver, prefix=''):
    result = []
    for p in resolver.url_patterns:
        pat = str(p.pattern)
        if hasattr(p, 'url_patterns'):
            result += walk(p, prefix + pat)
        else:
            result.append((prefix + pat, p.name, getattr(p, 'default_args', {}) or {}))
    return result


lines = []
c = Client()
urls = walk(get_resolver())
lines.append(f'TOTAL URLS: {len(urls)}')
for pat, name, kwargs in urls:
    if '<' in pat:
        lines.append(f'SKIP (needs args): {pat} name={name}')
        continue
    path = '/' + pat
    while '//' in path:
        path = path.replace('//', '/')
    if path.endswith('/') and len(path) > 1 and pat.endswith('/'):
        pass
    try:
        r = c.get(path)
        lines.append(f'{r.status_code} GET {path} name={name}')
    except Exception as e:
        lines.append(f'ERROR {path} name={name}: {e.__class__.__name__}: {e}')
        lines.append(traceback.format_exc())

with open('_view_check.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('done', len(lines))
