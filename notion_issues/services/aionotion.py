import os
import urllib
import logging
import asyncio
import argparse
from pprint import pformat, pprint

from aio_api_sm import AioApiSessionManager
from notion_issues.logger import Logger

log = Logger(__name__)

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
            encoded_params = urllib.urlencode(uri_params)
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

        resp_json = await self._request_manager.post(url, json=payload)

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

    async def get_page(self, page_id, props=False):
        url = self.url('page', {'page_id': page_id})

        resp_json = await self._request_manager.request('get', url)
        if props:
            pf = PropertyFetcher(self)
            await pf.fetch_properties(page_id, resp_json['properties'])
            resp_json['properties'] = pf.properties

        return resp_json

    async def update_page(self, page_id, properties={}, archived=False):
        url = self.url('page', {'page_id': page_id})

        payload = {'properties': properties, 'archived': archived}

        resp_json = await self._request_manager.request('patch', url, json=payload)

        return resp_json

    async def get_property(self, page_id, property_id):
        url = self.url('page.property', {'page_id': page_id,
                                'property_id': property_id})

        resp_json = await self._request_manager.request('get', url)

        return resp_json

    async def property_values(self, page_id, properties):
        """Get and flatten property values."""
        _properties = {}
        for key, info in properties.items():
            property_info = await self.get_property(page_id, info['id'])
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

class PropertyFetcher:

    def __init__(self, notion):
        self.notion = notion
        self.properties = {}

    async def _consume_queue(self, q):
        try:
            while True:
                page_id, property_name, property_id = await q.get()
                if not (page_id and property_id):
                    return
                log.debug(f"{page_id}: get property {property_id}")
                prop = await self.notion.get_property(page_id, property_id)
                self.properties[property_name] = prop
        except Exception as e:
            log.error(f"_property_queue_handler failed: {e}")

    async def _fetch_properties(self, page_id, properties):
        q = asyncio.Queue()
        concurrency = len(properties)
        for name, _id in properties.items():
            await q.put((page_id, name, _id['id']))
        for _ in range(0, concurrency):
            await q.put((None, None, None))

        executors = [self._consume_queue(q) for _ in range(0, concurrency)]
        await asyncio.gather(*executors)

    async def fetch_properties(self, page_id, properties):
        await self._fetch_properties(page_id, properties)
        return self.properties

class DatabaseFetcher:

    def __init__(self, notion):
        self.notion = notion
        self.pages = []

    async def _consume_queue(self, q):
        try:
            while True:
                page = await q.get()
                if not page:
                    return
                log.debug(f"{page['id']}: call property fetcher")
                property_fetcher = PropertyFetcher(self.notion)
                properties = await property_fetcher.fetch_properties(
                        page['id'], page['properties'])
                page['properties'] = properties
                self.pages.append(page)
        except Exception as e:
            log.error(f"_consume_queue failed: {e}")

    async def _fetch_database(self, database_id, _filter):
        q = asyncio.Queue()
        concurrency = 10

        pages = await self.notion.database_query(database_id, _filter)
        if not pages.get('results'):
            log.info(f"{pformat(pages)} entries in DB")
        for page in pages.get('results', []):
            await q.put(page)
        for _ in range(0, concurrency):
            await q.put(None)

        executors = [self._consume_queue(q) for _ in range(0, concurrency)]
        await asyncio.gather(*executors)

    async def fetch_database(self, database_id, _filter):
        await self._fetch_database(database_id, _filter)
        return self.pages

async def test_db_fetch():
    import os
    from pprint import pprint
    from datetime import datetime

    now = datetime.now()
    notion = AioNotion(os.environ.get("NOTION_TOKEN"), rate_limit=5, burst_limit=30)
    dbid = await notion.database_id_for_name("Issues")
    _filter = { "property": "Issue Key",
                      "rich_text": {
                          "starts_with": "RFPIO"
                      }
              }
    database_fetcher = DatabaseFetcher(notion)
    pages = await database_fetcher.fetch_database(dbid, _filter)
    # pprint(pages)
    print(f"time: {datetime.now() - now} seconds, {len(pages)} pages")
    await notion.close()

if __name__ == '__main__':
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_db_fetch())
    except asyncio.exceptions.CancelledError:
        log.error('Cancelled.')
    except Exception as err:
        msg = (f"Exception {err} raised.")
        log.error(msg, exc_info=True)

