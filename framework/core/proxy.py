#!/usr/bin/env python
# -*- coding: utf-8 -*-
#     
#     proxy.py
#     
#     This file is part of the RoboEarth Cloud Engine framework.
#     
#     This file was originally created for RoboEearth
#     http://www.roboearth.org/
#     
#     The research leading to these results has received funding from
#     the European Union Seventh Framework Programme FP7/2007-2013 under
#     grant agreement no248942 RoboEarth.
#     
#     Copyright 2012 RoboEarth
#     
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#     
#     http://www.apache.org/licenses/LICENSE-2.0
#     
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#     
#     \author/s: Dominique Hunziker 
#     
#     

# ROS specific imports
import rosgraph.names

# zope specific imports
from zope.interface import implements

# twisted specific imports
from twisted.python import log

# Custom imports
from errors import InternalError, InvalidRequest
from util.interfaces import verifyObject
from core.interfaces import IEndpointProxy, IEndpointControl, IRobotControl, \
    INodeControl, IParameterControl, IContainerControl
from core.command import NodeCommand, ParameterCommand, ArrayCommand, FileCommand, \
    ContainerCommand, RobotCommand


class _EndpointProxy(object):
    """ Base class which provides the necessary methods for all endpoint
        proxies.
    """
    implements(IEndpointProxy)
    
    def __init__(self, user, uid, commID, control):
        """ Initialize the endpoint monitor.
            
            @param user:        User to which this endpoint belongs.
            @type  user:        core.user.User
            
            @param uid:         Identifier of this endpoint.
            @type  uid:         str
            
            @param commID:      Communication ID of this endpoint.
            @type  commID:      str
            
            @param control:     Control which is used to send the commands to
                                the endpoint.
            @type  control:     core.interfaces.IEndpointControl
        """
        verifyObject(IEndpointControl, control)
        
        self._user = user
        self._uid = uid
        self._commID = commID
        self._control = control
        self._interfaces = set()
    
    @property
    def owner(self):
        """ Owner (type: core.user.User) of this endpoint. """
        return self._user
    
    @property
    def uid(self):
        """ Identifier of this endpoint. """
        return self._uid
    
    @property
    def commID(self):
        """ Communication ID of this endpoint. """
        return self._commID
    
    def registerInterface(self, interface):
        """ Register a new interface with this endpoint.
            
            @param interface:   Interface instance which should be registered.
            @type  interface:   core.interface.Interface
        """
        if interface in self._interfaces:
            raise InternalError('There exists already an interface '
                                'with the same tag.')
        
        interface.registerControl(self._control)
        self._interfaces.add(interface)
    
    def unregisterInterface(self, interface):
        """ Unregister an interface with this endpoint.
            
            @param interface:   Interface instance which should be
                                unregistered.
            @type  interface:   core.interface.Interface
        """
        if interface not in self._interfaces:
            raise InternalError('Tried to unregister a non existing '
                                'interface.')
        
        self._interfaces.remove(interface)
    
    def delete(self):
        """ Removes the proxy, i.e. the represented endpoint.
            
            Make sure to call this method, because this method makes sure that
            all necessary references are removed.
            
            Once this method is called this monitor can no longer be used.
        """
        for interface in self._interfaces.copy():
            interface.delete()
        
        self._user = None
        self._control = None


class RobotProxy(_EndpointProxy):
    """ Class which is used to keep track of the status of a Robot.
    """
    def __init__(self, user, robotID, commID, key, control):
        """ Initialize the Robot proxy.
            
            @param user:        User to which this robot belongs.
            @type  user:        core.user.User
            
            @param robotID:     RobotID which is used to identify the robot.
            @type  robotID:     str
            
            @param commID:      Communication ID of this robot.
            @type  commID:      str
            
            @param key:         Key which should be used to verify connection
                                from represented robot.
            @type  key:         str
                                    
            @param control:     Control which is used to communicate with the
                                robot.
            @type  control:     core.interfaces.IRobotControl
        """
        verifyObject(IRobotControl, control)
        
        super(RobotProxy, self).__init__(user, robotID, commID, control)
        
        control.createRobot(RobotCommand(robotID, key))
    
    def delete(self):
        """ Removes the proxy, i.e. the represented robot.
            
            Make sure to call this method, because this method makes sure that
            all necessary references are removed.
            
            Once this method is called this monitor can no longer be used.
        """
        self._control.destroyRobot(self._uid)
        
        super(RobotProxy, self).delete()


