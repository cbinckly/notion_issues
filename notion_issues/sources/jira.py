import jira
from jira.exceptions import JIRAError

from notion_issues import unassigned_user
from notion_issues.sources import IssueSource
from notion_issues.logger import Logger

JIRA_TIMEFMT = "%Y-%m-%d %H:%M"
log = Logger('notion_issues.sources.jira')

class JiraSource(IssueSource):

    closed_statuses = ['closed', 'resolved']

    def __init__(self, jira_token, jira_project, jira_server):
        self.jira = jira.JIRA(options={'server': jira_server},
                         token_auth=jira_token)
        self.project = jira_project

    def map_unassigned_user(self, user):
        if user == unassigned_user:
            return None
        return user

    def get_issues(self, since=None):
        if since
        output = {}
        query = f'project={self.project}'
        if since:
            since_str = since.strftime(JIRA_TIMEFMT)
            query = f'{query} and (updated > {since_str} or created > (since_str)')

        for issue in self.jira.search_issues(query):
            if issue.fields.assignee:
                assignee = issue.fields.assignee.name
            else:
                assignee = unassigned_user

            output[issue.key] = {
                  "title": issue.fields.summary,
                  "status": issue.fields.status.name,
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

    def update_issue(self, key, issue_dict):
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

        status = issue_dict['status']
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
