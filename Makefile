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
promo=006-promotion-video

help:
	@echo "Options:"
	@echo "	make all:            Run all analyze scripts. WARNING: takes a looong time"
	@echo "	make fast-run:       just run the fast scripts, takes only a few minutes"
	@echo "	make long-run:       just run the long scripts"
	@echo "	make clean:          Clean all results"
	@echo "	make clean-fast-run: Clean the results from the fast scripts"
	@echo "	make clean-long-run: Clean the results from the long scripts"

all: fast-run long-run promotion-video

fast-run:
	$(RUN_PY) $(dis_node) --enable-video --enable-images --simulate-forwarding --sequence-diagram
	$(RUN_PY) $(profile)
	$(RUN_PY) $(random) --enable-video --simulate-forwarding

long-run:
	$(RUN_PY) $(msg_size) --disable-logfiles

promotion-video:
	$(RUN_PY) $(promo) --enable-video --simulate-forwarding --resolution hd

clean: clean-fast-run clean-long-run clean-promotion

clean-fast-run:
	$(RM) $(RESULTS)/$(dis_node)
	$(RM) $(SCENARIOS)/$(dis_node)
	$(RM) $(RESULTS)/$(profile)
	$(RM) $(SCENARIOS)/$(profile)
	$(RM) $(RESULTS)/$(random)
	$(RM) $(SCENARIOS)/$(random)

clean-long-run:
	$(RM) $(RESULTS)/$(msg_size)
	$(RM) $(SCENARIOS)/$(msg_size)

clean-promotion-video:
	$(RM) $(RESULTS)/$(promo)
	$(RM) $(SCENARIOS)/$(promo)

install-deps:
	sudo apt-get install libffi-dev
	pip3 install -r requirements.txt

check:
	$(RUN_PY) $(self_check) --quiet --disable-logfiles

distclean:
	git clean -f -X -d

test:
	$(PY) -m pytest tests/

.PHONY: help all fast-run long-rung clean clean-fast-run clean-long-run install-deps distclean test promotion-video clean-promotion-video
