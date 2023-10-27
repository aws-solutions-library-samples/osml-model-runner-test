import argparse
from typing import Any, Dict, List

import boto3
import pandas as pd
from tabulate import tabulate


def get_combined_cost_data(start_time: str, end_time: str) -> pd.DataFrame:
    """
    Fetches AWS cost data for a specified time range and combines it into a DataFrame.

    :param start_time: Start time in ISO8601 format (e.g., '2023-10-20T09:00:00Z').
    :param end_time: End time in ISO8601 format (e.g., '2023-10-20T11:00:00Z').
    :return: A DataFrame containing cost data for the specified time range.
    """
    print("Getting cost data for {} to {}".format(start_time, end_time))
    session = boto3.Session(profile_name="default", region_name="us-west-2")  # Replace with your AWS profile name

    # AWS Cost Explorer client
    ce = session.client("ce")

    # Initialize an empty list to store data for all hours
    combined_data = []

    # Calculate the number of hours between start and end times
    num_hours = (pd.to_datetime(end_time) - pd.to_datetime(start_time)).total_seconds() / 3600

    # Iterate through each hour and fetch data
    for hour in range(int(num_hours) + 1):
        hour_start = pd.to_datetime(start_time) + pd.DateOffset(hours=hour)
        hour_end = hour_start + pd.DateOffset(hours=1)

        # Get an AWS cost and usage report with the service filter for the current hour
        response = ce.get_cost_and_usage(
            TimePeriod={"Start": hour_start.strftime("%Y-%m-%dT%H:%M:%SZ"), "End": hour_end.strftime("%Y-%m-%dT%H:%M:%SZ")},
            Granularity="HOURLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Append the data for the current hour to the combined data list
        combined_data += response["ResultsByTime"]

    # Create a DataFrame from the combined data
    df_list: List[Dict[str, Any]] = []

    # Initialize total cost
    total_cost = 0.0

    for period in combined_data:
        for group in period.get("Groups", []):
            service_name = group["Keys"][0]
            cost_amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            df_list.append({"Service": service_name, "Cost": cost_amount, "TimePeriod": period["TimePeriod"]["Start"]})
            total_cost += cost_amount  # Accumulate the total cost

    # Add a row for total cost
    df_list.append({"Service": "Total", "Cost": total_cost, "TimePeriod": "Total"})

    df = pd.DataFrame(df_list)
    return df


def main():
    """
    Fetches AWS cost data for a specified time range and combines it into a DataFrame for display.
    :return:
    """
    parser = argparse.ArgumentParser(description="Fetch AWS cost data for a specified time range.")
    parser.add_argument("start_time", help="Start time in ISO8601 format (e.g., 2023-10-20T09:00:00Z)")
    parser.add_argument("end_time", help="End time in ISO8601 format (e.g., 2023-10-20T11:00:00Z)")
    args = parser.parse_args()

    print("Please ensure that the cost explorer has been updated for the request time window!")

    # Get combined cost data for the specified time range
    df = get_combined_cost_data(args.start_time, args.end_time)

    # Create a pretty table for cost breakdown
    table = tabulate(df, headers="keys", tablefmt="fancy_grid")

    # Display the pretty table
    print(table)


if __name__ == "__main__":
    main()
