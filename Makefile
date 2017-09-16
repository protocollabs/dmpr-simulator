PY=python3
RUN_PY=$(PY) dmpr-simulator

RESULTS=results
SCENARIOS=results/.scenarios

msg_size=001-message-size
dis_node=002-disappearing-node
profile=003-profile-core


help:
	@echo "Options:"
	@echo "	make all:	run all analyze scripts. WARNING: takes a looong time"
	@echo "	make fast:	just run the some fast scripts, takes only some minutes"
	@echo "	make slow:	just run the slow scripts"
	@echo "	make clean:	Clean all results"
	@echo "	make clean_fast:	Clean the results from the fast scripts"
	@echo "	make clean_slow:	Clean the results from the slow scripts"

all: fast slow

fast:
	$(RUN_PY) $(dis_node) --enable-video --enable-images --simulate-forwarding --sequence-diagram
	$(RUN_PY) $(profile)

slow:
	$(RUN_PY) $(msg_size)

clean: clean_fast clean_slow

clean_fast:
	rm -r $(RESULTS)/$(dis_node)
	rm -r $(SCENARIOS)/$(dis_node)
	rm -r $(RESULTS)/$(profile)
	rm -r $(SCENARIOS)/$(profile)

clean_slow:
	rm -r $(RESULTS)/$(msg_size)
	rm -r $(SCENARIOS)/$(msg_size)

.PHONY: help all fast slow clean clean_fast clean_slow
