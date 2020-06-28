import argparse
import collections
import re
import os
import sys

import lxml.etree

def check_package_xml_for_name(path, name):
    package_xml = os.path.join(path, 'package.xml')
    # Open up the package.xml and ensure that this is the correctly named
    # package, as the path is not unique enough
    tree = lxml.etree.parse(package_xml)
    correct_package_name = True
    for child in tree.getroot().getchildren():
        if child.tag == 'name':
            if child.text != name:
                correct_package_name = False
        break

    return correct_package_name


class Repository:
    def __init__(self, name, qd_path, package_xml_path, depth):
        self.name = name
        self.qd_path = qd_path
        self.package_xml_path = package_xml_path
        self.depth = depth

    def __eq__(self, other):
        return self.name == other

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recurse', help='Whether to recursively find QDs for all dependencies', action='store_true', default=False)
    parser.add_argument('source_path', help='The top-level of the source tree in which to find package and dependencies', action='store')
    parser.add_argument('package', help='The top-level package for which to find Quality level of dependencies', action='store')
    args = parser.parse_args()

    source_path = args.source_path
    package_to_examine = args.package

    # First we walk the source repository, finding all of the packages and
    # storing their relative paths.  This saves us from having to do multiple
    # walks of the filesystem later.
    package_paths = []
    for (dirpath, dirnames, filenames) in os.walk(source_path):
        if 'package.xml' in filenames:
            package_paths.append(dirpath)

    dep_to_qd = []
    for path in package_paths:
        if os.path.basename(path) == package_to_examine:
            if check_package_xml_for_name(path, package_to_examine):
                dep_to_qd.append(Repository(package_to_examine, os.path.join(path, 'QUALITY_DECLARATION.md'), os.path.join(path, 'package.xml'), 0))
                break
    else:
        print("Could not find package to examine '%s'" % (package_to_examine))
        return 2

    repos_to_examine = collections.deque([dep_to_qd[0]])
    all_repos = collections.deque([dep_to_qd[0]])
    deps_not_found = set()
    while repos_to_examine:
        repo_to_examine = repos_to_examine.popleft()
        tree = lxml.etree.parse(repo_to_examine.package_xml_path)
        deps = []
        for child in tree.getroot().getchildren():
            if child.tag in ['depend', 'build_depend']:
                deps.append(child.text)

        deps.sort()
        for dep in deps:
            if dep in dep_to_qd:
                continue
            for path in package_paths:
                depname = os.path.basename(path)
                if depname == dep:
                    if not check_package_xml_for_name(path, depname):
                        continue

                    child_repo = Repository(depname, os.path.join(path, 'QUALITY_DECLARATION.md'), os.path.join(path, 'package.xml'), repo_to_examine.depth + 1)
                    dep_to_qd.append(child_repo)
                    if args.recurse:
                        repos_to_examine.appendleft(child_repo)
                        all_repos.appendleft(child_repo)
                    break
            else:
                deps_not_found.add(dep)

    print(all_repos)
    if deps_not_found:
        print("WARNING: Could not find packages '%s', not recursing" % (', '.join(deps_not_found)))

    quality_level_re = re.compile('.*claims to be in the \*\*Quality Level ([1-5])\*\*')
    dep_to_quality_level = collections.OrderedDict()
    for qd in dep_to_qd:
        if not os.path.exists(qd.qd_path):
            print("WARNING: Could not find quality declaration for package '%s', skipping" % (qd.name))
            continue
        with open(qd.qd_path, 'r') as infp:
            for line in infp:
                match = re.match(quality_level_re, line)
                if match is None:
                    continue
                groups = match.groups()
                if len(groups) != 1:
                    continue
                dep_to_quality_level[qd.name] = (int(groups[0]), qd.depth)

    for dep,quality in dep_to_quality_level.items():
        print('%s%s: %d' % ('  ' * quality[1], dep, quality[0]))

    return 0

if __name__ == '__main__':
    sys.exit(main())