class ROSEnvProxy(_EndpointProxy):
    """ Class which is used to keep track of the status of a ROS environment.
    """
    def __init__(self, user, tag, commID, control):
        """ Initialize the ROS environment proxy.
            
            @param user:        User instance to which this ROS environment
                                belongs.
            @type  user:        core.user.User
            
            @param tag:         Tag of this environment.
            @type  tag:         str
            
            @param commID:      CommID of the ROS environment.
            @type  commID:      str
             
            @param control:     Control which is used to communicate with the
                                ROS environment.
            @type  control:     core.interfaces.IROSEnvControl
        """
        verifyObject(INodeControl, control)
        verifyObject(IParameterControl, control)
        
        super(ROSEnvProxy, self).__init__(user, tag, commID, control)
        
        self._rosAddrs = set()
    
    def addNode(self, tag, pkg, exe, args, name, namespace):
        """ Add a node to the monitored ROS environment.
            
            @param tag:     Tag which is used to identify the ROS node which
                            should added.
            @type  tag:     str

            @param pkg:     Package name where the node can be found.
            @type  pkg:     str

            @param exe:     Name of executable which should be launched.
            @type  exe:     str
            
            @param args:    Arguments which should be used for the launch.
            @type  args:    str
            
            @param name:    Name of the node under which it should be launched.
            @type  name:    str
            
            @param namespace:   Namespace in which the node should use be
                                launched.
            @type  namespace:   str
            
            @raise:     errors.InvalidRequest
        """
        # First make sure, that the received strings are str objects
        # and not unicode objects
        if isinstance(pkg, unicode):
            try:
                pkg = str(pkg)
            except UnicodeEncodeError:
                raise InvalidRequest('The package "{0}" is not '
                                     'valid.'.format(pkg))
        
        if isinstance(exe, unicode):
            try:
                exe = str(exe)
            except UnicodeEncodeError:
                raise InvalidRequest('The executable "{0}" is not '
                                     'valid.'.format(exe))
        
        if isinstance(name, unicode):
            try:
                name = str(name)
            except UnicodeEncodeError:
                raise InvalidRequest('The name "{0}" is not '
                                     'valid.'.format(name))
        
        if isinstance(namespace, unicode):
            try:
                namespace = str(namespace)
            except UnicodeEncodeError:
                raise InvalidRequest('The namespace "{0}" is not '
                                     'valid.'.format(namespace))
        
        if not rosgraph.names.is_legal_name(namespace):
            raise InvalidRequest('The namespace "{0}" is not '
                                 'valid.'.format(namespace))
        
        log.msg('Start node "{0}/{1}" (tag: "{2}") in ROS environment '
                '"{3}".'.format(pkg, exe, tag, self._commID))
        self._control.addNode(NodeCommand(tag, pkg, exe, args, name,
                                          namespace))
    
    def removeNode(self, tag):
        """ Remove a node from the monitored ROS environment.
            
            @param tag:     Tag which is used to identify the ROS node which
                            should be removed.
            @type  tag:     str
        """
        log.msg('Remove node (tag: "{0}") from ROS environment '
                '"{1}".'.format(tag, self._commID))
        self._control.removeNode(tag)
    
    def _castStr(self, value):
        """ Internally used method to convert a value to a string.
        """
        if isinstance(value, str):
            return value
        elif isinstance(value, unicode):
            return str(value)
        
        raise ValueError('Value is not a valid string.')
        
    def _castBool(self, value):
        """ Internally used method to convert a value to a bool.
        """
        if isinstance(value, basestring):
            value = value.strip().lower()
            
            if value == 'true':
                return True
            elif value == 'false':
                return False
        else:
            try:
                return bool(int(value))
            except ValueError:
                pass
        
        raise ValueError('Value is not a valid bool.')
    
    def _cast(self, value, paramType):
        """ Internally used method to convert a value.
        """
        if paramType == 'int':
            return int(value)
        elif paramType == 'str':
            return self._castStr(value)
        elif paramType == 'float':
            return float(value)
        elif paramType == 'bool':
            return self._castBool(value)
        
        raise ValueError('Parameter type is invalid.')
    
    def addParameter(self, name, value, paramType):
        """ Add a parameter to the parameter server in the monitored ROS
            environment.
            
            @param name:    Name of the parameter which should be added.
            @type  name:    str
            
            @param value:   Value of the parameter which should be added.
            @type  value:   Depends on @param paramType
            
            @param paramType:   Type of the parameter to add. Valid base types
                                are:
                                    int, str, float, bool
                                
                                The base types can be summarized to an array,
                                for example:
                                    [int, str, bool, str]
                                
                                Additionally, a special type is defined for
                                adding a file; this type can't be used in an
                                array:
                                    file
            @type  paramType:   str
            
            @raise:     InvalidRequest if the name is not a valid ROS name.
        """
        if not rosgraph.names.is_legal_name(name):
            raise InvalidRequest('The name "{0}" is not valid.'.format(name))
        
        paramType = paramType.strip()
        
        try:
            if paramType == 'file':
                param = FileCommand(name, self._castStr(value))
            else:
                if paramType[0] == '[' and paramType[-1] == ']':
                    paramType = map(lambda x: x.strip(),
                                    paramType[1:-1].split(','))
                    cmd = ArrayCommand
                else:
                    value = [value]
                    paramType = [paramType]
                    cmd = ParameterCommand
            
                if len(value) != len(paramType):
                    raise InvalidRequest('Length of parameter specification '
                                         'does not match length of supplied '
                                         'values.')
                
                value = [self._cast(*pair) for pair in zip(value, paramType)]
                paramType = ''.join(p.upper()[0] for p in paramType)
                param = cmd(name, value, paramType)
        except ValueError as e:
            raise InvalidRequest(str(e))
        
        log.msg('Add parameter "{0}" to ROS environment "{1}".'.format(
                    name, self._commID))
        self._control.addParameter(param)
    
    def removeParameter(self, name):
        """ Remove a parameter from the parameter server in the monitored ROS
            environment.
            
            @param name:    Name of the parameter which should be removed.
            @type  name:    str
        """
        log.msg('Remove parameter "{0}" from ROS environment "{1}".'.format(
                    name, self._commID))
        self._control.removeParameter(name)
    
    def reserveAddr(self, addr):
        """ Callback method for Interface to reserve the ROS address.
            
            @param addr:    ROS address which should be reserved.
            @type  adrr:    str
            
            @raise:     ValueError if the address is already in use.
        """
        if addr in self._rosAddrs:
            raise ValueError('Address already is in use.')
        
        self._rosAddrs.add(addr)
    
    def freeAddr(self, addr):
        """ Callback method for Interface to free the ROS address.
            
            @param addr:    ROS address which should be freed.
            @type  addr:    str
        """
        if addr not in self._rosAddrs:
            log.msg('Tried to free an address which was not reserved.')
        else:
            self._rosAddrs.remove(addr)


