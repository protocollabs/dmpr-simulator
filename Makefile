# What to consider partial and what full for density_size plots
INTERVAL_PARTIAL = 11
INTERVAL_FULL = 0

# Choose python interpreter, prefer pypy
PY = python3 -W ignore::UserWarning
PYPY = $$(which pypy3 || which python3) -W ignore::UserWarning

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
plot = $(PY) -m analyze.message_size_plots.msg_size_plots  --output $(result_dir)/graphs --input $(result_dir)
acc = $(PY) -m analyze.message_size_plots.accumulate_lengths --input $(msg_dir) --output $(result_dir)

acc_density_size = $(acc) --first density --second size
plot_density_size = $(plot) --chartgroup density --xaxis size
acc_loss_interval = $(acc) --first loss --second interval
plot_loss_interval = $(plot) --chartgroup loss --xaxis interval

# default catcher
default:

# Plot all available plots
msg_size_plots: msg_size_plots_uncompressed msg_size_plots_zlib msg_size_plots_lzma

# Clean all plots
clean_plots:
	rm -rf $(result_dir)

msg_size_plots_uncompressed: $(all_len)
	$(acc_density_size) --filename len
	$(plot_density_size)

	$(acc_loss_interval) --filename len
	$(plot_loss_interval)

msg_size_plots_zlib: $(all_len_zlib)
	$(acc_density_size) --filename len-zlib
	$(plot_density_size)

	$(acc_loss_interval) --filename len-zlib
	$(plot_loss_interval)

msg_size_plots_lzma: $(all_len_lzma)
	$(acc_density_size) --filename len-lzma
	$(plot_density_size)

	$(acc_loss_interval) --filename len-lzma
	$(plot_loss_interval)

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

.PHONY: msg_size_plots clean_plots msg_size_plots_lzma\
		default msg_size_plots_uncompressed msg_size_plots_zlib \
		START_SIZE_COMBINATIONS_SZENARIO_WARNING_TAKES_HOURS
