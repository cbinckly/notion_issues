import jira
from jira.exceptions import JIRAError

from notion_issues import unassigned_user
from notion_issues.sources import IssueSource
from notion_issues.logger import Logger

JIRA_TIMEFMT = "%Y-%m-%d %H:%M"
log = Logger('notion_issues.sources.jira')

class JiraSource(IssueSource):

    closed_statuses = ['Closed', 'Resolved']

    def __init__(self, jira_token, jira_project, jira_server):
        self.jira = jira.JIRA(options={'server': jira_server},
                         token_auth=jira_token)
        self.project = jira_project
        self.__status_map = {}

    @property
    def _status_map(self):
        if not self.__status_map:
            self.__status_map = { s.name: s.name.lower()
                                  for s in self.jira.statuses() }
        return self.__status_map

    def status_to_notion(self, status):
        return self._status_map.get(status, '')

    def status_to_source(self, status):
        for jira_status, notion_status in self._status_map.items():
            if status == notion_status:
                return jira_status
        return ""

    def id_to_key(self, _id):
        return _id

    def key_to_id(self, key):
        return key

    def map_unassigned_user(self, user):
        if user == unassigned_user:
            return None
        return user

    def _issue_to_issue_dict(self, issue):
        if issue.fields.assignee:
            assignee = issue.fields.assignee.name
        else:
            assignee = unassigned_user

        output = {
              "title": issue.fields.summary,
              "status": self.status_to_notion(issue.fields.status.name),
              "assignee": assignee,
              "reporter": issue.fields.creator.key,
              "labels": [issue.fields.priority.name,
                         issue.fields.issuetype.name],
              "due_on": self.normalize_date(
                            issue.fields.duedate, granularity='minutes'),
              "opened_on": self.normalize_date(
                            issue.fields.created, granularity='minutes'),
              "updated_on": self.normalize_date(issue.fields.updated),
              "link": issue.permalink()
        }

        return output

    def get_issue(self, _id):
        issue = self.jira.issue(_id)
        return self._issue_to_issue_dict(issue)

    def get_issues(self, since=None, assignee=None):
        output = {}
        query = f'project={self.project}'
        if since:
            since_str = since.strftime(JIRA_TIMEFMT)
            query = f'{query} and (updated > "{since_str}" or created > "{since_str}")'
        if assignee:
            query = f'{query} and assignee = {assignee}'

        for issue in self.jira.search_issues(query):
            key = self.id_to_key(issue.key)
            output[key] = self._issue_to_issue_dict(issue)
        return output

    def update_issue(self, key, issue_dict):
        """
        Note: jira doesn't care if user names are in the correct case.
        """
        issue = self.jira.issue(key)
        fields = {
                "summary": issue_dict['title'],
                "assignee": {
                  "name": self.map_unassigned_user(issue_dict['assignee'])
                },
            }
        if issue_dict['due_on']:
            fields["duedate"] = issue_dict['due_on']

        try:
            issue.update(fields=fields)
            log.info(f"{key}: update to {fields}")
        except JIRAError as e:
            log.error(f"failed to update: {e}")

        status = self.status_to_source(issue_dict['status'])
        for transition in self.jira.transitions(issue):
            name = transition['to']['name']
            log.debug(f'assessing transition to {name}=={status}?')
            if name == status:
                log.info(f'{key}: transitioning issue to {name}.')
                try:
                    self.jira.transition_issue(issue, transition['id'])
                except JIRAError as e:
                    log.error(f"failed to transition: {e}")

    def __str__(self):
        return f"Jira Source: {self.project}"
