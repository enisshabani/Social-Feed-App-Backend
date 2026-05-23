from fastapi import HTTPException, status

class NotificationNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

class NotificationForbiddenError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access this notification")
