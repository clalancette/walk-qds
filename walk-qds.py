import argparse
import collections
import re
import os
import sys

import lxml.etree


class Package:
    __slots__ = ('name', 'qd_path', 'lxml_tree', 'depth', 'children')

    def __init__(self, name, qd_path, lxml_tree):
        self.name = name
        self.qd_path = qd_path
        self.lxml_tree = lxml_tree
        self.depth = 0
        self.children = []

    def __eq__(self, other):
        return self.name == other.name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recurse', help='Whether to recursively find QDs for all dependencies', action='store_true', default=False)
    parser.add_argument('source_path', help='The top-level of the source tree in which to find package and dependencies', action='store')
    parser.add_argument('package', help='The top-level package for which to find Quality level of dependencies', action='store')
    args = parser.parse_args()

    source_path = args.source_path
    package_name_to_examine = args.package

    package_name_to_package = {}
    for (dirpath, dirnames, filenames) in os.walk(source_path):
        if 'package.xml' in filenames:
            tree = lxml.etree.parse(os.path.join(dirpath, 'package.xml'))
            for child in tree.getroot().getchildren():
                if child.tag == 'name':
                    package_name_to_package[child.text] = Package(child.text, os.path.join(dirpath, 'QUALITY_DECLARATION.md'), tree)
                    break

    if not package_name_to_examine in package_name_to_package:
        print("Could not find package to examine '%s'" % (package_name_to_examine))
        return 2

    packages_to_examine = collections.deque([package_name_to_examine])
    depnames_found = [package_name_to_examine]
    deps_not_found = set()
    while packages_to_examine:
        package = package_name_to_package[packages_to_examine.popleft()]
        deps = []
        for child in package.lxml_tree.getroot().getchildren():
            if child.tag not in ['depend', 'build_depend']:
                continue

            depname = child.text
            if depname in depnames_found:
                continue

            depnames_found.append(depname)

            if depname in package_name_to_package:
                package_name_to_package[depname].depth = package_name_to_package[package.name].depth + 1
                package_name_to_package[package.name].children.append(package_name_to_package[depname])
                if args.recurse:
                    packages_to_examine.append(depname)
            else:
                deps_not_found.add(depname)

    if deps_not_found:
        print("WARNING: Could not find packages '%s', not recursing" % (', '.join(deps_not_found)))

    quality_level_re = re.compile('.*claims to be in the \*\*Quality Level ([1-5])\*\*')

    # Now start walking in a depth-first search, starting from the top element,
    # figuring out and printing the quality levels as we go.
    deps_to_print = collections.deque([package_name_to_package[package_name_to_examine]])
    strings_to_print = []
    while deps_to_print:
        package = deps_to_print.popleft()
        if not os.path.exists(package.qd_path):
            print("WARNING: Could not find quality declaration for package '%s', skipping" % (package.name))
            continue
        with open(package.qd_path, 'r') as infp:
            for line in infp:
                match = re.match(quality_level_re, line)
                if match is None:
                    continue
                groups = match.groups()
                if len(groups) != 1:
                    continue
                strings_to_print.append('%s%s: %d' % ('  ' * package.depth, package.name, int(groups[0])))
                break
            else:
                print("WARNING: Could not find quality level for package '%s', skipping" % (package.name))

        for child in package.children:
            deps_to_print.appendleft(child)

    for s in strings_to_print:
        print(s)

    return 0

if __name__ == '__main__':
    sys.exit(main())
