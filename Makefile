# file: Makefile

###################################################################################################
#
#
#   Makefile
#
#
#
#   $ nix-shell --show-trace
#   (nix-shell) make -B -j4 build && make -B -j4 copy-data-to-dist
#   (nix-shell) tar czf tiptoe.tar.gz --directory=./dist .
#
#
###################################################################################################

# Run this by default, when no targets are passed to `make`
# .PHONY: all build clean summary test

# Constants
#------------------------------------------------------------------------------
BINARY = tiptoe

SRCDIR = ./src
DISTDIR = ./dist

PROG = $(SRCDIR)/tiptoe.py
PROG_EDITOR = $(SRCDIR)/editor.py
#------------------------------------------------------------------------------

# Variables
#------------------------------------------------------------------------------
LEVEL = 0
#------------------------------------------------------------------------------

# Targets
#------------------------------------------------------------------------------
# Ensure pyinstaller is installed or use inside nix-shell
# See also: ~
#   - https://stackoverflow.com/questions/28033003/pyinstaller-with-pygame
build:
	@echo "Starting build"
	@pyinstaller --onefile $(PROG) && echo "[info] exit code: $$?"
	@stat $(DISTDIR)/$(BINARY)
	@echo "Finished build"


# make -B -j4 build && make -B -j4 copy-data-to-dist
copy-data-to-dist:
	@echo "copy-data-to-dist"
	@echo "  - Starting: Copying data"
	mkdir -p $(DISTDIR)/src/data
	@echo "[info] exit code: $$?"
	cp -r $(SRCDIR)/data $(DISTDIR)/src/ 
	@echo "[info] exit code: $$?"
	cp -r $(SRCDIR)/config $(DISTDIR)/src 
	@echo "[info] exit code: $$?"
	@echo "  - Finished: Copied data"

clean:
	@echo "clean"
	@echo "  - Starting"
	@echo "  - Finished"

edit:
	@echo "edit"
	@echo "  - Starting"

	@echo "  - Start the editor at level 0:"
	@echo "       (Tip: make edit LEVEL=1)"
	python ${PROG_EDITOR} ${LEVEL}
	@echo "  - Finished"

format:
	black --quiet $(SRCDIR)

run:
	@echo "run"
	@echo "  - Starting"

	@echo "  - Run the game:"
	python ${PROG}
	@echo "  - Finished"

summary:
	@echo "summary"
	@echo "  - Starting"

	@echo "  - Display information for the current directory:"
	dust --reverse

	@echo "  - Display a report for the code in a directory and all subdirectories:"
	tokei --files

	@echo "  - Show a history of commits:"
	git log --oneline | head 
	@echo "  - Finished"

test:
	@echo "test"
	@echo "unimplemented"


strace-binary:
	@echo "strace-binary"
	strace -c ./dist/$(BINARY)

watch:
	@echo "watch"
	@echo "  - Starting"

	@echo "  - Send a `SIGTERM` to any previously spawned python subprocesses before executing 'python tiptoe.py':"
	@echo "        (Tip: use spacebar to reload)"
	fd --extension=py | entr -r python ${PROG}
	@echo "  - Finished"

targzip:
	@echo "tarzip" && echo "[info] $$(date +%s) [c]reating a g[z]ipped archive from a directory using relative paths"
	@echo "  - Starting"
	@tar czvf tiptoe.tar.gz --directory=./dist .
	@echo "  - Finished" && echo "Finished: tar saved many files together into a single tape or disk archive, that can be restored to individual files from the archive"
	@stat tiptoe.tar.gz
#
#$ make build && make copy-data-to-dist && du -ch ./dist && stat ./dist/$(BINARY)
#
build-copy-data: build copy-data-to-dist
	@du -ch ./dist 
	@stat ./dist/$(BINARY)

#@Redundancy
dump_all:
	@echo "dump"
	@echo "  - Starting"
	@fd --extension py . | xargs -I _ cat _ | hexdump -C | cat
	@echo "  - Finished"

#@Redundancy
od_all:
	@echo "dump"
	@echo "  - Starting"
	@fd --extension py . | xargs -I _ cat _ | od | cat
	@echo "  - Finished"
#------------------------------------------------------------------------------

# Notes
#------------------------------------------------------------------------------

# Override a variable defined in the Makefile:
#
# 	make target variable=new_value

# Force making of a target, even if source files are unchanged:
#
# 	make --always-make target

#################################################################
# Archive
#################################################################

# build-credits:
# 	@echo "build-credits"
# 	@echo "  - Starting"
# 	@echo "  - build"
# 	clang++ -g -std=c++11 gcredits.cpp -o build/gcredits -DLAB_SLOW=1 
# 	@echo "  - Finished"
#
# build-run-credits:
# 	@echo "buildruncredits"
# 	@echo "  - Starting"
# 	@echo "  - build"
# 	clang++ -g -std=c++11 gcredits.cpp -o build/gcredits -DLAB_SLOW=1 
# 	@echo "  - run"
# 	valgrind -s --leak-check=full ./build/gcredits
# 	@echo "  - Finished"
# #
# # $ ls *.cpp | entr -r make memcheck-build-run-credits
# #
# memcheck-build-run-credits:
# 	@echo "buildruncredits"
# 	@echo "  - Starting"
# 	@echo "  - build"
# 	clang++ -g -std=c++11 gcredits.cpp -o build/gcredits -DLAB_SLOW=1 
# 	@echo "  - run"
# 	valgrind -s --leak-check=full ./build/gcredits
# 	@echo "  - Finished"
#
#------------------------------------------------------------------------------
