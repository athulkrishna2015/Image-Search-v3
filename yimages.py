import re
import json
import requests
import urllib.parse

from . import utils

requests.packages.urllib3.disable_warnings()

BASE_URL = 'https://yandex.ru/images/search?format=json&request={%22blocks%22:[{%22block%22:%22serp-list_infinite_yes%22,%22params%22:{},%22version%22:2}]}&text='
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.67 Safari/537.36"
}


def make_yimages_url(query):
    return BASE_URL + urllib.parse.quote_plus(query)


def get_yimages_response(query):
    url = make_yimages_url(query)
    try:
        r = requests.get(url, verify=False, headers=headers)
        return r.json()
    except:
        utils.report('Request error\n\n' + url)
        return None


def parse_yimages_response(response):
    result = []

    try:
        block = response['blocks'][0]
        assert block['name']['block'] == 'serp-list_infinite_yes'

        html = block['html']
        assert len(html) > 0
        assert 'data-bem' in html
        assert 'serp-item' in html
    except Exception as e:
        utils.report('Error parsing json response\n\n' + repr(e))
        return result

    # undocumented unofficial parsing of Yandex Images response 
    # (get item json from html string in json response)
    found = re.findall(r"data-bem='{.serp-item.:(.*?)}'", html)
    for item in (found or []):
        try:
            item_json = json.loads(item)
            image_url = 'https:' + item_json['thumb']['url'].replace('&amp;', '&')
            result.append(image_url)
        except:
            pass

    return result


def get_yimages(query):
    response = get_yimages_response(query)
    return parse_yimages_response(response)
