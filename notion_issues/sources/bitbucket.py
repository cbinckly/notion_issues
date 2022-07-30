import requests
from pprint import pprint
from atlassian.bitbucket import Cloud

from notion_issues import unassigned_user
from notion_issues.sources import IssueSource
from notion_issues.logger import Logger

log = Logger('notion_issues.sources.bitbucket')

class BitbucketSource(IssueSource):

    closed_statuses = ['closed', 'resolved']

    def __init__(self, bitbucket_user, bitbucket_app_pass,
                 bitbucket_repo, bitbucket_server):
        self.bitbucket = Cloud(username=bitbucket_user,
                               password=bitbucket_app_pass,
                               cloud=True)
        self.user = bitbucket_user
        self.password = bitbucket_app_pass
        self.repo_path = bitbucket_repo
        self.server = bitbucket_server
        try:
            self.workspace_slug, self.repo_name = self.repo_path.split('/')
        except:
            log.error(f'Error getting workspace and repo - {self.repo_path}')
            raise

        self.workspace = self.bitbucket.workspaces.get(self.workspace_slug)
        self.repo = self.workspace.repositories.get(self.repo_name)
        self.session = requests.Session()
        self.session.auth = (self.user, self.password)

    def map_unassigned_user(self, user):
        if user == unassigned_user:
            return ""
        return user

    def _issue_to_issue_dict(self, issue):
        if issue.data['assignee']:
            assignee = issue.data['assignee'].get('nickname')
        else:
            assignee = unassigned_user


        if issue.data['reporter']:
            reporter = issue.data['reporter'].get('nickname') or ''
        else:
            reporter = ""

        output = {
              "title": issue.data['title'],
              "status": issue.data['state'],
              "assignee": assignee,
              "reporter": reporter,
              "labels": [issue.data['priority'],
                         issue.data['type']],
              "due_on": "",
              "opened_on": self.normalize_date(
                            issue.data['created_on'],
                            granularity='minutes'),
              "updated_on": self.normalize_date(issue.data['updated_on']),
              "link": issue.data['links']['html']['href']
        }
        return output

    def get_issue(self, _id):
        issue = self.repo.issues.get(_id)
        return self._issue_to_issue_dict(issue)

    def get_issues(self, since=None):
        query = ""
        if since:
            query = f"updated_on > {since.strftime('%Y-%m-%dT%H:%M:%S')}"

        output = {}
        for issue in self.repo.issues.each(q=query):
            key = f'{self.repo_name}#{issue.data["id"]}'
            output[key] = self._issue_to_issue_dict(issue)
        return output

    def update_issue(self, key, issue_dict):
        number = key.split("#")[1]
        issue = self.repo.issues.get(int(number))
        fields = {
                "title": issue_dict['title'],
                "state": issue_dict['status']
            }
        if issue_dict['assignee']:
            self._change_issue_assignee(number, issue_dict['assignee'])
        pprint(fields)
        issue.update(**fields)

    def _get_workspace_members(self):
        resp = self.session.get(f"{self.server}/2.0/workspaces/"
                                f"{self.workspace_slug}/members")
        return { v['user'].get('nickname', 'noname'): v['user']['account_id']
                 for v in resp.json()['values'] }

    def _change_issue_assignee(self, issue_id, assignee):
        members = self._get_workspace_members()
        if assignee in members:
            payload = {
                "changes": {
                    { "assignee_account_id": { "new": members['assignee'] } }
                }
            }
            resp = self.session.post(f"{self.server}/2.0/repositories/"
                                     f"{self.workspace_slug}/{self.repo_name}/"
                                     f"issues/{issue_id}", json=payload)

    def __str__(self):
        return f"Bitbucket Source: {self.repo_path}"
