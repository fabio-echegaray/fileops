from enum import Enum


class ZProjection(Enum):
    UNSPECIFIED = -100
    MAX = -101
    MIN = -102
    SUM = -103
    STD = -104
    MEAN = -105
    MEDIAN = -106


def zprojection_from_str(proj_str: str) -> ZProjection | None:
    if type(proj_str) != str:
        return None

    proj_str = proj_str.lower()

    if proj_str[0:3] == 'all':
        proj_str = proj_str.split('-')[1]

    if proj_str == 'max':
        return ZProjection.MAX
    elif proj_str == 'min':
        return ZProjection.MIN
    elif proj_str == 'sum':
        return ZProjection.SUM
    elif proj_str == 'std':
        return ZProjection.STD
    elif proj_str == 'mean' or proj_str == 'avg':
        return ZProjection.MEAN
    elif proj_str == 'median':
        return ZProjection.MEDIAN
    else:
        return ZProjection.UNSPECIFIED
