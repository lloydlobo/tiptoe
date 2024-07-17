# file: Makefile

###################################################################################################
#
#
#   Makefile
#
#
#   $ nix-shell --show-trace
#   (nix-shell) make -B -j4 build && make -j4 copy-data-to-dist
#   (nix-shell) tar czf tiptoe.tar.gz --directory=./dist .
#
#
###################################################################################################

# Run this by default, when no targets are passed to `make`
# .PHONY: all build clean summary test

#------------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------------

BINARY = tiptoe

SRCDIR = ./src
DISTDIR = ./dist

PROG = $(SRCDIR)/tiptoe.py
PROG_EDITOR = $(SRCDIR)/editor.py

TESTSRCS = $(SRCDIR)/test_editor.py $(SRCDIR)/test_game.py

DFLAGS=

#------------------------------------------------------------------------------------
# Variables
#------------------------------------------------------------------------------------

LEVEL = 0

#------------------------------------------------------------------------------------
# Targets
#------------------------------------------------------------------------------------

# Ensure pyinstaller is installed or use inside nix-shell
# See also: ~
#   - https://stackoverflow.com/questions/28033003/pyinstaller-with-pygame
build: ./src/game.py
	@echo "Starting build"
	@pyinstaller --onefile $(PROG) && echo "[info] exit code: $$?"

	@stat $(DISTDIR)/$(BINARY)
	@echo "Finished build"

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
	@stat $(DISTDIR)

	@echo "  - Starting"
	trash --verbose $(DISTDIR)
	@echo "  - Finished"


edit:
	@echo "edit"
	@echo "  - Starting"

	@echo "  - Start the editor at level 0:"
	@echo "       (Tip: make edit LEVEL=1)"
	python ${PROG_EDITOR} ${LEVEL}
	@echo "  - Finished"

# black --quiet $(SRCDIR)
format:
	black $(SRCDIR)

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

strace-binary:
	@echo "strace-binary"
	@strace -c ./dist/$(BINARY)

# make -j4  watch DFLAGS=--debug
# fd --extension=py | entr -r python ./src/tiptoe.py --debug
watch:
	@echo "watch"
	@echo "  - Starting"
	@echo "  - Send a `SIGTERM` to any previously spawned python subprocesses before executing 'python tiptoe.py':"
	@echo "        (TIP: reload: <Space>, exit: <q>)"

	@fd --extension=py | entr -r python ${PROG} $(DFLAGS)
	@echo "  - Finished"

targzip:
	@echo "tarzip" && echo "[info] $$(date +%s) [c]reating a g[z]ipped archive from a directory using relative paths"
	@echo "  - Starting"
	@tar czvf tiptoe.tar.gz --directory=./dist .
	@echo "  - Finished" && echo "Finished: tar saved many files together into a single tape or disk archive, that can be restored to individual files from the archive"
	@stat tiptoe.tar.gz

#@Redundancy
# make build && make copy-data-to-dist && du -ch ./dist && stat ./dist/$(BINARY)
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

#------------------------------------------------------------------------------------
# Tests
#------------------------------------------------------------------------------------

# ❯ python -m doctest src/internal/prelude.py -v
# ❯ find . -name 'prelude.py' | entr -cprs 'make -j4 doctest'
doctest:
	@echo "doctest"
	@echo "  - Starting"
	# find . -name '*.py' | xargs -I _ python -m doctest _
	python -m doctest ./src/internal/prelude.py
	@echo "  - Finished"

# time parallel -j4 --bar --eta python ::: $(TESTSRCS) && echo "exit code: $$?"
test:
	@echo "test" && echo "[info] $$(date +%s) NOTE: Test works only for builtin unittest"
	@echo "  - Starting"
	find src -name "test_*.py" | parallel -j 4 --bar --eta python {}
	@echo "  - Finished"

# $ fd -e py . | grep test | entr -crs 'make -j4 test-pytest'
test-pytest:
	@echo "test" && echo "[info] $$(date +%s) Testing via pytest"
	@echo "  - Starting"
	pytest -v src/internal/test_{animation,assets,prelude,spark,tilemap}.py
	@echo "  - Finished"


# fd -e py . | entr -cprs 'make -j4 test-discover'
#	-s starting directory
#	-p pattern
test-discover:
	@echo "test" && echo "[info] $$(date +%s) Testing via python -m unittest discover"
	@echo "  - Starting"
	@python -m unittest discover -s src -p "test*.py"
	@echo "  - Finished"

#------------------------------------------------------------------------------------
# Notes
#------------------------------------------------------------------------------------

# Override a variable defined in the Makefile:
#
# 	make target variable=new_value

# Force making of a target, even if source files are unchanged:
#
# 	make --always-make target

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
