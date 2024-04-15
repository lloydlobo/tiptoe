# @dataclass
# class Assets:
#     player: pg.Surface
#     enemy: pg.Surface
#     grass: list[pg.Surface]
#     stone: list[pg.Surface]
#     decor: list[pg.Surface]
#     large_decor: list[pg.Surface]
#
#     def for_entity(self, key: EntityKind):
#         match key:
#             case EntityKind.PLAYER:
#                 return self.player
#             case EntityKind.ENEMY:
#                 return self.enemy
#                 # Pattern will never be matched for subject type "Never" [reportUnnecessaryComparison]
#                 # case _:
#                 #   sys.exit()
#
#         if not isinstance(key, EntityKind):
#             raise ValueError(f"expected EntityKind. got {type(key)}")
#         else:
#             return pg.Surface((TILE_SIZE, TILE_SIZE))
#
#     def for_tile(self, key: TileKind):
#         if key == TileKind.GRASS:
#             return self.grass
#         elif key == TileKind.STONE:
#             return self.stone
