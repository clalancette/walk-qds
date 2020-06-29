# Copyright 2020 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import collections
import os
import re
import sys

import lxml.etree


class Package:
    """Class to represent one package in the hierarchy of packages."""

    __slots__ = ('name', 'qd_path', 'lxml_tree', 'depth', 'children')

    def __init__(self, name, qd_path, lxml_tree):
        self.name = name
        self.qd_path = qd_path
        self.lxml_tree = lxml_tree
        self.depth = 0
        self.children = []


def main():
    parser = argparse.ArgumentParser(description='Utility to find and print quality levels of a ROS package and dependencies')
    parser.add_argument(
        '--recurse',
        help='Whether to recursively find quality levels for all dependencies',
        action='store_true',
        default=False)
    parser.add_argument(
        '--exclude',
        help='Package to specifically exclude from quality level checking (may be passed more than once)',
        action='append',
        default=[])
    parser.add_argument(
        'source_path',
        help='The top-level of the source tree in which to find package and dependencies',
        action='store')
    parser.add_argument(
        'package',
        help='The top-level package for which to find quality level of dependencies',
        action='store')
    args = parser.parse_args()

    source_path = args.source_path
    package_name_to_examine = args.package

    if package_name_to_examine in args.exclude:
        print("Package name '%s' must not be in the exclude list" % (package_name_to_examine))
        return 1

    # Walk the entire source_path passed in by the user, looking for all of the
    # package.xml files.  For each of them we parse the package.xml, and go
    # looking for the name of the package.  We then save that off, along with
    # the parser and the path, so we can later look up the package.  It is
    # slightly unfortunate that we end up parsing *all* the package.xml files
    # here, as we will only use a small fraction of them.  But this is the only
    # foolproof method to get the proper package names.

    package_name_to_package = {}
    for (dirpath, dirnames, filenames) in os.walk(source_path):
        if 'package.xml' not in filenames:
            continue

        tree = lxml.etree.parse(os.path.join(dirpath, 'package.xml'))
        for child in tree.getroot().getchildren():
            if child.tag != 'name':
                continue

            package_name_to_package[child.text] = Package(
                child.text,
                os.path.join(dirpath, 'QUALITY_DECLARATION.md'),
                tree)
            break

    if package_name_to_examine not in package_name_to_package:
        print("Could not find package to examine '%s'" % (package_name_to_examine))
        return 2

    # Starting with the package given by the user on the command-line, walk the
    # package dependencies in a breadth-first manner.  We want breadth-first so
    # that if a dependency shows up on more than one "level", we'll only show
    # it at the highest level it is a dependency at.

    packages_to_examine = collections.deque([package_name_to_examine])
    depnames_found = [package_name_to_examine]
    deps_not_found = set()
    while packages_to_examine:
        package = package_name_to_package[packages_to_examine.popleft()]
        for child in package.lxml_tree.getroot().getchildren():
            if child.tag not in ['depend', 'build_depend']:
                continue

            depname = child.text
            if depname in depnames_found:
                continue

            if depname in args.exclude:
                continue

            depnames_found.append(depname)

            if depname in package_name_to_package:
                package_name_to_package[depname].depth = package.depth + 1
                package.children.append(package_name_to_package[depname])
                if args.recurse:
                    packages_to_examine.append(depname)
            else:
                deps_not_found.add(depname)

    if deps_not_found:
        print("WARNING: Could not find dependencies '%s', skipping" % (', '.join(deps_not_found)))

    quality_level_re = re.compile(r'.*claims to be in the \*\*Quality Level ([1-5])\*\*')

    # Now start walking in a depth-first search, starting from the top element,
    # figuring out the quality levels as we go.  Note that we don't do the
    # printing here, just so that we collect all of the WARNINGS before we
    # print out the entire tree.
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

        deps_to_print.extendleft(package.children)

    [print(s) for s in strings_to_print]

    return 0


if __name__ == '__main__':
    sys.exit(main())
