from enum import Enum, auto


class InitGameSub(Enum):
    WAIT = auto()
    RESTART = auto()
    EXIT = auto()


class SpiderEscapeSub(Enum):
    FIRST = auto()
    SECOND = auto()
    THIRD = auto()
    FOURTH = auto()
    EXIT = auto()


class MatchThreeSub(Enum):
    SWIPES = auto()
    HEROES_ULT = auto()
    EXIT = auto()


class SkipClicksSub(Enum):
    BEFORE_TAVERN = auto()
    OPEN_TASKS = auto()
    OPEN_TAVERN = auto()
    EXIT = auto()


class NoahsTavernSub(Enum):
    SKIP_HEROE = auto()
    SKIP_ALL = auto()
    EXIT = auto()
