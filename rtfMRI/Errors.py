"""Excpetion definitions for rtfMRI"""

class RTError(Exception):
    """Top level general error"""
    pass

class ValidationError(RTError):
    """Invalid information supplied in a call"""
    pass

class StateError(RTError):
    """System is not in a valid state relative to the request"""
    pass

class RequestError(RTError):
    """Error in the request"""
    pass

class MessageError(RTError):
    """Invalid message"""
    pass

class InvocationError(RTError):
    """program arguments incorrect"""
    pass
