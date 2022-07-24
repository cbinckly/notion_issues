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



