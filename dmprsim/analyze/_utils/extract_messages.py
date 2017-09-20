from pathlib import Path


def all_tracefiles(input_dirs, tracepoint) -> tuple:
    for dir in input_dirs:
        for router in (dir / 'routers').iterdir():
            tracefile = router / 'trace' / tracepoint
            yield router.name, tracefile


def extract_messages(tracefile: Path) -> list:
    messages = []
    try:
        with tracefile.open() as f:
            for line in f:
                time = line.split()[0]
                msg = ' '.join(line.split()[1:])
                messages.append((time, msg))
    except FileNotFoundError:
        pass
    return messages
