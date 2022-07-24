from setuptools import setup, find_packages

setup(
    name='notion_issues',
    version='0.1',
    author='cbinckly',
    url='https://poplars.dev/',
    author_email='cbinckly@poplars.dev',
    packages=find_packages(),
    description='Simple issue sync for Notion.',
    install_requires=[
        'requests',
        'pygithub',
        'jira',
        'python-dateutil',
        'pyyaml'
    ],
    entry_points={
        'console_scripts': [
            'notion_issues = notion_issues.__main__:main',
        ],
    },
    include_package_data=True,
)
