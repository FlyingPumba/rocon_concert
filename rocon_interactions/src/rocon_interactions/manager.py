#
# License: BSD
#   https://raw.github.com/robotics-in-concert/rocon_concert/license/LICENSE
#
##############################################################################
# Imports
##############################################################################

import uuid
import rospy
import rosgraph
import concert_msgs.msg as concert_msgs
import concert_msgs.srv as concert_srvs
import unique_id

# Local imports
from .remocon_monitor import RemoconMonitor
from .interactions_table import InteractionsTable
import interactions
from .exceptions import MalformedInteractionsYaml, YamlResourceNotFoundException

##############################################################################
# Interactions
##############################################################################


class InteractionsManager(object):
    '''
      Manages connectivity information provided by services and provides this
      for human interactive (aka remocon) connections.
    '''
    __slots__ = [
            'interactions_table',  # Dictionary of string : concert_msgs.RemoconApp[]
            'publishers',
            'parameters',
            'services',
            'spin',
            'platform_info',
            '_watch_loop_period',
            '_remocon_monitors'  # list of currently connected remocons.
        ]

    ##########################################################################
    # Initialisation
    ##########################################################################

    def __init__(self):
        self.interactions_table = InteractionsTable()
        self.publishers = self._setup_publishers()
        self.services = self._setup_services()
        self.parameters = self._setup_parameters()
        self._watch_loop_period = 1.0
        self._remocon_monitors = {}  # topic_name : RemoconMonitor

        # Load pre-configured interactions
        for resource_name in self.parameters['interactions']:
            try:
                msg_interactions = interactions.load_msgs_from_yaml_resource(resource_name)
                (new_interactions, invalid_interactions) = self.interactions_table.load(msg_interactions)
                for i in new_interactions:
                    rospy.loginfo("Interactions : loading %s [%s-%s-%s]" % (i.display_name, i.name, i.role, i.namespace))
                for i in invalid_interactions:
                    rospy.logwarn("Interactions : failed to load %s [%s-%s-%s]" (i.display_name, i.name, i.role, i.namespace))
            except YamlResourceNotFoundException as e:
                rospy.logerr("Interactions : failed to load resource %s [%s]" % (resource_name, str(e)))
            except MalformedInteractionsYaml as e:
                rospy.logerr("Interactions : pre-configured interactions yaml malformed [%s][%s]" % (resource_name, str(e)))

    def spin(self):
        '''
          Parse the set of /remocons/<name>_<uuid> connections.
        '''
        while not rospy.is_shutdown():
            master = rosgraph.Master(rospy.get_name())
            diff = lambda l1, l2: [x for x in l1 if x not in l2]
            try:
                # This master call returns a filtered list of [topic_name, topic_type] elemnts (list of lists)
                remocon_topics = [x[0] for x in master.getPublishedTopics(concert_msgs.Strings.REMOCONS_NAMESPACE)]
                new_remocon_topics = diff(remocon_topics, self._remocon_monitors.keys())
                lost_remocon_topics = diff(self._remocon_monitors.keys(), remocon_topics)
                for remocon_topic in new_remocon_topics:
                    self._remocon_monitors[remocon_topic] = RemoconMonitor(remocon_topic, self._ros_publish_interactive_clients)
                    self._ros_publish_interactive_clients()
                    rospy.loginfo("Interactions : new remocon connected [%s]" % remocon_topic[len(concert_msgs.Strings.REMOCONS_NAMESPACE) + 1:])  # strips the /remocons/ part
                for remocon_topic in lost_remocon_topics:
                    self._remocon_monitors[remocon_topic].unregister()
                    del self._remocon_monitors[remocon_topic]  # careful, this mutates the dictionary http://stackoverflow.com/questions/5844672/delete-an-element-from-a-dictionary
                    self._ros_publish_interactive_clients()
                    rospy.loginfo("Interactions : remocon left [%s]" % remocon_topic[len(concert_msgs.Strings.REMOCONS_NAMESPACE) + 1:])  # strips the /remocons/ part
            except rosgraph.masterapi.Error:
                rospy.logerr("Interactions : error trying to retrieve information from the local master.")
            except rosgraph.masterapi.Failure:
                rospy.logerr("Interactions : failure trying to retrieve information from the local master.")
            rospy.rostime.wallsleep(self._watch_loop_period)

    def _setup_publishers(self):
        '''
          These are all public topics. Typically that will drop them into the /concert
          namespace.
        '''
        publishers = {}
        publishers['roles'] = rospy.Publisher('~roles', concert_msgs.Roles, latch=True)
        publishers['interactive_clients'] = rospy.Publisher('~interactive_clients', concert_msgs.InteractiveClients, latch=True)
        return publishers

    def _setup_services(self):
        '''
          These are all public services. Typically that will drop them into the /concert
          namespace.
        '''
        services = {}
        services['get_interactions'] = rospy.Service('~get_interactions',
                                                       concert_srvs.GetInteractions,
                                                       self._ros_service_get_interactions)
        services['get_interaction'] = rospy.Service('~get_interaction',
                                                       concert_srvs.GetInteraction,
                                                       self._ros_service_get_interaction)
        services['set_interactions'] = rospy.Service('~set_interactions',
                                                       concert_srvs.SetInteractions,
                                                       self._ros_service_set_interactions)
        services['request_interaction'] = rospy.Service('~request_interaction',
                                                       concert_srvs.RequestInteraction,
                                                       self._ros_service_request_interaction)
        return services

    def _setup_parameters(self):
        param = {}
        param['rosbridge_address'] = rospy.get_param('~rosbridge_address', "")
        param['rosbridge_port'] = rospy.get_param('~rosbridge_port', 9090)
        param['interactions'] = rospy.get_param('~interactions', [])
        return param

    ##########################################################################
    # Ros Api Functions
    ##########################################################################

    def _ros_publish_interactive_clients(self):
        interactive_clients = concert_msgs.InteractiveClients()
        for remocon in self._remocon_monitors.values():
            if remocon.status is not None:  # i.e. we are monitoring it.
                interactive_client = concert_msgs.InteractiveClient()
                interactive_client.name = remocon.name
                interactive_client.id = unique_id.toMsg(uuid.UUID(remocon.status.uuid))
                interactive_client.platform_info = remocon.status.platform_info
                if remocon.status.running_app:
                    interactive_client.app_name = remocon.status.app_name
                    interactive_clients.running_clients.append(interactive_client)
                else:
                    interactive_clients.idle_clients.append(interactive_client)
        self.publishers['interactive_clients'].publish(interactive_clients)

    def _ros_service_get_interaction(self, request):
        '''
          Handle incoming requests for a single app.
        '''
        response = concert_srvs.GetInteractionResponse()
        response.interaction = self.interactions_table.find(request.hash)
        response.result = False if response.interaction is None else True
        return response

    def _ros_service_get_interactions(self, request):
        '''
          Handle incoming requests to provide a role-applist dictionary
          filtered for the requesting platform.

          @param request
          @type concert_srvs.GetInteractionsRequest
        '''
        response = concert_srvs.GetInteractionsResponse()
        response.interactions = []

        if request.roles:  # works for None or empty list
            unavailable_roles = [x for x in request.roles if x not in self.interactions_table.roles()]
            for role in unavailable_roles:
                rospy.logwarn("Interactions : received request for interactions of an unregistered role [%s]" % role)

        filtered_interactions = self.interactions_table.filter(request.roles, request.uri)
        for i in filtered_interactions:
            response.interactions.append(i.msg)
        return response

    def _ros_service_set_interactions(self, request):
        '''
          Add or remove interactions from the interactions table.

          Note: uniquely identifying apps by name (not very sane).

          @param request list of roles-apps to set
          @type concert_srvs.SetInteractionsRequest
        '''
        if request.load:
            (new_interactions, invalid_interactions) = self.interactions_table.load(request.interactions)
            for i in new_interactions:
                rospy.loginfo("Interactions : loading %s [%s-%s-%s]" % (i.display_name, i.name, i.role, i.namespace))
            for i in invalid_interactions:
                rospy.logwarn("Interactions : failed to load %s [%s-%s-%s]" (i.display_name, i.name, i.role, i.namespace))
        else:
            removed_interactions = self.interactions_table.unload(request.interactions)
            for i in removed_interactions:
                rospy.loginfo("Interactions : unloading %s [%s-%s-%s]" % (i.display_name, i.name, i.role, i.namespace))
        response = concert_srvs.SetInteractionsResponse()
        response.result = True
        return response

    def _ros_service_request_interaction(self, request):
        response = concert_srvs.RequestInteractionResponse()
        response.result = True
        response.error_code = concert_msgs.ErrorCodes.SUCCESS
        maximum_quota = None
        if request.role in self.role_and_app_table.keys():
            for app in self.role_and_app_table[request.role]:  # app is concert_msgs.RemoconApp
                if app.name == request.application and app.namespace == request.namespace:
                    if app.max == 0:
                        return response
                    else:
                        maximum_quota = app.max
                        break
        if maximum_quota is not None:
            count = 0
            for remocon_monitor in self._remocon_monitors.values():
                if remocon_monitor.status is not None and remocon_monitor.status.running_app:
                    # Todo this is a weak check as it is not necessarily uniquely identifying the app
                    if remocon_monitor.status.app_name == request.application:
                        count += 1
            if count < max:
                return response
            else:
                response.error_code = concert_msgs.ErrorCodes.ROLE_APP_QUOTA_REACHED
                response.message = concert_msgs.ErrorCodes.MSG_ROLE_APP_QUOTA_REACHED
        else:
            response.error_code = concert_msgs.ErrorCodes.ROLE_APP_UNAVAILABLE
            response.message = concert_msgs.ErrorCodes.MSG_ROLE_APP_UNAVAILABLE
        response.result = False
        return response
