from fastapi import HTTPException


def api_error(status: int, code: str, message: str, **extra) -> HTTPException:
    """رد خطأ موحّد: {"detail": {"code": ..., "message": ...}}"""
    return HTTPException(status, detail={"code": code, "message": message, **extra})
