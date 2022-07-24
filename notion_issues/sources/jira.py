import jira

from notion_issues import IssueSource, unassigned_user

DEFAULT_JIRA_SERVER = "https://jiracloud.net"

class JiraSource(IssueSource):

    closed_statuses = ['closed', 'resolved']

    def __init__(self, jira_token, jira_project,
                 jira_server=DEFAULT_JIRA_SERVER):
        self.jira = JIRA(options={'server': args.server},
                         token_auth=args.jira_token)
        self.project = jira_project

    def get_issues(self):
        output = {}
        issues = jira.search_issues(f'project={self.project}')
        for issue in issues:
            if issue.fields.assignee:
                assignee = issue.fields.assignee.name
            else:
                assignee = unassigned_user

            output[issue.key] = {
                  "title": issue.fields.summary,
                  "status": issue.fields.status.name,
                  "assignee": assignee,
                  "reporter": issue.fields.creator.key,
                  "labels": [issue.fields.priority,
                             issue.fields.issuetype.name],
                  "due_on": self.normalize_date(
                                issue.fields.due_date, granularity='minutes'),
                  "opened_on": self.normalize_date(
                                issue.fields.created, granularity='minutes'),
                  "updated_on": self.normalize_date(issue.fields.updated),
                  "link": issue.permalink
            }

        return output

    def update_issue(self, key, issue_dict):
        issue = jira.issue(key)
        issue.update(fields={
                  "summary": issue_dict['title'],
                  "status": issue_dict['status'],
                  "assignee": { "name": issue_dict['assignee'] },
                  "due_on": issue_dict['due_on']
            })

    def __str__(self):
        return f"Jira Source: {self.project}"
