import os
import sys
from pprint import pprint
from github import Github

from notion_issues import unassigned_user
from notion_issues.sources import IssueSource, ISO_UTC_FMT

class GithubSource(IssueSource):

    use_path = False
    include_pull_requests = False

    closed_statuses = ['closed']

    def __init__(self, github_token, github_repo):
        self.github = Github(github_token)
        self.repo_path = github_repo
        self.repo = self.github.get_repo(self.repo_path)

    def key_to_id(self, key):
        return int(key.split('#')[-1])

    def map_unassigned_user(self, user):
        if user == unassigned_user:
            return ""
        return user

    def _issue_to_issue_dict(self, issue):

        if issue.assignee:
            assignee = issue.assignee.login
        else:
            assignee = unassigned_user

        due_on = ""
        if issue.milestone:
            due_on = issue.milestone.due_on

        labels = [l.name for l in issue.labels]

        output = {
              "title": issue.title,
              "status": issue.state,
              "assignee": assignee,
              "reporter": issue.user.login,
              "labels": labels,
              "due_on": self.normalize_date(due_on, granularity='minutes'),
              "opened_on": self.normalize_date(issue.created_at, granularity='minutes'),
              "updated_on": self.normalize_date(issue.updated_at),
              "link": issue.html_url
        }

        return output

    def get_issue(self, _id):
        issue = self.repo.get_issue(_id)
        return self._issue_to_issue_dict(issue)

    def get_issues(self, since=None, assignee=None):
        output = {}

        get_issues_args = { 'state': 'all' }
        if since:
            get_issues_args['since'] = since
        if assignee:
            get_issues_args['assignee'] = assignee

        for issue in self.repo.get_issues(**get_issues_args):
            if issue.pull_request and not self.include_pull_requests:
                continue

            if self.use_path:
                key = f"{self.repo_path}#{issue.number}"
            else:
                key = f"{self.repo_path.rsplit('/', 1)[1]}#{issue.number}"

            output[key] = self._issue_to_issue_dict(issue)

        return output

    def update_issue(self, key, issue_dict):
        issue_number = int(key.rsplit("#", 1)[1])
        issue = self.repo.get_issue(issue_number)
        result = issue.edit(title=issue_dict['title'],
                            state=issue_dict['status'],
                            assignee=self.map_unassigned_user(
                                issue_dict['assignee']))

    def __str__(self):
        return f"Github Source: {self.repo_path}"

if __name__ == '__main__':
    gh = GithubSource(os.environ.get("GITHUB_TOKEN"), sys.argv[1])
    pprint(gh.get_issues())
