"""Apply the resource contract before user code; Python normally ignores site errors."""
try:
    from squidpy_policy import configure
    configure()
except Exception as error:
    raise SystemExit(f"squidpy: resource configuration failed: {error}") from error
