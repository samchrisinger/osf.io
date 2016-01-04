"""
Custom exceptions for add-ons.
"""


class AddonError(Exception):
    pass


class HookError(AddonError):
    pass

class InvalidAuthError(AddonError):
    pass
