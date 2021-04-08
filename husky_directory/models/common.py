"""
Models that are shared by more than one service. These should be
bare-bones models that do not define specialized behavior unless
the behavior itself is truly common. Otherwise, those behaviors
should be declared in an inheriting subclass within the context of
the respective service model.
"""
from pydantic import BaseModel


class UWDepartmentRole(BaseModel):
    """Denotes that an identity has some role within the UW (e.g., a job title, or class level)."""

    class Config:
        orm_mode = True

    title: str
    department: str
