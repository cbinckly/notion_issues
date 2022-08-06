import os
import sys
import asyncio
import argparse
from pathlib import Path
from pprint import pprint, pformat
from dateutil import parser as date_parser
from datetime import datetime, timedelta, timezone

from notion_issues import IssueSync
from notion_issues.sources._github import GithubSource
from notion_issues.sources._jira import JiraSource
from notion_issues.sources.bitbucket import BitbucketSource
from notion_issues.sources.notion import NotionSource
from notion_issues.logger import Logger

log = Logger('notion_issues')
THIRTY_DAYS = timedelta(seconds=60*60*24*30)

defaults = {
        'since': datetime.now(timezone.utc) - THIRTY_DAYS,
        'jira_token': os.environ.get("JIRA_TOKEN"),
        'jira_server': os.environ.get("JIRA_SERVER"),
        'jira_project': os.environ.get("JIRA_PROJECT"),
        'github_token': os.environ.get("GITHUB_TOKEN"),
        'github_repo': os.environ.get("GITBUH_REPO"),
        'notion_token': os.environ.get("NOTION_TOKEN"),
        'notion_database': os.environ.get("NOTION_DATABASE"),
        'bitbucket_app_password': os.environ.get("BITBUCKET_APP_PASSWORD"),
        'bitbucket_user': os.environ.get("BITBUCKET_USER"),
        'bitbucket_repo': os.environ.get("BITBUCKET_REPO"),
        'bitbucket_server': os.environ.get("BITBUCKET_SERVER",
                                           "https://api.bitbucket.org")
        }

def load_since(path):
    with Path(path).open('r') as f:
        return parser.parse(f.read())

def parse_args():
    parser = argparse.ArgumentParser('notion_issues')
    parser.add_argument('-nt', '--notion-token', type=str,
            default=defaults['notion_token'],
            help=f"Notion Token. Default: {defaults['notion_token']}")
    parser.add_argument('-nd', '--notion-database', type=str,
            default=defaults['notion_database'],
            help=f"Notion database ID. Default: {defaults['notion_database']}")
    since = parser.add_mutually_exclusive_group(required=False)
    since.add_argument('-s', '--since', metavar='YYYYmmddTHHMMSS',
            default=defaults['since'], type=date_parser.parse,
            help=f"Sync issues since date time. Default: {defaults['since']}")
    since.add_argument('-sf', '--since-file', metavar='PATH',
            type=load_since, help=f"Sync issues since date time in file.")
    parser.add_argument('-v', '--verbose', action='store_true',
            help=f"Turn on verbose logging")
    parser.add_argument('--create-closed', action='store_true',
            help=f"Create new entries for closed issues.")
    parser.add_argument('--create-assignee', metavar="ASSIGNEE", type=str,
            help=f"Only create new entries for issues assigned to assignee.")
    parser.add_argument('--archive-aged', metavar="DAYS", type=int, default=7,
            help=(f"Remove entries that have been closed for DAYS. Default 7. "
                  f"Set to 0 to disable archiving"))


    subparsers = parser.add_subparsers(
            title="Issue Sources", required=True,
            help='issue sources help', dest="source")

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
    jira_parser.add_argument('-js', '--jira-server', type=str,
            default=defaults['jira_server'],
            help=f"Jira server address. Default: {defaults['jira_server']}")
    jira_parser.add_argument('-jp', '--jira-project', type=str,
            default=defaults['jira_project'],
            help=f"Jira Project Key. Default: {defaults['jira_project']}")
    jira_parser.set_defaults(func=jira_sync)

    bitbucket_parser = subparsers.add_parser(
            'bitbucket', help='Sync Bitbucket Issues')
    bitbucket_parser.add_argument('-ba', '--bitbucket-app-password', type=str,
            default=defaults['bitbucket_app_password'],
            help=f"Bitbucket Token. Default: {defaults['bitbucket_app_password']}")
    bitbucket_parser.add_argument('-bu', '--bitbucket-user', type=str,
            default=defaults['bitbucket_user'],
            help=f"Bitbucket User. Default: {defaults['bitbucket_user']}")
    bitbucket_parser.add_argument('-bs', '--bitbucket-server', type=str,
            default=defaults['bitbucket_server'],
            help=f"Bitbucket Server. Default: {defaults['bitbucket_server']}")
    bitbucket_parser.add_argument('-br', '--bitbucket-repo', type=str,
            default=defaults['bitbucket_repo'],
            help=f"Bitbucket Repo Path. Default: {defaults['bitbucket_repo']}")
    bitbucket_parser.add_argument('-bp', '--bitbucket-use-path',
            action='store_true',
            help=f"Use full repository path for issue key instead of name.")
    bitbucket_parser.set_defaults(func=bitbucket_sync)

    notion_parser = subparsers.add_parser(
            'notion', help='Maintain issues in Notion.')
    notion_delete = notion_parser.add_mutually_exclusive_group(required=True)
    notion_delete.add_argument('--delete-key', metavar="KEY", type=str,
            help=f"Delete an issue with a specific key from Notion.")
    notion_delete.add_argument('--delete-matching-keys', metavar="PATTERN",
            type=str,
            help=f"Delete issues with keys that begin with PATTERN.")
    notion_parser.set_defaults(func=notion_maintain)

    return parser.parse_args()

