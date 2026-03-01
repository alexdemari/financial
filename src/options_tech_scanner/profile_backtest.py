import cProfile
import pstats

from options_tech_scanner.backtest import run_backtest


def main():
    run_backtest(data_dir="data", lookahead=30)


if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()

    main()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumtime").print_stats(30)
