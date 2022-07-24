import os
import argparse
from pprint import pprint
from dateutil import parser
from datetime import datetime, timedelta, timezone

from notion_issues.sources._github import GithubSource
from notion_issues.sources.jira import JiraSource
from notion_issues.sources.notion import NotionSource
from notion_issues.logger import Logger

log = Logger('notion_issues')

defaults = {
        'jira_token': os.environ.get("JIRA_TOKEN"),
        'jira_server': 'https://jira.junipercloud.net/it',
        'jira_project': 'RFPIO',
        'github_token': os.environ.get("GITHUB_TOKEN"),
        'github_repo': 'Juniper-SE/cse-global-loans',
        'notion_token': os.environ.get("NOTION_TOKEN"),
        'notion_database': 'Issues',
        }

def parse_args():
    parser = argparse.ArgumentParser(__name__)
    parser.add_argument('-nt', '--notion-token', type=str,
            default=defaults['notion_token'],
            help=f"Notion Token. Default: {defaults['notion_token']}")
    parser.add_argument('-d', '--notion-database', type=str,
            default=defaults['notion_database'],
            help=f"Notion database ID. Default: {defaults['notion_database']}")
    parser.add_argument('-v', '--verbose', action='store_true',
            help=f"Turn on verbose logging")
    parser.add_argument('--create-closed', action='store_true',
            help=f"Create new entries for closed issues.")
    parser.add_argument('--create-assignee', metavar="ASSIGNEE", type=str,
            help=f"Only create new entries for issues assigned to assignee.")
    parser.add_argument('--archive-aged', action='store_true',
            help=f"Remove entries that have been closed for over a month.")


    subparsers = parser.add_subparsers(help='sub-command help')

    github_parser = subparsers.add_parser('github', help='Sync Github Issues')
    github_parser.add_argument('-gt', '--github-token',
            type=str, default=defaults['github_token'],
            help=f"Github Token. Default: {defaults['github_token']}")
    github_parser.add_argument('-gr', '--github-repo',
            type=str, default=defaults['github_repo'],
            help=f"Github Repo Name. Default: {defaults['github_repo']}")
    github_parser.add_argument('-gp', '--github-use-path', action='store_true',
            help=f"Use full repository path for issue key instead of name.")
    github_parser.set_defaults(func=github_sync)

    jira_parser = subparsers.add_parser('jira', help='Sync Jira Issues')
    jira_parser.add_argument('-jt', '--jira-token', type=str,
            default=defaults['jira_token'],
            help=f"Jira Token. Default: {defaults['jira_token']}")
    jira_parser.add_argument('-s', '--server', type=str,
            default=defaults['jira_server'],
            help=f"Jira server address. Default: {defaults['jira_server']}")
    jira_parser.add_argument('-p', '--project', type=str,
            default=defaults['jira_project'],
            help=f"Jira Project Key. Default: {defaults['jira_project']}")
    jira_parser.set_defaults(func=jira_sync)

    return parser.parse_args()

def github_sync(args, syncer):
    notion_source = NotionSource(args.notion_token, args.notion_database)
    github_source = GithubSource(args.github_token, args.github_repo)
    _filter = args.github_repo
    if not args.github_use_path:
        _filter = args.github_repo.rsplit('/', 1)[1]
    syncer.sync_sources(notion_source, github_source, _filter)

def jira_sync(args, syncer):
    notion_source = NotionSource(args.notion_token, args.notion_database)
    jira_source = JiraSource(args.jira_token, args.jira_project)
    syncer.sync_sources(notion_source, jira_source, args.jira_project)

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
        log.info(f"notion({len(notion_issues)}), other({len(source_issues)})")

        threshold = datetime.now(timezone.utc) - timedelta(seconds=60*60*24*31)

        for key, issue_dict in source_issues.items():
            log.debug("{key}: assessing.")
            if key in notion_issues:
                log.debug(f"{key}: exists in notion")
                notion_issue = notion_issues[key]
                if not self.issues_equal(notion_issue, issue_dict):
                    if issue_dict['updated_on'] > notion_issue['updated_on']:
                        log.debug(f"{key}: other source is newer")
                        notion_source.update_issue(key, issue_dict)
                        log.info(f"{key}: notion updated successfully.")
                    else:
                        log.debug(f"{key}: notion source is newer")
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
                log.info(f"{key}: created in notion.")

def main():
    args = parse_args()
    if args.verbose:
        log.verbose()
    log.debug(f"executing {args.func} with {args}")
    syncer = IssueSync(
            args.create_closed, args.create_assignee, args.archive_aged)
    args.func(args, syncer)

if __name__ == '__main__':
    main()