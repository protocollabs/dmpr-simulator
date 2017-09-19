PY=python3
RUN_PY=$(PY) dmpr-simulator
RM=rm -rf

RESULTS=results
SCENARIOS=results/.scenarios

msg_size=001-message-size
dis_node=002-disappearing-node
profile=003-profile-core
self_check=004-self-test
random=005-random-network

help:
	@echo "Options:"
	@echo "	make all:	run all analyze scripts. WARNING: takes a looong time"
	@echo "	make fast:	just run the fast scripts, takes only a few minutes"
	@echo "	make slow:	just run the slow scripts"
	@echo "	make clean:	Clean all results"
	@echo "	make clean_fast:	Clean the results from the fast scripts"
	@echo "	make clean_slow:	Clean the results from the slow scripts"

all: fast slow

fast:
	$(RUN_PY) $(dis_node) --enable-video --enable-images --simulate-forwarding --sequence-diagram
	$(RUN_PY) $(profile)
	$(RUN_PY) $(random) --enable-video --simulate-forwarding

slow:
	$(RUN_PY) $(msg_size) --disable-logfiles

clean: clean_fast clean_slow

clean_fast:
	$(RM) $(RESULTS)/$(dis_node)
	$(RM) $(SCENARIOS)/$(dis_node)
	$(RM) $(RESULTS)/$(profile)
	$(RM) $(SCENARIOS)/$(profile)
	$(RM) $(RESULTS)/$(random)
	$(RM) $(SCENARIOS)/$(random)

clean_slow:
	$(RM) $(RESULTS)/$(msg_size)
	$(RM) $(SCENARIOS)/$(msg_size)

check:
	$(RUN_PY) $(self_check) --quiet --disable-logfiles

.PHONY: help all fast slow clean clean_fast clean_slow check
