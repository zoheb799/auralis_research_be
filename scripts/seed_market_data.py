import sys


def main() -> None:
    print(
        "This demo seeder has been disabled because it deletes market data and "
        "writes synthetic values. Use the market-data sync endpoints instead.",
        file=sys.stderr,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
