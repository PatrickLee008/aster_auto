import urllib.request
import ssl

proxy = 'http://brd-customer-hl_5e1f2ce5-zone-aster-country-us:jlfm7ayb6puo@brd.superproxy.io:33335'
url = 'https://geo.brdtest.com/welcome.txt?product=isp&method=native'

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({'https': proxy, 'http': proxy})
)

try:
    print(opener.open(url).read().decode())
except Exception as e:
    print(f"Error: {e}")
