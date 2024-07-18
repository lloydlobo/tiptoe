import json
import logging
from pathlib import Path
from typing import Any, List

import pygame as pg


logger = logging.getLogger(__name__)


class Spritesheet:
    """Spritesheet class for loading sprites from a spritesheet via a JSON metadata file.

    Example::

        logging.basicConfig(level=logging.DEBUG)
        spritesheet = Spritesheet(
            sheet_path=Path("src")/"data"/"images"/"spritesheets"/"large_decor.png",
            metadata_path=Path("src")/"data"/"images"/"spritesheets"/"large_decor.json",
        )

        ld_sprites: list[pygame.SurfaceType] = []
        for group in ["tree", "bush", "pileofbricks"]:
            ld_sprites.extend(spritesheet.load_sprites("large_decor", group))
    """

    def __init__(self, sheet_path: Path, metadata_path: Path) -> None:
        self.sheet_path = sheet_path
        self.metadata_path = metadata_path
        self.spritesheet: pg.SurfaceType = self.load_spritesheet()
        self.metadata: dict[str, Any] = self.load_metadata()

    def load_spritesheet(self) -> pg.SurfaceType:
        """Load the spritesheet image and set the colorkey for transparency.

        Returns:
            pg.SurfaceType: The loaded spritesheet image.
        """
        try:
            img = pg.image.load(self.sheet_path).convert()
            img.set_colorkey((0, 0, 0))  # black background becomes transpaarent
            return img
        except pg.error as e:
            logger.error(f"error loading spritesheet: {e}")
            raise

    def load_metadata(self) -> dict[str, Any]:
        """Load the spritesheet metadata from the JSON file.

        Returns:
            dict[str, Any]: The loaded metadata dictionary.
        """
        try:
            with open(self.metadata_path) as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"error loading metadata: {e}")
            raise

    def load_sprites(self, s_category: str, s_group: str) -> List[pg.SurfaceType]:
        """Load sprites from the spritesheet based on the provided category and group.

        Args:
            category_name (str): The category name in the metadata.
            group_name (str): The group name within the category in the metadata.

        Returns:
            list[pg.SurfaceType]: A list of sprites loaded from the spritesheet.
        """
        try:
            group = self.metadata[s_category][s_group]
            w, h = group["size"]["w"], group["size"]["h"]
            return [
                self.spritesheet.subsurface(
                    pg.Rect(
                        frame["x"],
                        frame["y"],
                        w,
                        h,
                    )
                )
                for frame in group["frames"]
            ]
        except KeyError as e:
            logger.error(f"error loading sprites: {e}")
            raise
