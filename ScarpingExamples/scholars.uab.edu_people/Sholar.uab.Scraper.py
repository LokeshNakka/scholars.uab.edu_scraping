import json
import math
import os
import queue
import threading
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm

import pandas
import requests
from lxml import html
import fake_useragent
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome
from selenium.webdriver.support import expected_conditions as EC

ua = fake_useragent.UserAgent()

header = {'User-Agent': ua.random}

q = queue.Queue()
data = {}


def GetRes(url, status: tqdm = None):
    while True:
        response = requests.get(url, headers=header)
        if response.status_code == 200:
            res = response.json()
            q.put(res)
            if status is not None:
                status.update(1)
                break
            return res
        else:
            time.sleep(.1)
            header['User-Agent'] = ua.random


def GetFacultyLinks():
    global data
    jdata = GetRes(
        'https://scholars.uab.edu/dataservice?getRenderedSearchIndividualsByVClass=1&vclassId=http%3A%2F%2Fscholars.uab.edu%2Fontology%2Flocal%23AdjunctFaculty&page=1')
    totalPages = len(jdata['pages'])
    data['individuals'] = []

    threads = []
    with tqdm(range(2, totalPages + 1), desc='Status') as bar:
        for i in range(2, totalPages + 1):
            url = f'https://scholars.uab.edu/dataservice?getRenderedSearchIndividualsByVClass=1&vclassId=http%3A%2F%2Fscholars.uab.edu%2Fontology%2Flocal%23AdjunctFaculty&page={i}'
            t = threading.Thread(target=GetRes, args=(url, bar))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    while not q.empty():
        data['individuals'].extend(q.get()['individuals'])

    with open('individuals.json', 'w') as jfile:
        json.dump(data, jfile)


driver_path = ''


def Get_Sel(pro_datas, statusBar=None):
    global driver_path
    driver = Chrome(driver_path)

    for pro_data in pro_datas:
        img_url = pro_data.get('imageUrl', None)
        main_url = pro_data.get('URI', None)
        label = pro_data.get('profileUrl', None).split('/')[-1]
        if main_url is not None:
            path = rf'{os.getcwd()}\data_sel\{label}'
            if not os.path.exists(path):
                os.makedirs(path)
            else:
                continue
            driver.get(main_url)
            page_source = driver.page_source
            tree = html.fromstring(page_source)
            email = [_.strip() for _ in tree.xpath('//a[@itemprop="email"]/text()')]
            phone = [_.strip() for _ in tree.xpath('//span[@itemprop="telephone"]/text()')]
            position = [','.join([__.strip(',\n\t ') for __ in _.xpath('descendant::text()')]) for _ in
                        tree.xpath('//ul[@id="individual-personInPosition"]/li')]

            if img_url is not None:
                img_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//img[@class="img-rounded"]')))
                with open(rf"{path}\{label}.png", 'wb') as img:
                    img.write(img_element.screenshot_as_png)
            try:
                qr_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//img[@id="qrIcon"]')))
                with open(rf"{path}\{label}_qr.png", 'wb') as img:
                    img.write(qr_element.screenshot_as_png)
            except:
                pass
            tab_contents = tree.xpath('//div[@class="tab-content"]/child::div')
            for tab_content in tab_contents[:-1]:
                h2 = ''.join(tab_content.xpath('child::h2/text()'))
                panels = tab_content.xpath('descendant::div[@class="panel panel-default"]')
                for panel in panels:
                    p_head = ' '.join(
                        [__.strip() for __ in panel.xpath('div[@class="panel-heading"]/descendant::text()')]).strip()
                    table = panel.xpath('descendant::table[@class="table table-hover"]')
                    p_body = None
                    if len(table) > 0:
                        p_body = pandas.read_html(html.tostring(table[0]))[0]
                        p_body.to_csv(rf"{path}\{h2}_{p_head}.csv")
                    else:
                        p_body = [' '.join([_a.strip('\n\t ') for _a in __.xpath('descendant::text()')])
                                      .strip('\n\t ').replace('\n', ' ')
                                  for __ in panel.xpath('div[@class="panel-body"]/descendant::li')]
                        pandas.DataFrame(p_body, columns=[p_head]).to_csv(rf"{path}\{h2}_{p_head}.csv")
            pro_data['email'] = email
            pro_data['phone'] = phone
            pro_data['position'] = position
            with open(rf"{path}\{label}.json", 'w') as jfile_save:
                json.dump(pro_data, jfile_save)
        statusBar.update(1)


