from fastapi import HTTPException, status


class GameNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="当前没有进行中的游戏")


class PlayerNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="玩家不存在")


class InvalidGameStateException(HTTPException):
    def __init__(self, detail: str = "游戏状态不允许此操作"):
        super().__init__(status_code=400, detail=detail)


class AlreadyAssignedRoleException(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="该玩家已分配角色")


class CaptureException(HTTPException):
    def __init__(self, detail: str = "抓捕失败"):
        super().__init__(status_code=400, detail=detail)


class ReviveException(HTTPException):
    def __init__(self, detail: str = "复活失败"):
        super().__init__(status_code=400, detail=detail)
