import os
import sys
import urllib
import requests
from datetime import datetime, timedelta, timezone
from pprint import pformat, pprint

from notion_issues import unassigned_user
from notion_issues.sources import IssueSource
from notion_issues.services.aionotion import AioNotion
from notion_issues.helpers.notion import PropertyFetcher, DatabaseFetcher
from notion_issues.logger import Logger

log = Logger('notion_issues.sources.notion')

class NotionSource(IssueSource):

    closed_statuses = ['closed', 'resolved']

    def __init__(self, notion_token, notion_database):
        self.notion = AioNotion(notion_token, rate_limit=5, burst_limit=35)
        self.notion_database = notion_database
        self.__notion_database_id = None
        self.page_id_map = {}

    async def notion_database_id(self):
        if not self.__notion_database_id:
            self.__notion_database_id  = await self.notion.database_id_for_name(
                        self.notion_database)
        return self.__notion_database_id

    async def close(self):
        await self.notion.close()

    def id_to_key(self, _id):
        for issue_key, page_id in self.page_id_map.values():
            if page_id == _id:
                return issue_key
        return ""

    async def key_to_id(self, key):
        if key in self.page_id_map:
            return self.page_id_map.get(key)

        _filter = {
                "property": "Issue Key",
                "rich_text": {
                        "equals": key
                    }
                }
        db_id = await self.notion_database_id()
        results = await self.notion.database_query(db_id, _filter)
        pages = results.get('results')
        if pages:
            return pages[0]['id']

        return None

    def _issue_to_issue_dict(self, page, page_properties):
        output = {
              "title": page_properties['Title'],
              "status": page_properties['Status'],
              "assignee": page_properties['Assignee'],
              "reporter": page_properties['Reporter'],
              "labels": page_properties['Labels'],
              "due_on": self.normalize_date(
                                page_properties['Due Date']),
              "opened_on": self.normalize_date(
                                page_properties['Opened On']),
              "updated_on": self.normalize_date(
                                page['last_edited_time']),
              "link": page_properties['Link'],
        }
        return output

    async def get_issue(self, _id):
        page = await self.notion.get_page(_id)
        pf = PropertyFetcher(self.notion)
        props = await pf.fetch_properties(page['id'], page['properties'])
        self.page_id_map[props['Issue Key']] = page['id']
        return self._issue_to_issue_dict(page, props)

    async def get_issues(self, issue_key_filter="", since=None, assignee=None):
        output = {}
        _filters = []

        if issue_key_filter:
            _filters.append({ "property": "Issue Key",
                              "rich_text": {
                                  "starts_with": issue_key_filter
                              }
                      })

        if since:
            _filters.append({
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "after": self.normalize_date(since)
                    }
                })

        if assignee:
            _filters.append({
                    "property": "Assignee",
                    "select": {
                        "equals": assignee
                    }
                })

        _filter = {}
        if _filters:
            if len(_filters) > 1:
                _filter = { "and": _filters }
            else:
                _filter = _filters[0]

        log.debug(f'notion filter: {pformat(_filter)}')

        dbf = DatabaseFetcher(self.notion)
        db_id = await self.notion_database_id()
        pages = await dbf.fetch_database(db_id, _filter, comments=True)

        output = {}
        for page in pages:
            pprint(page)
            key = page['properties']['Issue Key']
            props = self._issue_to_issue_dict(page, page['properties'])
            output[key] = props
            self.page_id_map[key] = page['id']

        return output

    async def update_issue(self, key, issue_dict):
        properties = self._issue_dict_to_properties(key, issue_dict)
        page_id = self.page_id_map[key]
        resp = await self.notion.update_page(page_id, properties)

        return resp

    async def create_issue(self, key, issue_dict):
        properties = self._issue_dict_to_properties(key, issue_dict)
        db_id = await self.notion_database_id()
        resp = await self.notion.add_page_to_database(db_id, properties)
        return resp

    async def archive_issue(self, key):
        page_id = self.page_id_map[key]
        resp = await self.notion.update_page(page_id, archived=True)
        return resp

    def _issue_dict_to_properties(self, key, issue_dict):
        properties = {
                "Title": {
                    "title": [
                        { "text": { "content": issue_dict['title'] },
                          "href": issue_dict['link']
                        }
                    ]
                },
                "Assignee": {
                    "select": { "name": issue_dict['assignee'] }
                },
                "Labels": {
                    "multi_select": [
                        { "name": i } for i in issue_dict['labels']
                    ]
                },
                "Status": {
                    "select": { "name": issue_dict['status'] }
                },
                "Issue Key": {
                    "rich_text": [{
                        "type": "text",
                        "text": {
                            "content": key
                        }
                    }]
                },
                "Opened On": {
                    "date": { "start": issue_dict['opened_on'] }
                },
                "Updated On": {
                    "date": { "start": issue_dict['updated_on'] }
                },
                "Link": {
                    "url": issue_dict['link']
                }
            }

        if issue_dict['due_on']:
            properties["Due Date"] = {
                    "date": { "start": issue_dict['due_on'] }
                }
        if issue_dict['reporter']:
            properties["Reporter"] = {
                    "select": { "name": issue_dict['reporter'] }
                }

        return properties

    def __str__(self):
        return f"Notion Source: {self.notion_database}"


async def test_source():
    import os
    from pprint import pprint
    from datetime import datetime

    since = datetime.now(timezone.utc) - timedelta(seconds=60*60*24*5)
    notion = NotionSource(os.environ.get("NOTION_TOKEN"), "Issues")
    pages = await notion.get_issues(since=since)
    pprint(pages)
    await notion.close()

if __name__ == '__main__':
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_source())
    except asyncio.exceptions.CancelledError:
        log.error('Cancelled.')
    except Exception as err:
        msg = (f"Exception {err} raised.")
        log.error(msg, exc_info=True)