class ContainerProxy(ROSEnvProxy):
    """ Class which is used to keep track of the status of a container
        (containing a ROS environment).
    """
    def __init__(self, user, cTag, commID, control):
        """ Initialize the Container proxy.
            
            @param user:        User instance to which this Container belongs.
            @type  user:        core.user.User
                                    
            @param control:     Control which is used to communicate with the
                                Container.
            @type  control:     core.interfaces.IContainerControl
            
            @param commID:      CommID of the ROS environment inside the
                                Container.
            @type  commID:      str
            
            @param cTag:        Container tag which is used by the user to
                                identify this Container.
            @type  cTag:        str
        """
        verifyObject(IContainerControl, control)
        
        super(ContainerProxy, self).__init__(user, cTag, commID, control)
        
        self._connected = False   # TODO: At the moment not used
        
        log.msg('Start container "{0}".'.format(commID))
        control.createContainer(ContainerCommand(cTag, commID))
    
    @property
    def status(self):   # TODO: At the moment not used
        """ Status of the container. (True = connected; False = disconnected)
        """
        return self._connected
    
    def setConnectedFlag(self, flag):   # TODO: At the moment not used
        """ Set the 'connected' flag for the container.
            
            @param flag:    Flag which should be set. True for connected and
                            False for not connected.
            @type  flag:    bool
            
            @raise:         InvalidRequest if the container is already
                            registered as connected.
        """
        if flag:
            if self._connected:
                raise InvalidRequest('Tried to set container to connected '
                                     'which already is registered as '
                                     'connected.')
            
            self._connected = True
            self._user.sendContainerUpdate(self._uid, True)
        else:
            self._connected = False
            self._user.sendContainerUpdate(self._uid, False)
    
    def delete(self):
        """ Removes the monitor, i.e. the represented container.
            
            Make sure to call this method, because this method makes sure
            that all necessary references are removed.
            
            Once this method is called this monitor can no longer be used.
        """
        log.msg('Stop container "{0}".'.format(self._commID))
        self._control.destroyContainer(self._uid)
        
        super(ContainerProxy, self).delete()
