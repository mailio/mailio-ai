class UnsupportedMessageTypeError(Exception):
    def __init__(self, msg_type):
        self.msg_type = msg_type
        super().__init__(f"Unsupported message type: {msg_type}")

class NotFoundError(Exception):
    def __init__(self, id):
        self.id = id
        super().__init__(f"Document not found: {id}")

class UnauthorizedError(Exception):
    def __init__(self):
        super().__init__("Unauthorized")

class InvalidUsageError(Exception):
    def __init__(self):
        super().__init__("Invalid usage")