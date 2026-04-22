# 导出豆瓣Top100（每行一个标题）
# 说明：请遵守网站条款；如遇到反爬/需要登录，可能需要在浏览器打开后再手动复制页面源码。
import time
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
headers = {"User-Agent": UA, "Referer": "https://movie.douban.com/"}

titles = []
for start in range(0, 250, 25):  # 0,25,50,75 -> 共100条
    url = f"https://movie.douban.com/top250?start={start}&filter="
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for item in soup.select("div.item span.title:first-child"):
        titles.append(item.get_text(strip=True))
    time.sleep(1.2)

for t in titles[:100]:
    print(t)
