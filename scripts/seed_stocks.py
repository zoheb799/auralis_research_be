import sys


def main() -> None:
    print(
        "This demo seeder has been disabled because it deletes market data and "
        "writes synthetic values. Use scripts/sync_stock_fundamentals.py for "
        "source-backed data.",
        file=sys.stderr,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
