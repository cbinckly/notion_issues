import os
import asyncio
import urllib
import requests
import argparse
from pprint import pformat, pprint

from notion_issues.logger import Logger

log = Logger(__name__)

defaults = {
        'notion_token': os.environ.get("NOTION_TOKEN"),
        'notion_database_id': 'unset',
        }

class Notion:

    api_version = '2022-06-28'
    api_base = "https://api.notion.com/v1/"
    paths = {
                'search': 'search',
                'database': 'databases/{database_id}',
                'database.query': 'databases/{database_id}/query',
                'pages': 'pages',
                'page': 'pages/{page_id}',
                'page.property': 'pages/{page_id}/properties/{property_id}',
            }

    def __init__(self, token):
        self.token = token

    @property
    def headers(self):
        return {
            "Accept": "application/json",
            "Notion-Version": self.api_version,
            "Authorization": f"Bearer {self.token}"
        }

    def url(self, name, path_params={}, uri_params={}):
        uri_path = self.paths[name].format(**path_params)
        if uri_params:
            encoded_params = urllib.urlencode(uri_params)
            uri_path = f"{uri_path}?{encoded_params}"
        return f"{self.api_base}{uri_path}"

    def database_id_for_name(self, name):
        url = self.url("search")

        payload = {"query": name, "filter": {"property": "object", "value": "database"}}

        response = requests.post(url, json=payload, headers=self.headers)
        resp_json = response.json()

        for result in resp_json.get('results', []):
            if result['title']:
                if result['title'][0]['plain_text'].lower() == name.lower():
                    return result['id']

        return None

    def get_database(self, database_id):
        url = self.url('database', {'database_id': database_id})

        response = requests.get(url, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def database_query(self, database_id, filters={}, sorts=[]):
        url = self.url('database.query', {'database_id': database_id})

        payload = {}
        if filters:
            payload['filter'] = filters
        if sorts:
            payload['sorts'] = sorts

        response = requests.post(url, json=payload, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def add_page_to_database(self, database_id, properties):
        url = self.url('pages')

        payload = {
                "parent": {
                    "type": "database_id",
                    "database_id": database_id },
                "properties": properties
            }

        response = requests.post(url, json=payload, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def get_page(self, page_id):
        url = self.url('page', {'page_id': page_id})

        response = requests.get(url, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def update_page(self, page_id, properties={}, archived=False):
        url = self.url('page', {'page_id': page_id})

        payload = {'properties': properties, 'archived': archived}

        response = requests.patch(url, json=payload, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def get_property(self, page_id, property_id):
        url = self.url('page.property', {'page_id': page_id,
                                'property_id': property_id})

        response = requests.get(url, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def property_values(self, page_id, properties):
        """Get and flatten property values."""
        _properties = {}
        for key, info in properties.items():
            property_info = self.get_property(page_id, info['id'])
            value = property_info

            _object = property_info.get('object')
            if _object == 'property_item':
                _type = property_info.get('type')
                if _type == 'multi_select':
                    value = [i['name'] for i in property_info['multi_select']]
                elif _type == 'url':
                    value = property_info['url']
                elif _type == 'select':
                    value = ""
                    if property_info.get('select'):
                        value = property_info['select']['name']
                elif _type == 'date':
                    value = ""
                    if property_info.get('date'):
                        value = property_info['date']['start']
            elif _object == 'list':
                _type = property_info.get('property_item', {}).get('type')
                if _type == 'title':
                    results = property_info.get('results', [])
                    components = [i['title']['plain_text'] for i in results]
                    value = " ".join(components)
                elif _type == 'rich_text':
                    results = property_info.get('results', [])
                    components = [i['rich_text']['plain_text'] for i in results]
                    value = " ".join(components)

            _properties[key] = value

        return _properties

def test_page_fetch():
    import os
    from pprint import pprint
    from datetime import datetime

    now = datetime.now()
    notion = Notion(os.environ.get("NOTION_TOKEN"))
    dbid = notion.database_id_for_name("Project Issues")
    pages = notion.database_query(dbid, "")
    page_info = pages['results'][0]
    page_details = notion.get_page(page_info['id'])
    page_details['properties'] = notion.property_values(
            page_info['id'], page_details['properties'])
    pprint(page_details)
    print(f"time: {datetime.now() - now} seconds")

def test_db_fetch():
    import os
    from pprint import pprint
    from datetime import datetime

    now = datetime.now()
    notion = Notion(os.environ.get("NOTION_TOKEN"))
    dbid = notion.database_id_for_name("Issues")
    pages = notion.database_query(dbid, "")
    full_pages = []
    for page in pages['results']:
        page['properties'] = notion.property_values(
                page['id'], page['properties'])
    pprint(pages)
    print(f"time: {datetime.now() - now} seconds")

if __name__ == '__main__':
    # test_page_fetch()
    test_db_fetch()

