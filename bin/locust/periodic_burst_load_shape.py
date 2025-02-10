import math
from typing import Optional, Tuple

from locust import LoadTestShape, events


@events.init_command_line_parser.add_listener
def add_custom_arguments(parser) -> None:
    """
    Add custom command line arguments for periodic burst load shape.

    :param parser: ArgumentParser instance to add arguments to
    """
    parser.add_argument(
        "--pbls-repeat-period", type=int, default=600, help="PeriodicBurstLoadShape: Repeat cycle in seconds"
    )
    parser.add_argument(
        "--pbls-min-concurrency", type=int, default=5, help="PeriodicBurstLoadShape: Minimum number of users"
    )
    parser.add_argument("--pbls-peak-concurrency", type=int, default=40, help="PeriodicBurstLoadShape: Peak number of users")
    parser.add_argument(
        "--pbls-peak-std", type=int, default=None, help="PeriodicBurstLoadShape: Peak standard deviation in seconds"
    )
    parser.add_argument("--pbls-peak-mean", type=int, default=None, help="PeriodicBurstLoadShape: Mean in seconds")


class PeriodicBurstLoadTestShape(LoadTestShape):
    """
    Custom load shape that generates periodic bursts of load.

    Alternates between periods of high load (bursts) and low load (rest periods).
    Maintains a minimum number of users with periodic bursts up to a peak number.
    The bursts follow a normal distribution pattern, with configurable timing.
    """

    def __init__(self):
        super().__init__()

    def tick(self) -> Optional[Tuple[int, float]]:
        """
        Calculate the target user count and spawn rate for the current time.

        :return: Tuple of (user_count, spawn_rate) or None to stop the test
        """
        if self.runner is None:
            return None

        run_time = round(self.get_run_time())
        return self.calculate_load_at_time(run_time)

    def calculate_load_at_time(self, run_time) -> Optional[Tuple[int, float]]:
        """
        Calculate the number of users at a specific point in time.

        :param run_time: The current time in seconds since the test started
        :return: a Tuple of [# users, user spawn rate]
        """

        # Need to access these values here because the runner does not get setup during
        # initialization. It gets attached later after the load test shape has been
        # created. See: https://github.com/locustio/locust/blob/master/locust/env.py#L122
        repeat_period = self.runner.environment.parsed_options.pbls_repeat_period
        min_concurrency = self.runner.environment.parsed_options.pbls_min_concurrency
        peak_concurrency = self.runner.environment.parsed_options.pbls_peak_concurrency
        peak_mean = self.runner.environment.parsed_options.pbls_peak_mean
        peak_std = self.runner.environment.parsed_options.pbls_peak_std
        if peak_mean is None:
            peak_mean = repeat_period / 2
        if peak_std is None:
            peak_std = repeat_period / 10

        # This causes the load pattern to repeat every repeat_period seconds.
        relative_time = run_time % repeat_period

        # This computes the number of concurrent users at this instance in time.
        # The load will always have min_concurrency users, but it will occasionally
        # burst to peak_concurrency once per repeat cycle. The location of that
        # burst is at the peak_mean and the peak_std controls how much of
        # a ramp up/down occurs.
        z = (relative_time - peak_mean) / peak_std
        user_count = (peak_concurrency - min_concurrency) * math.e ** -(math.pi * z**2) + min_concurrency
        return round(user_count), round(user_count)
