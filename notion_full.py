import os
import urllib
import requests
import argparse
from pprint import pformat, pprint

from jira import JIRA

defaults = {
        'notion_token': os.environ.get("NOTION_TOKEN"),
        'notion_database_id': 'unset',
        }

def parse_args():
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-nt', '--notion-token', type=str, required=True,
            default=defaults['notion_token'],
            help=f"Notion Token. Default: {defaults['notion_token']}")
    parser.add_argument('-db', '--notion-database', type=str, required=True,
            default=defaults['notion_database_id'],
            help=f"Notion Database ID. Default: {defaults['notion_database_id']}")
    return parser.parse_args()

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
        uri_path = path.format(**path_params)
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
                **properties
            }

        response = requests.post(url, json=payload, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def get_page(self, page_id):
        url = self.url('pages', {'page_id': page_id})

        response = requests.get(url, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def update_page(self, page_id, properties):
        url = self.url('page', {'page_id': page_id})

        payload = {'properties': properties}

        response = requests.patch(url, json=payload, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def get_property(self, page_id, property_id):
        url = self.url('page', {'page_id': page_id,
                                'property_id': property_id})

        response = requests.get(url, headers=self.headers)
        resp_json = response.json()

        return resp_json

    def property_values(self, page_id, properties):
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
                    value = property_info['select']['name']
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

class NotionPropertyType():

    def from_json(self):
        raise NotImplementedError('Implement in child.')

    def to_json(self):
        raise NotImplementedError('Implement in child.')

class Number(NotionPropertyType):

    object_type = "property_item"

    def __init__(self, name, value):
        self.property_id = None
        self.page_id = None
        self.name = name
        self.value = value

    @classmethod
    def from_json(cls, _json):
        self.property_id = _json.get("id")
        self.value = _json.get("number")

    def to_json(self):
        _dict = { "object": self.object_type,
                  "type": "number",
                  "value": value }
        if self.property_id:
            _dict['id'] = self.propery_id

        return _dict


class MultiSelectEntry:
    def __init__(self, name, value):

class MultiSelect(NotionPropertyType):

    object_type = "property_item"

    def __init__(self, name, values):
        self.property_id = None
        self.page_id = None
        self.name = name
        self.values = values

    @classmethod
    def from_json(cls, _json):
        self.property_id = _json.get("id")
        self.value = _json.get("multi_select")

    def to_json(self):
        _dict = { "object": self.object_type,
                  "type": "number",
                  "value": value }
        if self.property_id:
            _dict['id'] = self.propery_id

        return _dict


def notion_page_properties_for(key, name, assignee, status, due_date, url):

    properties = {
            "properties": {
                "Name": {
                    "title": [
                        { "text": { "content": name } }
                    ]
                },
                "Assignee": {
                    "multi_select": [
                        { "name": assignee }
                    ]
                },
                "Status": {
                    "select": { "name": status }
                },
                "Issue Key": {
                    "rich_text": [{
                        "type": "text",
                        "text": {
                            "content": issue_key
                        }
                    }]
                },
                "Link": {
                    "url": url
                }
            }
        }

    return properties

if __name__ == '__main__':

    args = parse_args()

    notion = Notion(args.notion_token)
    db_id = notion.database_id_for_name(args.notion_database)
    pprint(notion.get_database(db_id))
    '''
    items = notion.database_query(db_id, {})
    for item in items['results']:
        page_details = notion.substitute_page_properties(notion.get_page(item['id']))
        pprint(page_details)
    properties = create_jira_issue_page_properties(
            "RFPIO-0", "Test Issue", "cbinckly", "open",
            "https://jira.junipercloud.net/it/browse/RFPIO-8")
    '''



