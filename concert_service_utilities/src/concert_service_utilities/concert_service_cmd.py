#!/usr/bin/env python
#
# License: BSD
#   https://raw.github.com/robotics-in-concert/rocon_concert/license/LICENSE
#
#################################################################################

from __future__ import division, print_function

import sys
import os
import traceback
import argparse
import rocon_python_utils
import rocon_std_msgs.msg as rocon_std_msgs

#################################################################################
# Global variables
#################################################################################

NAME = 'concert_service'

#################################################################################
# Local methods
#################################################################################

def _list(argv):
    args = argv[2:]

    cached_service_profile_information, unused_invalid_services = rocon_python_utils.ros.resource_index_from_package_exports(rocon_std_msgs.Strings.TAG_SERVICE)

    for cached_resource_name, (cached_filename, unused_catkin_package) in cached_service_profile_information.iteritems():
        print(str(cached_resource_name) + " : " + str(cached_filename))


def _info(argv):
    print("Info")
    pass


def _index(argv):
    print("Index") 
    pass

def _fullusage(argv):
    print("""\nconcert_service is a command-line tool for printing information about Concert Service

Commands:
\tconcert_service list\t\tdisplay a list of available rapps in ROS_PACKAGE_PATH
\tconcert_service info\t\tdisplay concert_service information
\tconcert_service index\t\tgenerate an index file of a concert_serivce tree
\tconcert_service help\t\tUsage

Type concert_service <command> -h for more detailed usage, e.g. 'concert_service info -h'
""")
    sys.exit(getattr(os, 'EX_USAGE', 1))




#################################################################################
# Main
#################################################################################

def _set_commands(): 
    cmd = {}
    cmd['list'] = _list
    cmd['info'] = _info
    cmd['index'] = _index
    cmd['help'] = _fullusage
    return cmd

def main():
    argv = sys.argv

    if len(argv) == 1:
        _fullusage(argv)

    available_commands = _set_commands()

    try:
        command = argv[1]

        if command in available_commands.keys():
            available_commands[command](argv)
        else:
            available_commands['help'](argv)
    except RuntimeError as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    except Exception as e:
        sys.stderr.write("Error: %s\n" % str(e))
        ex, val, tb = sys.exc_info()
        traceback.print_exception(ex, val, tb)
        sys.exit(1)