async def notion_maintain(args, syncer):
    notion_source = NotionSource(args.notion_token, args.notion_database)
    if args.delete_key:
        log.info(f"{args.delete_key}: archive issue requested.")
        issues = await notion_source.get_issues()
        if args.delete_key in issues:
            log.info(f"{args.delete_key}: archive issue.")
            resp = await notion_source.archive_issue(args.delete_key)
            log.debug(f"{args.delete_key}: response {pformat(resp)}")
        else:
            log.error(f"{args.delete_key} not found in notion.")
    elif args.delete_matching_keys:
        log.info(f"{args.delete_matching_keys}: archive matching requested.")
        issues = await notion_source.get_issues(
                issue_key_filter=args.delete_matching_keys)
        for key in issues.keys():
            if key.startswith(args.delete_matching_keys):
                log.info(f"{key}: archive issue.")
                await notion_source.archive_issue(key)

async def github_sync(args, syncer):
    notion_source = NotionSource(args.notion_token, args.notion_database)
    github_source = GithubSource(args.github_token, args.github_repo)
    _filter = args.github_repo
    if not args.github_use_path:
        _filter = args.github_repo.rsplit('/', 1)[1]
    await syncer.sync_sources(notion_source, github_source, _filter)

async def jira_sync(args, syncer):
    notion_source = NotionSource(args.notion_token, args.notion_database)
    jira_source = JiraSource(args.jira_token, args.jira_project,
                             args.jira_server)
    await syncer.sync_sources(notion_source, jira_source, args.jira_project)

async def bitbucket_sync(args, syncer):
    notion_source = NotionSource(args.notion_token, args.notion_database)
    bitbucket_source = BitbucketSource(
            args.bitbucket_user, args.bitbucket_app_password,
            args.bitbucket_repo, args.bitbucket_server)
    _filter = args.bitbucket_repo
    if not args.bitbucket_use_path:
        _filter = args.bitbucket_repo.rsplit('/', 1)[1]
    await syncer.sync_sources(notion_source, bitbucket_source, _filter)

def validate(args):
    errors = []
    if not args.source:
        errors.append("Issue source must be specified.")
    if not args.notion_token:
        errors.append("Notion token is required.")
    if not args.notion_database:
        errors.append("Notion database is required.")
    if args.source == 'github':
        if not args.github_token:
            errors.append("Github token is required.")
        if not args.github_repo:
            errors.append("Github repo is required.")
    if args.source == 'jira':
        if not args.jira_token:
            errors.append("Jira token is required.")
        if not args.jira_project:
            errors.append("Jira project is required.")
    return errors

async def async_main():
    args = parse_args()
    if args.verbose:
        log.verbose()
    log.debug(f"executing {args.func} with {args}")
    errors = validate(args)
    if errors:
        for e in errors:
            log.error(f"{e}")
        log.error("args not valid, stopping.")
        sys.exit(1)
    syncer = IssueSync(
            args.create_closed, args.create_assignee,
            args.since_file or args.since,
            args.archive_aged)
    await args.func(args, syncer)

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_main())
    except asyncio.exceptions.CancelledError:
        log.error('Cancelled.')
    except Exception as err:
        msg = (f"Exception {err} raised.")
        log.error(msg, exc_info=True)

if __name__ == '__main__':
    main()
