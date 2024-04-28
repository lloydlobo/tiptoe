from collections import deque
from dataclasses import dataclass
from enum import Enum, auto, unique
from typing import Any, Callable, Optional, Sequence

import pygame as pg

import internal.prelude as pre


@unique
class MoveUnitCommand(Enum):
    EXECUTE = auto()
    UNDO = auto()
    REDO = auto()
    NONE = auto()


MoveUnitCommandCallableDictType = dict[MoveUnitCommand, Callable[[], None]]


def create_move_unit_command(unit: pg.Vector2, next_pos: pre.Vec2Type, max_dist: float = pre.TILE_SIZE**2) -> MoveUnitCommandCallableDictType:
    redo_stack: deque[Any] = deque(maxlen=256)
    prev_x: Optional[float] = None
    prev_y: Optional[float] = None

    def execute() -> None:
        nonlocal prev_x, prev_y
        prev_x, prev_y = unit.xy
        unit.move_towards_ip(next_pos, max_dist)
        redo_stack.appendleft(undo)

    def undo() -> None:
        nonlocal prev_x, prev_y
        if prev_x is not None and prev_y is not None:
            unit.move_towards_ip((prev_x, prev_y), max_dist)
            redo_stack.appendleft(execute)

    def redo() -> None:
        if prev_x is not None and prev_y is not None:
            if redo_stack:
                redo_cmd = redo_stack.popleft()
                redo_cmd()

    def none() -> None:
        pass

    if 0:  # getting not accesed function errors
        cmds: MoveUnitCommandCallableDictType = {}
        for key in MoveUnitCommand:
            cmds[key] = locals()[key.name.lower()]

    # cmds = {MoveUnitCommandKind.EXECUTE: execute, MoveUnitCommandKind.UNDO: undo, MoveUnitCommandKind.REDO: redo, MoveUnitCommandKind.NONE: none}

    cmds: MoveUnitCommandCallableDictType = {}
    for key in MoveUnitCommand:
        match key:
            case MoveUnitCommand.EXECUTE:
                cmds[key] = execute
            case MoveUnitCommand.UNDO:
                cmds[key] = undo
            case MoveUnitCommand.REDO:
                cmds[key] = redo
            case MoveUnitCommand.NONE:
                cmds[key] = none
    return cmds


def test__internal__move__commands__py():
    @dataclass
    class MoveCase:
        init_pos: pg.Vector2
        next_pos: pg.Vector2
        max_dist: float
        exec_expected: tuple[float, float]
        undo_expected: tuple[float, float]
        redo_expected: tuple[float, float]

    def test__move__command__execution():
        test_cases: Sequence[MoveCase] = [
            MoveCase(pg.Vector2(0, 0), pg.Vector2(10, 10), 100, (10, 10), (0, 0), (10, 10)),
            MoveCase(pg.Vector2(5, 5), pg.Vector2(15, 15), 100, (15, 15), (5, 5), (15, 15)),
            MoveCase(pg.Vector2(10, 10), pg.Vector2(20, 20), 100, (20, 20), (10, 10), (20, 20)),
        ]
        for tc in test_cases:
            unit = tc.init_pos
            commands = create_move_unit_command(unit, tc.next_pos, tc.max_dist)
            commands[MoveUnitCommand.EXECUTE]()
            assert unit.xy == tc.exec_expected
            assert unit == pg.Vector2(*tc.exec_expected)
            commands[MoveUnitCommand.UNDO]()
            assert unit.xy == tc.undo_expected
            assert unit == pg.Vector2(*tc.undo_expected)
            commands[MoveUnitCommand.REDO]()
            assert unit.xy == tc.redo_expected
            assert unit == pg.Vector2(*tc.redo_expected)

    try:
        test__move__command__execution()
        print("Unit movement commands tested successfully.")
    except AssertionError as e:
        print(f"Unit movement commands test failed: {e}")
    except Exception as e:
        print(f"An error occurred during unit movement commands test: {e}")


