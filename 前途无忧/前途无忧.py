from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
import re
import pymongo
from multiprocessing import Pool

client=pymongo.MongoClient(MONGO_URL)   #链接至MongoDB文档型数据库
db=client[MONGO_DB]

browser = webdriver.PhantomJS(service_args=SERVICE_ARGS)    #使用隐形的浏览器PhantomJS
wait = WebDriverWait(browser, 10)       #设置浏览器超时时间

# 设置窗口大小
# browser.set_window_size(1400, 900)

# 加载搜索页
def search(KEYWORD, url):
    print("正在搜索")
    try:
        browser.get(url)
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#kwdselectid")))      #判断输入框是否存在
        submit = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "body > div.content > div > div.fltr.radius_5 > div > button")))     #判断搜索键是否有效的
        input.send_keys(KEYWORD)
        submit.click()
        total = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "#resultList > div.dw_page > div > div > div > span:nth-child(2)")))    #确定总页码
        get_products()
        return total.text
    except TimeoutException:
        return search(KEYWORD, url)

# 加载翻页后内容
def next_page(page_number):
    print("正在翻页", page_number)
    try:
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#jump_page")))      #定向翻页
        submit = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#resultList > div.dw_page > div > div > div > span.og_but")))    #判断确定键是否可行
        input.clear()
        input.send_keys(page_number)
        submit.click()
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "#resultList > div.dw_page > div > div > div > ul "), str(page_number)))      #检查元素中的文本内容是否存在指定的内容
        get_products()
    except TimeoutException:
        next_page(page_number)

#解析职位目录的URL信息
def get_products():
    html = browser.page_source         #页面信息
    pattern = re.compile('<input.*?class="checkbox".*?<span>.*?<a.*?target="_blank".*?href="(.*?)".*?onmousedown.*?</a>.*?</span>',re.S)
    items=re.findall(pattern,html)        #使用正则表达式进行匹配
    for url in items:
        get_job(url)

#获取具体职位信息
def get_job(URL):
    html = requests.get(URL)
    html.encoding = 'gbk'         #根据该网址的编码进行设置,避免乱码
    pattern = re.compile(
        '<h1.*?title="(.*?)".*?<strong>(.*?)</strong>.*?title="(.*?)".*?title="(.*?)'
        '&nbsp;&nbsp;\|&nbsp;&nbsp;(.*?)&nbsp;&nbsp;\|&nbsp;&nbsp;.*?人&nbsp;&nbsp;\|&nbsp;&nbsp;(.*?)发布.*?">.*?上班地址：</span>(.*?)</p>', re.S)
    items = re.findall(pattern, html.text)
    for item in items:
        message = {
            "职位": item[0],
            "薪资": item[1],
            "公司名字": item[2],
            "公司地点": item[3],
            "工作经验": item[4],
            "发布时间": item[5],
            "上班地点": item[6].replace("\t", "")
        }
        save_to_mongo(message)

#保存至MONGODB
def save_to_mongo(result):
    try:
        if db[MONGO_TABLE].insert(result):
            print("存储到MONGDB",result)
    except Exception:
        print("存储到MONGDB失败")

def main():
    try:
        total = search(KEYWORD, URL)
        total = int(re.compile("(\d+)").search(total).group(1))     #获取总页码
        for i in range(2,total+1):
            next_page(i)
    finally:
        browser.close()

if __name__ == '__main__':
    pool=Pool(3)             #多进程
    pool.apply_async(main())