def Get_req(pro_datas, statusBar=None):
    global driver_path

    for pro_data in pro_datas:
        img_url = pro_data.get('imageUrl', None)
        main_url = pro_data.get('URI', None)
        label = pro_data.get('profileUrl', None).split('/')[-1]
        if main_url is not None:
            path = rf'{os.getcwd()}\data_req\{label}'
            if not os.path.exists(path):
                os.makedirs(path)
            else:
                continue
            response = requests.get(main_url, headers=header)
            page_source = ''
            if response.status_code == 200:
                page_source = response.text
            tree = html.fromstring(page_source)
            email = [_.strip() for _ in tree.xpath('//a[@itemprop="email"]/text()')]
            phone = [_.strip() for _ in tree.xpath('//span[@itemprop="telephone"]/text()')]
            position = [','.join([__.strip(',\n\t ') for __ in _.xpath('descendant::text()')]) for _ in
                        tree.xpath('//ul[@id="individual-personInPosition"]/li')]
            if img_url is not None:
                img_res = requests.get(f'https://scholars.uab.edu{img_url}', headers=header)
                with open(rf"{path}\{label}.{img_url.split('.')[-1]}", 'wb') as img:
                    img.write(img_res.content)
            # qr_res, qr_src = '', ''
            # try:
            #     qr_src = ''.join(tree.xpath('//img[@id="qrIcon"]/@src')).strip()
            #     qr_res = requests.get(f'https://scholars.uab.edu{qr_src}', headers=header)
            #     print(qr_src, qr_res)
            #     with open(rf"{path}\{label}_qr.{qr_src.split('.')[-1]}", 'wb') as img:
            #         img.write(qr_res.content)
            # except Exception as e:
            #     print(e, qr_src, qr_res)
            #     pass
            tab_contents = tree.xpath('//div[@class="tab-content"]/child::div')
            for tab_content in tab_contents[:-1]:
                h2 = ''.join(tab_content.xpath('child::h2/text()'))
                panels = tab_content.xpath('descendant::div[@class="panel panel-default"]')
                for panel in panels:
                    p_head = ' '.join(
                        [__.strip() for __ in panel.xpath('div[@class="panel-heading"]/descendant::text()')]).strip()
                    table = panel.xpath('descendant::table[@class="table table-hover"]')
                    p_body = None
                    if len(table) > 0:
                        p_body = pandas.read_html(html.tostring(table[0]))[0]
                        p_body.to_csv(rf"{path}\{h2}_{p_head}.csv")
                    else:
                        p_body = [' '.join([_a.strip('\n\t ') for _a in __.xpath('descendant::text()')])
                                      .strip('\n\t ').replace('\n', ' ')
                                  for __ in panel.xpath('div[@class="panel-body"]/descendant::li')]
                        pandas.DataFrame(p_body, columns=[p_head]).to_csv(rf"{path}\{h2}_{p_head}.csv")
            pro_data['email'] = email
            pro_data['phone'] = phone
            pro_data['position'] = position
            with open(rf"{path}\{label}.json", 'w') as jfile_save:
                json.dump(pro_data, jfile_save)
        statusBar.update(1)


def GetIndDetails(workers=4):
    global driver_path, data
    driver_path = ChromeDriverManager().install()
    individual = data.get('individuals', None)
    if individual is None:
        with open('individuals.json', 'r') as jfile:
            jdata = json.load(jfile)
            individual = jdata['individuals']
    workload_per = math.ceil(len(individual) / workers)
    threads = []
    with tqdm(total=len(individual), desc='profiles')as bar:
        for i in range(workers):
            start = i * workload_per
            end = (i + 1) * workload_per if len(individual) > (i + 1) * workload_per else len(individual)
            t = threading.Thread(target=Get_Sel, args=(individual[start:end], bar))  # selenium
            # t = threading.Thread(target=Get_req, args=(individual[start:end], bar)) # requests

            t.start()
            threads.append(t)
        for thr in threads:
            thr.join()


# GetFacultyLinks()
GetIndDetails(4)
