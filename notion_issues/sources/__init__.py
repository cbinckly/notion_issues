from abc import ABC
from dateutil import parser

ISO_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
ISO_UTC_MIN_FMT = "%Y-%m-%dT%H:%M:00Z"

class IssueSource(ABC):

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Implement in child.")

    def key_to_id(self, key):
        """Convert an issue key to and id.

        :param key: notion issue key
        :type key: str
        :returns: issue id.
        :rtype: str, int
        """
        raise NotImplementedError('Implement in child.')

    def normalize_date(self, date, granularity='seconds'):
        if not date:
            return ""
        if isinstance(date, str):
            date = parser.isoparse(date)
        if granularity == 'seconds':
            return date.strftime(ISO_UTC_FMT)
        return date.strftime(ISO_UTC_MIN_FMT)

    def get_issue(self, _id):
        """
        :param _id: filter properties for the source.
        :type _id: int or str
        :returns: issues dict
        """
        raise NotImplementedError("Implement in child.")

    def get_issues(self, *kwargs):
        """
        :param kwargs: filter properties for the source.
        :type kwargs: key=value pairs.
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


