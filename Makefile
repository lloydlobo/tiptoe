#################################################################
#
#   Makefile
#
#################################################################

# Run this by default, when no targets are passed to `make`
.PHONY: all build clean summary test

# Constants
#---------------------------------------------------------------
BINARY = tiptoe
PROG = src/tiptoe.py
PROG_EDITOR = src/editor.py

# Variables
#---------------------------------------------------------------
level = 0

# Targets
#---------------------------------------------------------------
test: 
	@echo "test"
	@echo "unimplemented"

# Ensure pyinstaller is installed or use inside nix-shell
#
# See also: ~
#   - https://stackoverflow.com/questions/28033003/pyinstaller-with-pygame
build:
 	$(shell pyinstaller --onefile $(PROG)) &

build-copy-data:
	time make build && echo
	time make copy-data-to-dist && echo
	time du -ch ./dist && echo 
	time stat ./dist/$(BINARY) && echo

copy-data-to-dist:
	@echo "Copying data" && echo
	mkdir -vp ./dist/src/data
	cp -vr ./src/data ./dist/src/
	cp -vr ./src/config ./dist/src
	@echo "Finished build" && echo

clean:
	@echo "clean"
	@echo "  - Starting"
	@echo "  - Finished"

edit:
	@echo "edit"
	@echo "  - Starting"

	@echo "  - Start the editor at level 0:"
	@echo "       (Tip: make edit level=1)"
	python ${PROG_EDITOR} ${level}
	@echo "  - Finished"

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

watch:
	@echo "watch"
	@echo "  - Starting"

	@echo "  - Send a `SIGTERM` to any previously spawned python subprocesses before executing 'python tiptoe.py':"
	@echo "        (Tip: use spacebar to reload)"
	fd --extension=py | entr -r python ${PROG}
	@echo "  - Finished"

# @Redundancy
dump_all:
	@echo "dump"
	@echo "  - Starting"
	@fd --extension py . | xargs -I _ cat _ | hexdump -C | cat
	@echo "  - Finished"

# @Redundancy
od_all:
	@echo "dump"
	@echo "  - Starting"
	@fd --extension py . | xargs -I _ cat _ | od | cat
	@echo "  - Finished"

# Notes
#---------------------------------------------------------------

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
