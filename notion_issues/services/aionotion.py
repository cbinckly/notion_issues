import os
import urllib
import logging
import asyncio
import argparse
from pprint import pformat, pprint

from aio_api_sm import AioApiSessionManager
from notion_issues.services import PaginatedList
from notion_issues.logger import Logger

log = Logger('notion_issues.services.aionotion')

defaults = {
        'notion_token': os.environ.get("NOTION_TOKEN"),
        'notion_database_id': 'unset',
        }

class AioNotion:

    api_version = '2022-06-28'
    api_base = "https://api.notion.com/"
    paths = {
                'search': 'search',
                'database': 'databases/{database_id}',
                'database.query': 'databases/{database_id}/query',
                'pages': 'pages',
                'page': 'pages/{page_id}',
                'page.property': 'pages/{page_id}/properties/{property_id}',
                'comments': 'comments'
            }

    limit_per_host = 10 # notion rate limits at 3 requests/second
    ttl_dns_cache = 60

    def __init__(self, token, rate_limit=5, burst_limit=20):
        self.token = token
        self.properties_queue = asyncio.Queue()
        self.properties_cache = {}
        self._request_manager = AioApiSessionManager(
                self.api_base, headers=self.headers,
                rate_limit=rate_limit, rate_limit_burst=burst_limit)
        self.__session = None

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
            encoded_params = urllib.parse.urlencode(uri_params)
            uri_path = f"{uri_path}?{encoded_params}"
        #return f"{self.api_base}{uri_path}"
        return f"/v1/{uri_path}"

    async def close(self):
        await self._request_manager.close()

    async def database_id_for_name(self, name):
        url = self.url("search")

        payload = {"query": name, "filter": {"property": "object", "value": "database"}}

        resp_json = await self._request_manager.post(url, json=payload)

        for result in resp_json.get('results', []):
            if result['title']:
                if result['title'][0]['plain_text'].lower() == name.lower():
                    return result['id']

        return None

    async def get_database(self, database_id):
        url = self.url('database', {'database_id': database_id})

        resp_json = await self._request_manager.request('get', url)

        return resp_json

    async def database_query(self, database_id, filters={}, sorts=[]):
        url = self.url('database.query', {'database_id': database_id})

        payload = {}
        if filters:
            payload['filter'] = filters
        if sorts:
            payload['sorts'] = sorts

        resp_json = await self._request_manager.request('post', url, json=payload)
        resp_json['results'] = PaginatedList(
                self, "post", url, body=payload, last_resp=resp_json)
        return resp_json

    async def add_page_to_database(self, database_id, properties):
        url = self.url('pages')

        payload = {
                "parent": {
                    "type": "database_id",
                    "database_id": database_id },
                "properties": properties
            }

        resp_json = await self._request_manager.request('post', url, json=payload)

        return resp_json

    async def get_page(self, page_id, props=False, comments=False):
        url = self.url('page', {'page_id': page_id})

        resp_json = await self._request_manager.request('get', url)
        if props:
            pf = PropertyFetcher(self)
            await pf.fetch_properties(page_id, resp_json['properties'])
            resp_json['properties'] = pf.properties
        if comments:
            resp_json['comments'] = await self.get_comments(page_id)

        return resp_json

    async def get_comments(self, page_id):
        url = self.url('comments', {}, {'block_id': page_id})
        resp_json = await self._request_manager.request('get', url)

        resp_json['results'] = PaginatedList(self, 'get', url, last_resp=resp_json)

        return resp_json

    async def update_page(self, page_id, properties={}, archived=False):
        url = self.url('page', {'page_id': page_id})

        payload = {'properties': properties, 'archived': archived}

        resp_json = await self._request_manager.request(
                'patch', url, json=payload)

        return resp_json

    async def get_property(self, page_id, property_id):
        url = self.url('page.property', {'page_id': page_id,
                                'property_id': property_id})

        resp_json = await self._request_manager.request('get', url)
        if resp_json.get('object') == 'list':
            resp_json['results'] = PaginatedList(
                    self, 'get', url, last_resp=resp_json)

        return resp_json

    async def flatten_property_values(self, properties):
        """Flatten property values."""
        _properties = {}
        for key, property_info in properties.items():
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
            else:
                _type = property_info.get('property_item', {}).get('type')
                results = property_info.get('results', [])
                if _type == 'title':
                    components = [i['title']['plain_text'] async for i in results]
                elif _type == 'rich_text':
                    components = [i['rich_text']['plain_text'] async for i in results]
                value = " ".join(components)

            _properties[key] = value

        return _properties

async def test_db_fetch():
    import os
    from pprint import pprint
    from datetime import datetime
    from notion_issues.helpers.notion import DatabaseFetcher

    now = datetime.now()
    notion = AioNotion(os.environ.get("NOTION_TOKEN"), rate_limit=5, burst_limit=30)
    dbid = await notion.database_id_for_name("Issues")
    print(dbid)
    _filter = { "property": "Issue Key",
                      "rich_text": {
                          "starts_with": "RFPIO"
                      }
              }
    database_fetcher = DatabaseFetcher(notion)
    print("fetching")
    pages = await database_fetcher.fetch_database(dbid, _filter, comments=True)
    pprint(pages[-1])
    print(f"time: {datetime.now() - now} seconds, {len(pages)} pages")
    await notion.close()

if __name__ == '__main__':
    Logger.verbose()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_db_fetch())
    except asyncio.exceptions.CancelledError:
        log.error('Cancelled.')
    except Exception as err:
        msg = (f"Exception {err} raised.")
        log.error(msg, exc_info=True)
        print(msg)
