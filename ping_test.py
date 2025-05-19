import subprocess
import logging
import datetime
import os
from pathlib import Path
import re
from tqdm import tqdm
import time
from tabulate import tabulate
from colorama import Fore, Style
import random
import csv

def setup_logger(log_dir="logs"):
    """Set up a logger that writes to a date-named file."""
    # Create logs directory if it doesn't exist
    Path(log_dir).mkdir(exist_ok=True)
    
    # Generate filename based on current date
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"ping_stats_{today}.log")
    csv_file = os.path.join(log_dir, f"ping_stats_{today}.csv")
    
    # Configure logger
    logger = logging.getLogger("ping_statistics")
    logger.setLevel(logging.INFO)
    
    # Create file handler which logs even info messages
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # Create formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Add the handler to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, csv_file

# log_ping_data(logger, total, allowed, blocked, unreachable, avg_response_time)
def log_ping_data(logger, total, allowed, blocked, unreachable, avg_response_time):
    """Log a single ping data point."""
    logger.info(f"Total: {total}, Allowed: {allowed}, Blocked: {blocked}, Unreachable: {unreachable}, Response Time: {avg_response_time}")

def get_response_time(ping_output):
    # Extract all time values and convert to float
    times = [float(time) for time in re.findall(r'time=(\d+\.\d+) ms', ping_output)]
    times += [float(time) for time in re.findall(r'time=(\d+) ms', ping_output)]
    # Return average (or None if no times found)
    return sum(times) / len(times) if times else None

def ping_host(hostname, count=3):
    """
    Ping a host and return the output.
    
    Args:
        hostname: The hostname or IP address to ping
        count: Number of ping packets to send (default 4)
    
    Returns:
        The ping command output as a string
    """
    # For Windows
    if subprocess.os.name == 'nt':
        command = ['ping', '-n', str(count), hostname]
    # For Linux/Mac
    else:
        command = ['ping', '-c', str(count), hostname]
    
    try:
        # Run the command and capture output
        result = subprocess.run(command, 
                                capture_output=True, 
                                text=True, 
                                check=False)
        
        # Return the output
        return result.stdout, result.returncode, get_response_time(result.stdout)
    except Exception as e:
        return None, None, None

# 208.91.112.55 -- fortinet blocked IP
def is_allowed(website):
    ping_result, return_code, response_time = ping_host(website)
    if return_code == 0:
        if '208.91.112.55' in ping_result:
            return False, response_time
        else:
            return True, response_time
    # Not accessible by ping
    return None, response_time

if __name__ == "__main__":
    logger, csv_path = setup_logger()
    allowed, blocked, total, unreachable = 0, 0, 0, 0
    response_times, websites = [], []

    with open('allowed_websites.txt', 'r') as file:
        for line in file:
            websites += [[line.strip(), True]]
            
    # with open('blocked_websites.txt', 'r') as file:
    #     for line in file:
    #         websites += [[line.strip(), False]]
    
    random.shuffle(websites)

    cache = []
    for idx, website_data in enumerate(tqdm(websites)):
        total += 1
        website, expected_result = website_data[0], website_data[1]
        result, response_time = is_allowed(website)
        if idx % 5 == 0:
            if len(cache) >= 5:
                print(tabulate(cache[-5:]))
        else:
            result_text = ''
            if result is None:
                result_text = Fore.RED + 'UNREACHABLE' + Style.RESET_ALL
            elif result:
                result_text = 'ACCESSIBLE'
            elif not result:
                result_text = 'BLOCKED'
            if result == expected_result:
                result_text = Fore.GREEN + result_text + Style.RESET_ALL
            else:
                result_text = Fore.YELLOW + result_text + Style.RESET_ALL
            if response_time < 100:
                response_time_text = Fore.GREEN + f'{response_time:.2f} ms' + Style.RESET_ALL
            elif response_time > 300:
                response_time_text = Fore.YELLOW + f'{response_time:.2f} ms' + Style.RESET_ALL
            else:
                response_time_text = f'{response_time:.2f}'
            cache.append([website, result_text, response_time_text])
        if result is None:
            unreachable += 1
        else:
            if result:
                allowed += 1
            else:
                blocked += 1
        if response_time:
            response_times += [response_time]

    random.shuffle(cache)
    print(tabulate(cache))

    avg_response_time = sum(response_times) / len(response_times)
    log_ping_data(logger, total, allowed, blocked, unreachable, avg_response_time)
    with open(csv_path, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=' ',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow([total, allowed, blocked, unreachable, f'{avg_response_time:.2f}', f'{((allowed+blocked)/total)*100:.2f}'])

    status = Fore.RED  + 'UNAVAILABLE' + Style.RESET_ALL
    if total == allowed + blocked:
        status = Fore.GREEN + 'HEALTHY' + Style.RESET_ALL
    elif unreachable > 0 and unreachable != total:
        status = Fore.YELLOW + 'WARNING' + Style.RESET_ALL
    print(status, f'{((allowed+blocked)/total)*100:.2f}%')