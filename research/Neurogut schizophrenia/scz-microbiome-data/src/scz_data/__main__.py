from scz_data.cli import main

# Guard needed: download workers are spawned processes that re-import this module (Windows "spawn").
if __name__ == "__main__":
    raise SystemExit(main())
