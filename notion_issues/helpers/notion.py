import asyncio

from notion_issues.logger import Logger

log = Logger('notion_issues.helpers.notion')

class NotionHelper():

    def __init__(self, notion):
        self.notion = notion

    def get_page(self, page_id, props, comments):
        pass

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
                page, comments = await q.get()
                if not page:
                    return
                log.debug(f"{page['id']}: call property fetcher")
                property_fetcher = PropertyFetcher(self.notion)
                properties = await property_fetcher.fetch_properties(
                        page['id'], page['properties'])
                page['properties'] = properties
                if comments:
                    page['comments'] = await self.notion.get_comments(page['id'])
                self.pages.append(page)
        except Exception as e:
            log.error(f"_consume_queue failed: {e}")

    async def _fetch_database(self, database_id, _filter, comments):
        q = asyncio.Queue()
        concurrency = 10

        pages = await self.notion.database_query(database_id, _filter)
        if not pages.get('results'):
            log.info(f"{pformat(pages)} entries in DB")
        for page in pages.get('results', []):
            await q.put((page, comments))
        for _ in range(0, concurrency):
            await q.put((None, None))

        executors = [self._consume_queue(q) for _ in range(0, concurrency)]
        await asyncio.gather(*executors)

    async def fetch_database(self, database_id, _filter, comments=False):
        await self._fetch_database(database_id, _filter, comments)
        return self.pages
