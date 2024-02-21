import requests
import time
from datetime import datetime, timedelta
import subprocess

def count_blocks_mined():
    # Run the grep command and capture its output
    grep_process = subprocess.Popen(["grep", "execute_state_transition", "/var/log/rusk.log"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = grep_process.communicate()

    # Count the number of lines returned by the grep command
    num_lines = len(output.decode().split('\n'))

    # Check if the number of lines increased since the last call
    if hasattr(count_blocks_mined, 'last_count'):
        if num_lines > count_blocks_mined.last_count:
            print("####### BLOCK MINED! #######")

    # Update the last count value
    count_blocks_mined.last_count = num_lines

    return num_lines


def get_current_local_height():
    response = requests.post(
        'http://127.0.0.1:8080/02/Chain',
        headers={'Rusk-Version': '0.7.0-rc', 'Content-Type': 'application/json'},
        json={"topic": "gql", "data": "query { block(height: -1) { header { height } } }"}
    )
    return response.json()['block']['header']['height']

def get_global_height():
    response = requests.get('https://api.dusk.network/v1/latest?node=nodes.dusk.network', timeout=2)
    return response.json()['data']['blocks'][0]['header']['height']

def get_global_height_safe(): #this needs a thread
    while True:
        try:
            global_height = get_global_height()
            return global_height, datetime.now()
        except requests.exceptions.Timeout:
            print("Global node request timed out, retrying...")
            time.sleep(10)

def calculate_block_increase(local_heights, interval, current_height):
    if len(local_heights[interval]) >= 2:
        return current_height - local_heights[interval][-2]
    return 0

def format_timedelta(td):
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days} days")
    if hours:
        parts.append(f"{hours} hours")
    if minutes:
        parts.append(f"{minutes} minutes")
    if seconds:
        parts.append(f"{seconds} seconds")

    return ", ".join(parts)

def main():
    intervals = [1, 5, 15, 30, 60]  # Minutes
    local_heights = {interval: [] for interval in intervals}
    last_interval_check = {interval: datetime.now() for interval in intervals}

    # Get initial local and global heights
    local_height = get_current_local_height()
    global_height, last_global_check = get_global_height_safe()

    while True:
        current_time = datetime.now()

        # Update local heights for each interval
        for interval in intervals:
            time_since_last_interval_check = (current_time - last_interval_check[interval]).total_seconds()
            if time_since_last_interval_check >= interval * 60 or not local_heights[interval]:
                local_heights[interval].append(local_height)
                if len(local_heights[interval]) > 2:
                    local_heights[interval].pop(0)  # Keep only the last two records
                last_interval_check[interval] = current_time  # Update the last check time for this interval

        # Update global height every 5 minutes
        if (current_time - last_global_check).total_seconds() >= 300:
            global_height, last_global_check = get_global_height_safe()
        age = datetime.now() - last_global_check
        age_text = "Now" if age.total_seconds() < 1 else format_timedelta(age)

        # Update local height for the next iteration
        local_height = get_current_local_height()

        # Display results in table format
        print("-----------------------------")
        print("\nCurrent Local Height:", local_height)
        print(f"Current Global Height: {global_height} (Age: {age_text})")
        print("Blocks Mined:", count_blocks_mined())
        print("\n-----------------------------")
        print("\nBlock Increase Over Time:")
        print("Interval (min)\tBlocks Increased")
        for interval in intervals:
            blocks_increased = calculate_block_increase(local_heights, interval, local_height)
            print(f"{interval}\t\t{blocks_increased}")

        # Calculate estimated catch-up time using the largest available interval
        estimated_catch_up_time = None
        for interval in reversed(intervals):
            blocks_behind = global_height - local_height
            blocks_per_interval = calculate_block_increase(local_heights, interval, local_height)
            if blocks_per_interval > 0:
                time_per_block = interval * 60 / blocks_per_interval
                total_time_seconds = time_per_block * blocks_behind
                estimated_catch_up_time = timedelta(seconds=total_time_seconds)
                break

        if estimated_catch_up_time:
            # Check if the estimated catch-up time is negative or zero
            if estimated_catch_up_time.total_seconds() <= 0:
                print("\nEstimated Time to Catch Up: SYNCED!")
            else:
                print("\nEstimated Time to Catch Up:", format_timedelta(estimated_catch_up_time))

        time.sleep(60)  # Wait for 1 minute before next check

if __name__ == "__main__":
    main()
