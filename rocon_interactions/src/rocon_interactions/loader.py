#
# License: BSD
#   https://raw.github.com/robotics-in-concert/rocon_concert/license/LICENSE
#
##############################################################################
# Imports
##############################################################################

import rospy
import concert_msgs.srv as concert_srvs

# local
import interactions

##############################################################################
# Loader
##############################################################################


class Loader(object):
    '''
      This class is responsible for loading the role manager with the roles
      and app specifications provided in the service definitions.
    '''
    __slots__ = [
            '_set_interactions_proxy',
        ]

    def __init__(self):
        '''
        Don't do any loading here, just set up infrastructure and overrides from
        the solution.
        '''
        self._set_interactions_proxy = rospy.ServiceProxy(service_name, concert_srvs.SetInteractions)
        try:
            self._set_interactions_proxy.wait_for_service(15.0)
        except rospy.exceptions.ROSException:
            # timeout exceeded
            raise rospy.exceptions.ROSException("timed out waiting for service [%s]" % self._set_interactions_proxy.resolved_name)
        except rospy.exceptions.ROSInterruptException as e:
            raise e

    def load(self, interactions_yaml_resource, namespace='/', load=True):
        '''
        Parse a set of configurations specified in a yaml file and send the command to
        load/unload these on the interactions manager. For convenience, it also allows
        the setting of a namespace for the whole group which will only get applied if
        an interaction has no setting in the yaml.

        @param interactions_yaml_resource : yaml resource name for role-app parameterisation
        @type yaml string

        @param namespace: namespace to push connections down into
        @type string (e.g. /interactions)

        @param load : either load or unload the interaction information.
        @type boolean

        @raise ResourceNotFoundException, MalformedInteractionsYaml
        '''
        request = concert_srvs.SetInteractionsRequest()
        request.load = load

        # This can raise ResourceNotFoundException, MalformedInteractionsYaml
        request.interactions = interactions.load_msgs_from_yaml_resource(interactions_yaml_resource)
        for i in request.interactions:
            if i.namespace == '':
                i.namespace = namespace

        # Should check the response here and return some sort of true/false result.
        unused_response = self._set_interactions_proxy(request)
