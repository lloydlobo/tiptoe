import cProfile
import pstats

import internal.prelude as pre
from game import Launcher


iscprofile: bool = False
iscprofile = pre.DEBUG_GAME_CPROFILE


def main():
    """Main entry point"""

    launcher = Launcher()
    launcher.start()


if __name__ == "__main__":
    if iscprofile:
        cProfile.run("main()", "cProfile_main", sort="cumulative")
        p = pstats.Stats("cProfile_main")
        p.strip_dirs().sort_stats("cumulative").print_stats()
    else:
        main()
