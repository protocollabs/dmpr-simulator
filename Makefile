# What to consider partial and what full for density_size plots
INTERVAL_PARTIAL = 11
INTERVAL_FULL = 0

# Choose python interpreter, prefer pypy
PY = python3 -W ignore::UserWarning
PYPY = $$(which pypy3 || which python3) -W ignore::UserWarning
SH = $$(which bash || which sh)

# The directory which should contain the message_size output
msg_dir = run-data/message_sizes_old
result_dir = $(msg_dir)_results
# All configurations (size-density-loss-interval)
all_dirs = $(wildcard $(msg_dir)/*-*-*-*/)
# The files with message lengths for all configurations
all_len = $(all_dirs:/=/len)
all_len_zlib = $(all_dirs:/=/len-zlib)
all_len_lzma = $(all_dirs:/=/len-lzma)

# helpers
process_msg = $(PYPY) -m analyze.process_messages
acc_by_density_size = $(SH) analyze/message_size_plots/acc_by_density_size.sh $(msg_dir) $(result_dir)
plot_size_density = $(PY) -m analyze.message_size_plots.density_size_plots $(result_dir)

# default catcher
default:

# Plot all available plots
msg_size_plots: plot_by_density_size_uncompressed plot_by_density_size_zlib

# Clean all plots
clean_plots:
	rm -rf $(result_dir)

# generate all uncompressed density-size plots
plot_by_density_size_uncompressed: $(all_len)
	$(acc_by_density_size) $(INTERVAL_PARTIAL)
	$(plot_size_density) -o $(result_dir)/density-partial
	$(acc_by_density_size) $(INTERVAL_FULL)
	$(plot_size_density) -o $(result_dir)/density-full

# plot all zlib density-size plots
plot_by_density_size_zlib: $(all_len_zlib)
	$(acc_by_density_size) $(INTERVAL_PARTIAL) -zlib
	$(plot_size_density) -o $(result_dir)/density-partial-zlib
	$(acc_by_density_size) $(INTERVAL_FULL) -zlib
	$(plot_size_density) -o $(result_dir)/density-full-zlib

# plot all zlib density-size plots
plot_by_density_size_lzma: $(all_len_lzma)
	$(acc_by_density_size) $(INTERVAL_PARTIAL) -lzma
	$(plot_size_density) -o $(result_dir)/density-partial-lzma
	$(acc_by_density_size) $(INTERVAL_FULL) -lzma
	$(plot_size_density) -o $(result_dir)/density-full-lzma

# Compute the message lengths for each configuration
$(all_len):
	$(process_msg) -a len -o $@ $$(dirname $@)/routers/*/trace/tx.msg

# Compute the zlib-ed message lengths for each configuration
$(all_len_zlib):
	$(process_msg) -a len-zlib -o $@ $$(dirname $@)/routers/*/trace/tx.msg

# Compute the lzma-ed message lengths for each configuration
$(all_len_lzma):
	$(process_msg) -a len-lzma -o $@ $$(dirname $@)/routers/*/trace/tx.msg

# Start the scenario, this takes several hours and requires at least 16 GB RAM
START_SIZE_COMBINATIONS_SZENARIO_WARNING_TAKES_HOURS:
	$(PY) -m scenarios.msg_size_combinations

.PHONY: mrproper msg_size_plots plot_by_density_size_uncompressed clean_plots \
		plot_by_density_size_zlib default \
		START_SIZE_COMBINATIONS_SZENARIO_WARNING_TAKES_HOURS
