#!/usr/bin/env python2
import argparse
import datetime
import re
import requests
import subprocess

from utils.conf import docker


def clean_commit(commit_msg):
    replacements = ['1LP', 'RFR', 'WIP', 'WIPTEST', 'NOTEST']
    for replacement in replacements:
        commit_msg = commit_msg.replace('[{}]'.format(replacement), '')
    return commit_msg.strip(" ")


def main():
    parser = argparse.ArgumentParser(epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('new_tag',
        help='The new tag number')
    parser.add_argument('--old-tag', default=None,
        help='Build the release from an older tag')
    parser.add_argument('--full', action="store_true", default=False,
        help='Whether to generate full PR details')

    args = parser.parse_args()

    full = args.full

    new_ver = args.new_tag

    if not args.old_tag:
        proc = subprocess.Popen(['git', 'describe', '--tags', '--abbrev=0'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        old_tag = proc.stdout.read().strip("\n")
    else:
        old_tag = args.old_tag
    proc = subprocess.Popen(['git', 'log', '{}..master'.format(old_tag), '--oneline'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    commits = proc.stdout.read()

    valid_labels = [
        u'fix-locator-or-text', u'infra-related', u'fix-test', u'doc',
        u'other', u'enhancement', u'fix-framework', u'new-test-or-feature'
    ]

    print('integration_tests {} Released'.format(new_ver))
    print('')
    print('Includes: {} -> {}'.format(old_tag, new_ver))

    max_len = len(reduce((lambda x, y: x if len(x) > len(y) else y), valid_labels))

    now = datetime.date.today()
    start_of_week = now - datetime.timedelta(days=15)
    string_start = start_of_week.strftime('%Y-%m-%d')

    headers = {'Authorization': 'token {}'.format(docker['gh_token'])}
    r = requests.get(
        'https://api.github.com/search/issues?per_page=200&q=type:pr+repo:{}/'
        '{}+merged:>{}'.format(docker['gh_owner'], docker['gh_repo'], string_start),
        headers=headers)

    prs = {}
    for pr in r.json()['items']:
        prs[pr['number']] = pr
        for label in pr['labels']:
            if label['name'] in valid_labels:
                pr['label'] = label['name']

    for commit in commits.split("\n"):
        pr = re.match('.*[#](\d+).*', commit)
        if pr:
            pr_number = int(pr.groups()[0].replace("#", ''))
            if pr_number in prs:
                old_lab = prs[pr_number]['label']
                label = old_lab + " " * (max_len - len(old_lab))
                msg = "{} | {} | {}".format(
                    pr_number, label, clean_commit(prs[pr_number]['title']))
                if full:
                    print "=" * len(msg)
                print msg
                if full:
                    print "-" * len(msg)
                    string = prs[pr_number]['body']
                    if string is None:
                        string = ""
                    pytest_match = re.findall("({{.*}}\s*)", string, flags=re.S | re.M)
                    if pytest_match:
                        string = string.replace(pytest_match[0], '')
                    print string
                    print "=" * len(msg)
                    print ("")


if __name__ == "__main__":
    main()
