from pprint import pformat
from dateutil import parser
from datetime import datetime, timedelta, timezone

from notion_issues.logger import Logger

log = Logger('notion_issues.issue_sync')
unassigned_user = "unassigned"

class IssueSync:

    ignore_fields = ['updated_on', 'opened_on', 'reporter', 'link']

    def __init__(self, create_closed=False, create_assignee='',
            since="", archive_aged=7):
        self.create_closed = create_closed
        self.create_assignee = create_assignee
        self.archive_aged = archive_aged
        self.since = since

    def issues_equal(self, notion_issue, other_issue):
        notion_filtered = {k: v for k, v in notion_issue.items()
                                if k not in self.ignore_fields}
        other_filtered = {k: v for k, v in other_issue.items()
                               if k not in self.ignore_fields}
        return sorted(notion_filtered.items()) == sorted(other_filtered.items())

    def _source_kwargs(self):
        kwargs = {}
        if self.create_assignee:
            kwargs['assignee'] = self.create_assignee
        if self.since:
            kwargs['since'] = self.since
        return kwargs

    async def sync_sources(self, notion_source, other_source, issue_key_filter=""):
        source_kwargs = self._source_kwargs()
        source_issues = other_source.get_issues(**source_kwargs)
        notion_issues = await notion_source.get_issues(issue_key_filter, since=self.since)

        threshold = datetime.now(timezone.utc) - timedelta(seconds=60*60*24*self.archive_aged)

        missing_notion = set(source_issues.keys()) - set(notion_issues.keys())
        missing_other = set(notion_issues.keys()) - set(source_issues.keys())

        log.debug(f"notion_source missing keys: {missing_notion}")
        log.debug(f"other_source missing keys: {missing_other}")

        for key in missing_notion:
            _id = await notion_source.key_to_id(key)
            if _id:
                issue = await notion_source.get_issue(_id)
                if issue:
                    notion_issues[key] = issue

        for key in missing_other:
            _id = other_source.key_to_id(key)
            if _id:
                issue = other_source.get_issue(_id)
                if issue:
                    source_issues[key] = issue

        log.info(f"sync {notion_source}({issue_key_filter}) and {other_source}")
        log.debug(f"notion({len(notion_issues)}), other({len(source_issues)})")
        log.debug(f"Notion: {pformat(notion_issues)}")
        log.debug(f"Other: {pformat(source_issues)}")

        for key, issue_dict in source_issues.items():
            log.debug(f"{key}: assessing.")
            if key in notion_issues:
                log.debug(f"{key}: exists in notion")
                notion_issue = notion_issues[key]
                if not self.issues_equal(notion_issue, issue_dict):
                    if issue_dict['updated_on'] > notion_issue['updated_on']:
                        log.debug(f"{key}: other source is newer")
                        log.debug(f"{key}: updating with {pformat(issue_dict)}")
                        await notion_source.update_issue(key, issue_dict)
                        log.info(f"{key}: notion updated successfully.")
                    else:
                        log.debug(f"{key}: notion source is newer")
                        log.debug(f"{key}: updating with {pformat(notion_issue)}")
                        other_source.update_issue(key, notion_issue)
                        log.info(f"{key}: other source updated successfully.")
                else:
                    log.info(f"{key} in sync.")

                if self.archive_aged:
                    if issue_dict['status'] in other_source.closed_statuses:
                        last_edit = parser.isoparse(notion_issue['updated_on'])
                        if last_edit < threshold:
                            log.info(f"{key}: archiving aged issue.")
                            await notion_source.archive_issue(key)

            else:
                log.debug(f"{key}: does not exist in notion")
                if not self.create_closed:
                    if issue_dict['status'] in other_source.closed_statuses:
                        log.debug(f'{key}: not creating closed issue.')
                        continue

                if self.create_assignee:
                    if issue_dict['assignee'] != self.create_assignee:
                        log.debug(f'{key}: not for {self.create_assignee}')
                        continue

                resp = await notion_source.create_issue(key, issue_dict)
                log.debug(f"{key}: {pformat(resp)}")
                if 'status' in resp:
                    log.error(f'failed to create in notion: {pformat(resp)}')
                else:
                    log.info(f"{key}: created in notion.")
