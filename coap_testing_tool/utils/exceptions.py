
# - - - - Exceptions - - - - -

class CoordinatorError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        """Return the exception message"""
        return self.message

class SnifferError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        """Return the exception message"""
        return self.message

class TatError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        """Return the exception message"""
        return self.message

class AmqpMessageError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        """Return the exception message"""
        return self.message
