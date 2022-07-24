import os
import sys
from pprint import pprint
from github import Github

from notion_issues import IssueSource, unassigned_user, ISO_UTC_FMT

class GithubSource(IssueSource):

    use_path = False
    include_pull_requests = False

    closed_statuses = ['closed']

    def __init__(self, github_token, github_repo):
        self.github = Github(github_token)
        self.repo_path = github_repo

    def map_unassigned_user(self, user):
        if user == unassigned_user:
            return ""
        return user

    def get_issues(self):
        output = {}

        repo = self.github.get_repo(self.repo_path)

        for issue in repo.get_issues(state='all'):
            if issue.pull_request and not self.include_pull_requests:
                continue

            if self.use_path:
                key = f"{self.repo_path}#{issue.number}"
            else:
                key = f"{self.repo_path.rsplit('/', 1)[1]}#{issue.number}"

            if issue.assignee:
                assignee = issue.assignee.login
            else:
                assignee = unassigned_user

            due_on = ""
            if issue.milestone:
                due_on = issue.milestone.due_on

            labels = [l.name for l in issue.labels]

            output[key] = {
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

    def update_issue(self, key, issue_dict):
        issue_number = int(key.rsplit("#", 1)[1])
        repo = self.github.get_repo(self.repo_path)
        issue = repo.get_issue(issue_number)
        result = issue.edit(title=issue_dict['title'],
                            state=issue_dict['status'],
                            assignee=self.map_unassigned_user(
                                issue_dict['assignee']))

    def __str__(self):
        return f"Github Source: {self.repo_path}"

if __name__ == '__main__':
    gh = GithubSource(os.environ.get("GITHUB_TOKEN"), sys.argv[1])
    pprint(gh.get_issues())