# NOTE: this works as backup
# ################################################################################
# ### COMMANDS
# ################################################################################
#
#
# # Type variable.
# #
# # Usage:
# #
# #   T = TypeVar('T')  # Can be anything
# #   A = TypeVar('A', str, bytes)  # Must be str or bytes
# #
# # Note that only type variables defined in global scope can be pickled.
# A = TypeVar("A", pg.Vector2, tuple[float, float])  #  or use "pg.Vector"
#
#
# class MoveUnitCommand(Enum):
#     EXECUTE = auto()
#     UNDO = auto()
#     REDO = auto()
#     NONE = auto()
#
#
# MoveUnitCommandKindsType = dict[MoveUnitCommand, Callable[[], None]]  # for example; key: MoveUnitCommandKind.EXECUTE, value: () -> None
#
#
# # unit can be a vector2, surface or rect
# def create_move_unit_command(unit: pg.Vector2, next_pos: A, max_dist: float = TILE_SIZE**2):
#     """
#     Example:
#
#         ```javascript
#         // Source https://gameprogrammingpatterns.com/command.html
#         function makeMoveUnitCommand(unit, x, y) {
#           var xBefore, yBefore;
#           return {
#             execute: function() { xBefore = unit.x(); yBefore = unit.y(); unit.moveTo(x, y); },
#             undo: function() { unit.moveTo(xBefore, yBefore); }
#           };
#         }
#         ```
#     Note: By using nonlocal, you tell Python to look for the specified variable in the nearest enclosing scope that is not the global scope. This allows you to modify that variable's value.
#     Note: If performance is critical, you might want to remove or disable type checking in the final production code.
#     """
#     redo_stack: deque[Any] = deque(maxlen=2**8)  # 2**8 == 256
#     prev_x: Optional[Number] = None
#     prev_y: Optional[Number] = None
#
#     def execute() -> None:
#         nonlocal prev_x, prev_y
#         prev_x, prev_y = unit
#         unit.move_towards_ip((next_pos), max_dist)
#         redo_stack.appendleft(undo)
#
#     def undo() -> None:
#         nonlocal prev_x, prev_y
#         if prev_x is not None and prev_y is not None:
#             unit.move_towards_ip((prev_x, prev_y), max_dist)
#             redo_stack.appendleft(execute)  # Store the execute function for redoing
#
#     def redo() -> None:
#         if prev_x is not None and prev_y is not None:
#             if redo_stack:
#                 redo_cmd = redo_stack.popleft()
#                 redo_cmd()
#
#     def none() -> None:
#         pass
#
#     # cmds = {MoveUnitCommandKind.EXECUTE: execute, MoveUnitCommandKind.UNDO: undo, MoveUnitCommandKind.REDO: redo, MoveUnitCommandKind.NONE: none}
#     cmds: MoveUnitCommandKindsType = {}
#     for key in MoveUnitCommand:
#         match key:
#             case MoveUnitCommand.EXECUTE:
#                 cmds[key] = execute
#             case MoveUnitCommand.UNDO:
#                 cmds[key] = undo
#             case MoveUnitCommand.REDO:
#                 cmds[key] = redo
#             case MoveUnitCommand.NONE:
#                 cmds[key] = none
#     return cmds
#
#
# # Test code
#
#
# @dataclass
# class MoveCase:
#     init_pos: pg.Vector2
#     next_pos: pg.Vector2
#     max_dist: float
#     exec_expected: tuple[Number, Number]
#     undo_expected: tuple[Number, Number]
#     redo_expected: tuple[Number, Number]
#
#
# def test_move_command_execution_tdt():
#     """Test the execution of movement commands."""
#     test_cases: Sequence[MoveCase] = [
#         MoveCase(pg.Vector2(0, 0), pg.Vector2(10, 10), 100, (10, 10), (0, 0), (10, 10)),
#         MoveCase(pg.Vector2(5, 5), pg.Vector2(15, 15), 100, (15, 15), (5, 5), (15, 15)),
#         MoveCase(pg.Vector2(10, 10), pg.Vector2(20, 20), 100, (20, 20), (10, 10), (20, 20)),
#     ]
#     for tc in test_cases:
#         unit = tc.init_pos
#         commands = create_move_unit_command(unit, tc.next_pos, tc.max_dist)
#         commands[MoveUnitCommand.EXECUTE]()
#         assert unit.xy == tc.exec_expected
#         assert unit == pg.Vector2(*tc.exec_expected)
#         commands[MoveUnitCommand.UNDO]()
#         assert unit.xy == tc.undo_expected
#         assert unit == pg.Vector2(*tc.undo_expected)
#         commands[MoveUnitCommand.REDO]()
#         assert unit.xy == tc.redo_expected
#         assert unit == pg.Vector2(*tc.redo_expected)
#
#
# try:
#     test_move_command_execution_tdt()
#     print("Unit movement commands tested successfully.")
# except AssertionError as e:
#     print(f"Unit movement commands test failed: {e}")
# except Exception as e:
#     print(f"An error occurred during unit movement commands test: {e}")
#
