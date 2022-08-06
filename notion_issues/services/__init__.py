import logging
from pprint import pprint

from notion_issues.logger import Logger

log = Logger('notion_issues.services.paginated_list')

class PaginatedList:
    """It should act like a list."""

    def __init__(self, client, method, url, params={}, body={}, last_resp={}):
        self._client = client
        self._method = method.lower()
        self._base_url = url
        self._base_params = params
        self._base_body = body
        self._last_resp = last_resp
        self._list = []
        if self._last_resp:
            self._list.extend(self._last_resp['results'])
        log.debug(f"{self}")

    def __str__(self):
        return (f"PaginatedList({self._client}, {self._method}, {self._base_url}, "
                f"{self._base_params}, {self._base_body}) [{len(self._list)}]")

    @property
    def __fetched(self):
        return bool(self._last_resp)

    async def __has_more(self):
        if not self._last_resp:
            await self.__fetch_next()
        return bool(self._last_resp.get("has_more"))

    def _has_index(self, index):
        return index < len(self._list)

    @property
    def __next_cursor(self):
        return self._last_resp.get('next_cursor')

    async def __fetch_next(self):
        if self._method == 'get':
            params = self._base_params.copy()
            if self.__next_cursor:
                params['start_cursor'] = self.__next_cursor
            log.debug(f'getting next ({self._method} {self._url}?{params}).')
            self._last_resp = await self._client._request_manager.request(
                    self._method, self._base_url, params=params)
        elif self._method == 'post':
            body = self._base_body.copy()
            if self.__next_cursor:
                body['start_cursor'] = self.__next_cursor
            log.debug(f'posting next ({self._method} {self._base_url} {body}).')
            self._last_resp = await self._client._request_manager.request(
                    self._method, self._base_url, json=body)
        else:
            raise RuntimeError(
                    f"{self._method} is not supported by paginated list")

        results = self._last_resp.get('results', [])
        if results:
            self._list.extend(self._last_resp['results'])

        return results

    async def __fetch_to(self, index):
        has_more = await self.__has_more()
        while has_more and len(self._list) < index:
            await self.__fetch_next()
            has_more = await self.__has_more
        return len(self._list) > index

    async def __aiter__(self):
        if not self.__fetched:
            await self.__fetch_next()
        for l in self._list:
            yield l
        has_more = await self.__has_more()
        while has_more:
            new = await self.__fetch_next()
            for n in new:
                yield n
            has_more = await self.__has_more()
        return

    async def __getitem__(self, index):
        if isinstance(index, int):
            fetched_to_index = await self.__fetch_to(index)
            if fetched_to_index:
                return self._list[index]
            raise IndexError(f"{self} doesn't have index {index}")
        elif isinstance(index, slice):
            return PaginatedSlice(self, index)
        else:
            raise IndexError(f"cannot get index {index} {type(index)}")

class PaginatedSlice():

    def __init__(self, paginated_list, _slice):
        self._list = paginated_list
        self.__start = _slice.start or 0
        self.__stop = _slice.stop
        self.__step = _slice.step or 1
        log.debug(f"new paginated slice {paginated_list}[{slice}]")

    async def __aiter__(self):
        log.debug('in __aiter__')
        index = self.__start
        while not self.__finished(index):
            if self._list._has_index(index):
                yield await self._list[index]
            elif self._list.__has_more():
                fetched_to_index = self._list.__fetch_to(index)
                if fetched_to_index:
                    yield await self._list[index]
                else:
                    return
            index += self.__step

    def __finished(self, index):
        return self.__stop is not None and index >= self.__stop

async def main():
    import os
    from pprint import pprint
    from notion_issues.services.aionotion import AioNotion

    notion = AioNotion(os.environ.get("NOTION_TOKEN"))
    db_id = await notion.database_id_for_name("Issues")
    _filter = {}
    pprint(f"Issues: {db_id}")
    url = notion.url('database.query', {'database_id': db_id})
    _list = PaginatedList(notion, 'post', url, body={'page_size': 100})
    async for item in _list:
        pprint(f"all: {item['id']}")
    async for item in await _list[1:3]:
        pprint(f"some: {item['id']}")
    l2 = await _list[2]
    print(l2['id'])
    pprint([l['id'] for l in _list._list])

if __name__ == '__main__':
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except asyncio.exceptions.CancelledError:
        log.error('Cancelled.')
    except Exception as err:
        msg = (f"Exception {err} raised.")
        log.error(msg, exc_info=True)

