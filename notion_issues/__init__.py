from dateutil import parser

ISO_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
ISO_UTC_MIN_FMT = "%Y-%m-%dT%H:%M:00Z"
unassigned_user = "unassigned"

def get_intermediate_representation_template():
    return { "<issue_key>": {
                  "issue_key": "",
                  "title": "",
                  "status": "",
                  "assignee": "",
                  "reporter": "",
                  "labels": [],
                  "due_on": "",
                  "opened_on": "",
                  "closed_on": "",
                  "updated_on": "",
                  "link": ""
              }
           }

class IssueSource():

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Implement in child.")

    def normalize_date(self, date, granularity='seconds'):
        if not date:
            return ""
        if isinstance(date, str):
            date = parser.isoparse(date)
        if granularity == 'seconds':
            return date.strftime(ISO_UTC_FMT)
        return date.strftime(ISO_UTC_MIN_FMT)

    def get_issues(self):
        """
        :returns: issues dict
        """
        raise NotImplementedError("Implement in child.")

    def update_issue(self, issue_key, issues_dict):
        """
        :param issue_key: unique issue key.
        :type issue_key: str
        :param issues_dict: issues dict containing issues to update.
        :type issues_dict: dict
        """
        raise NotImplementedError("Implement in child.")

    def __str__(self):
        raise NotImplementedError("Implement in child.")


class IssueSync:

    ignore_fields = ['updated_on']

    def __init__(self, create_closed=False,
                 create_assignee='', archive_aged=True):
        self.create_closed = create_closed
        self.create_assignee = create_assignee
        self.archive_aged = archive_aged

    def issues_equal(self, notion_issue, other_issue):
        notion_filtered = {k: v for k, v in notion_issue.items()
                                if k not in self.ignore_fields}
        other_filtered = {k: v for k, v in other_issue.items()
                               if k not in self.ignore_fields}
        return sorted(notion_filtered.items()) == sorted(other_filtered.items())

    def sync_sources(self, notion_source, other_source, issue_key_filter=""):
        source_issues = other_source.get_issues()
        notion_issues = notion_source.get_issues(issue_key_filter)

        log.info(f"sync {notion_source}({issue_key_filter}) and {other_source}")
        log.debug(f"notion({len(notion_issues)}), other({len(source_issues)})")

        threshold = datetime.now(timezone.utc) - timedelta(seconds=60*60*24*31)

        for key, issue_dict in source_issues.items():
            log.debug(f"{key}: assessing.")
            if key in notion_issues:
                log.debug(f"{key}: exists in notion")
                notion_issue = notion_issues[key]
                if not self.issues_equal(notion_issue, issue_dict):
                    if issue_dict['updated_on'] > notion_issue['updated_on']:
                        log.debug(f"{key}: other source is newer")
                        log.debug(f"{key}: updating with {pformat(issue_dict)}")
                        notion_source.update_issue(key, issue_dict)
                        log.info(f"{key}: notion updated successfully.")
                    else:
                        log.debug(f"{key}: notion source is newer")
                        log.debug(f"{key}: updating with {pformat(issue_dict)}")
                        other_source.update_issue(key, notion_issue)
                        log.info(f"{key}: other source updated successfully.")
                else:
                    log.info(f"{key} in sync.")

                if self.archive_aged:
                    if issue_dict['status'] in other_source.closed_statuses:
                        last_edit = parser.isoparse(notion_issue['updated_on'])
                        if last_edit < threshold:
                            log.info(f"{key}: archiving aged issue.")
                            notion_source.archive_issue(key)

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

                resp = notion_source.create_issue(key, issue_dict)
                log.debug(f"{key}: {pformat(resp)}")
                if 'status' in resp:
                    log.error(f'failed to create in notion: {pformat(resp)}')
                else:
                    log.info(f"{key}: created in notion.")
