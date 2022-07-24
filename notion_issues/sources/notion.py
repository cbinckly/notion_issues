import os
import sys
import urllib
import requests
from pprint import pformat, pprint

from notion_issues import IssueSource, unassigned_user
from notion_issues.services.notion import Notion

class NotionSource(IssueSource):

    closed_statuses = ['closed', 'resolved']

    def __init__(self, notion_token, notion_database):
        self.notion = Notion(notion_token)
        self.notion_database = notion_database
        self.notion_database_id = self.notion.database_id_for_name(
                    notion_database)
        self.page_id_map = {}

    def get_issues(self, issue_key_filter=""):
        output = {}
        _filter = {}
        if issue_key_filter:
            _filter = { "property": "Issue Key",
                              "rich_text": {
                                  "starts_with": issue_key_filter
                              }
                      }
        notion_items = self.notion.database_query(
                self.notion_database_id, _filter)

        for item in notion_items['results']:
            page_details = self.notion.get_page(item['id'])
            page_properties = self.notion.property_values(
                    item['id'], page_details['properties'])
            key = page_properties['Issue Key']


            output[key] = {
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
                                    page_details['last_edited_time']),
                  "link": page_properties['Link'],
            }

            self.page_id_map[key] = item['id']

        return output

    def update_issue(self, key, issue_dict):
        properties = self._issue_dict_to_properties(key, issue_dict)
        page_id = self.page_id_map[key]
        resp = self.notion.update_page(page_id, properties)

        return resp

    def create_issue(self, key, issue_dict):
        properties = self._issue_dict_to_properties(key, issue_dict)
        resp = self.notion.add_page_to_database(
                self.notion_database_id, properties)
        return resp

    def archive_issue(self, key):
        page_id = self.page_id_map[key]
        resp = self.notion.update_page(page_id, archived=True)
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
                "Reporter": {
                    "select": { "name": issue_dict['reporter'] }
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

        return properties

    def __str__(self):
        return f"Notion Source: {self.notion_database}"

if __name__ == '__main__':
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_database = sys.argv[1]

    source = NotionSource(notion_token, notion_database)
    pprint(source.get_issues())
