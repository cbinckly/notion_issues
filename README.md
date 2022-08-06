## Notion Issues

A simple tool to pull issue information from
Jira, Bitbucket, or Github into a Notion database. Although simple, it 
provides a powerful way to see all your issues in one place.

### What does it do?

- Pull the following fields for each issue and stick them in the notion 
  database of your choosing:
    - Issue Key
    - Title
    - Labels (includes type/priority from BitBucket/Jira)
    - Status
    - Reporter
    - Assignee
    - Due Date
    - Created On
    - Link
- Keep the issues that are already in the database up to date.
- Push changes to some fields back to the source:
    - All Sources: Assignee, State, Title
    - Bitbucket and Jira: Due On
- Archive old, closed issues to remove them from your view.
- Use filters to ignore closed issues or issues that aren't assigned to you.

### How do I use it?

You provide the service information, tokens, and database
name, the tool does the hard work.

The general help applies to all issue sources:
```
$ notion_issues --help
usage: notion_issues [-h] [-nt NOTION_TOKEN] [-d NOTION_DATABASE] [-v] [--create-closed] [--create-assignee ASSIGNEE] [--archive-aged] {github,jira} ...

positional arguments:
  {github,jira}         sub-command help
    github              Sync Github Issues
    jira                Sync Jira Issues

options:
  -h, --help            show this help message and exit
  -nt NOTION_TOKEN, --notion-token NOTION_TOKEN
                        Notion Token. Default: None
  -d NOTION_DATABASE, --notion-database NOTION_DATABASE
                        Notion database ID. Default: Issues
  -v, --verbose         Turn on verbose logging
  --create-closed       Create new entries for closed issues.
  --create-assignee ASSIGNEE
                        Only create new entries for issues assigned to assignee.
  --archive-aged        Remove entries that have been closed for over a month.
```

#### Setup Tokens

> :warning: **Keep your tokens safe!** Tokens provided on the command line may
> be visible to others using your console's history or other means.  Best
> to use environment variables for your tokens!

Tokens are used to authenticate you with services. You can provide tokens as 
command line options, but this is not recommended.  The tools can also get
your token from the environment.  They look for the following variables:

- `NOTION_TOKEN`
- `GITHUB_TOKEN`
- `JIRA_TOKEN`
- `BITBUCKET_TOKEN`

Setup your environment before sync'ing your issues for the first time.

#### Choosing What to Do

The tools have a few different flags that let you curate what is copied to keep
your tables clean and focused.

By default, the tools won't create new issues on sync that are in a closed 
state.  If you would rather that closed issues were included, pass the 
`--create-closed` argument.

You can also limit the sync to only issues that are assigned to a particular 
user using the `--create-assignee ASSIGNEE` argument.  This will only create
issues that are assigned to the specified assignee.  Once the issue has been
sync'd once, it will continue to be updated, even if it is assigned to someone
else, unless you manually archive the entry in Notion.

Finally, to keep your tables lean, you can automatically archive entries from
the Notion database when they have been closed for over a month. Pass the 
`--remove-aged` argument to automatically age old closed issues out of your 
list.

#### Github

We need your tokens, the Github repository name, and Notion Database name.

```bash
notion_issues --notion-token NOTION_TOKEN --notion-database NAME \
              github --github-token GITHUB_TOKEN --github-repo USER/REPONAME
```

The GitHub source supports two conventions for the Issue Key.

1. `<repo_name>#<issue_number>` - the repo name and issue number. (Default)
2. `<repo_path>#<issue_number>` - the repo path and issue number.

If you're working with the defaults, issues from the repository 
`my_user/code_repo` would use only the name (`code_repo`) in the issue
number, e.g. `code_repo#5`.  If you pass the `--github-use-path` argument,
the full path will be used to build the number, e.g. `my_user/code_repo#5`.

> :warning: **Be consistent!** Changing the issue number format will result
> in the duplication of any issues that have already been craeted under the
> other key convention.

```
$ notion_issues github --help
usage: notion_issues github [-h] [-gt GITHUB_TOKEN] [-gr GITHUB_REPO] [-gp]

options:
  -h, --help            show this help message and exit
  -gt GITHUB_TOKEN, --github-token GITHUB_TOKEN
                        Github Token. Default: None
  -gr GITHUB_REPO, --github-repo GITHUB_REPO
                        Github Repo Name. Default: Juniper-SE/cse-global-loans
  -gp, --github-use-path
                        Use full repository path for issue key instead of name.
```

#### Jira

We need your tokens, the Jira Project Key, and Notion Database name.

```bash
notion_issues jira --jira-token JIRA_TOKEN --jira-project USER/REPONAME \
                   --notion-token NOTION_TOKEN --notion-database DATABASE_NAME
```

#### Bitbucket

We need your username and an 
[App Password](https://bitbucket.org/account/settings/app-passwords/), 
the repository path, and Notion Database name.

```bash
notion_issues --notion-token NOTION_TOKEN --notion-database DATABASE_NAME
              bitbucket --bitbucket-token JIRA_TOKEN --bitbucket-project USER/REPONAME \
                   
```
