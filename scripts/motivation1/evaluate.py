import os
import tarfile
import shutil
import sys
from datetime import datetime
from natsort import natsorted
import pandas as pd
from index_mapping import index_to_name

def create_evaluation_folder():
    evaluation_dir = os.path.join(os.getcwd(), 'evaluation')
    os.makedirs(evaluation_dir, exist_ok=True)
    return evaluation_dir

def remove_and_create_date_folder(date_dir):
    if os.path.exists(date_dir):
        shutil.rmtree(date_dir)
    os.makedirs(date_dir, exist_ok=True)

def extract_and_categorize_tar(file_path, output_dir):
    try:
        with tarfile.open(file_path, 'r:gz') as tar:
            tar.extractall(path=output_dir)

        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.log'):
                    parts = file.split('_')
                    try:
                        policy_name = next('_'.join(parts[i + 1:j]) for i, part in enumerate(parts) if part == 'SCENARIO' for j in range(i + 1, len(parts)) if 'DEVICES' in parts[j])
                        category_name = next('_'.join(parts[j + 1:]).replace('.log', '') for j in range(len(parts)) if 'DEVICES' in parts[j])
                        policy_dir = os.path.join(output_dir, policy_name)
                        os.makedirs(policy_dir, exist_ok=True)
                        category_dir = os.path.join(policy_dir, category_name)
                        os.makedirs(category_dir, exist_ok=True)
                        shutil.move(os.path.join(root, file), os.path.join(category_dir, file))
                    except StopIteration:
                        pass
    except Exception as e:
        print(f"Error extracting tar file {file_path}: {e}")

def copy_and_extract_files(base_dir, date_dir):
    if not os.path.exists(base_dir):
        return []

    ite_dirs = []

    for file_name in os.listdir(base_dir):
        if file_name.endswith('.tar.gz') or file_name.endswith('.log'):
            ite_name = file_name.split('.')[0]  # Extract the name without extension
            ite_dir = os.path.join(date_dir, ite_name)
            os.makedirs(ite_dir, exist_ok=True)
            ite_dirs.append(ite_dir)
            full_file_name = os.path.join(base_dir, file_name)
            shutil.copy(full_file_name, ite_dir)

            if file_name.endswith('.tar.gz'):
                extract_and_categorize_tar(os.path.join(ite_dir, file_name), ite_dir)

    return ite_dirs

def remove_nested_ite_folders(ite_dirs):
    for ite_dir in ite_dirs:
        nested_ite_dir = os.path.join(ite_dir, os.path.basename(ite_dir))
        if os.path.exists(nested_ite_dir):
            shutil.rmtree(nested_ite_dir)

def remove_progress_folder(date_dir):
    progress_dir = os.path.join(date_dir, 'progress')
    if os.path.exists(progress_dir):
        shutil.rmtree(progress_dir)

def read_logs(date_evaluation_dir):
    log_data = {}
    total_logs = 0
    unique_policies = set()
    unique_categories = set()

    for ite_dir in os.listdir(date_evaluation_dir):
        ite_path = os.path.join(date_evaluation_dir, ite_dir)
        if os.path.isdir(ite_path):
            log_data[ite_dir] = {}
            for policy_name in os.listdir(ite_path):
                policy_path = os.path.join(ite_path, policy_name)
                if os.path.isdir(policy_path):
                    log_data[ite_dir][policy_name] = {}
                    unique_policies.add(policy_name)
                    for category_name in os.listdir(policy_path):
                        category_path = os.path.join(policy_path, category_name)
                        if os.path.isdir(category_path):
                            log_files = {}
                            unique_categories.add(category_name)
                            for log_file in natsorted(os.listdir(category_path)):
                                if log_file.endswith('.log'):
                                    log_file_path = os.path.join(category_path, log_file)
                                    try:
                                        with open(log_file_path, 'r') as lf:
                                            log_files[log_file] = [line.strip() for line in lf.readlines()[1:]]  # Skip the first line
                                            total_logs += 1
                                    except Exception as e:
                                        print(f"Error reading log file {log_file_path}: {e}")
                            log_data[ite_dir][policy_name][category_name] = log_files

    total_ites = len(log_data)
    total_unique_policies = len(unique_policies)
    total_unique_categories = len(unique_categories)
    
    print("\n--- Log Reading Finished ---")
    print(f"Total ITEs processed: {total_ites}")
    print(f"Unique Policies processed: {total_unique_policies}")
    print(f"Unique Categories processed: {total_unique_categories}")
    print(f"Total log files read: {total_logs}")
    print("\n" + "-"*50 + "\n")
    
    return log_data

def process_files_by_date(base_path, date_str):
    try:
        date = datetime.strptime(date_str, '%d-%m-%Y_%H-%M')
        date_dir_name = date.strftime('%d-%m-%Y_%H-%M')
        base_dir = os.path.join(base_path, date_dir_name, 'default_config')
        evaluation_dir = create_evaluation_folder()
        date_evaluation_dir = os.path.join(evaluation_dir, date_dir_name)
        
        remove_and_create_date_folder(date_evaluation_dir)
        ite_dirs = copy_and_extract_files(base_dir, date_evaluation_dir)
        remove_nested_ite_folders(ite_dirs)
        remove_progress_folder(date_evaluation_dir)

        log_data = read_logs(date_evaluation_dir)
        return log_data

    except ValueError as e:
        print(f"Invalid date format. Please use DD-MM-YYYY_HH-MM. Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def select_option(options, option_name):
    options = natsorted(options)
    for idx, option in enumerate(options):
        print(f"{idx + 1}. {option}")
    while True:
        try:
            selection = int(input(f"Select {option_name} by number: ")) - 1
            if 0 <= selection < len(options):
                return options[selection]
            else:
                print(f"Invalid {option_name} number. Try again.")
        except ValueError:
            print(f"Please enter a valid number for {option_name}.")

def print_log_line(line, index):
    items = line.split(';')
    for item_idx, item in enumerate(items):
        name = index_to_name.get(index, "")
        print(f"{index}: {name}: {item.strip()}")
        index += 1
    return index

def parse_log_to_df(log_lines, ite, policy_name, devices, category):
    data = {'ite': ite, 'policy_name': policy_name, 'devices': devices, 'category': category}
    index = 0
    for line in log_lines:
        items = line.split(';')
        for item_idx, item in enumerate(items):
            name = index_to_name.get(index, "")
            if name:
                data[name] = item.strip()
            index += 1
    return pd.DataFrame([data])

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            print(f"Usage: python3 {sys.argv[0]} <date_time>")
            print(f"Example: python3 {sys.argv[0]} 15-06-2024_19-11")
        else:
            input_date = sys.argv[1]
            base_path = "output"  # Base path where the dated directories are located
            log_data = process_files_by_date(base_path, input_date)

            # Initialize an empty DataFrame to store all logs
            all_logs_df = pd.DataFrame()

            # Loop through and print log data based on user input
            while True:
                print("\n" + "-"*50 + "\n")
                ite_keys = list(log_data.keys())
                print("Available ITEs:")
                ite = select_option(ite_keys, "ITE")
                
                print("\n" + "-"*50 + "\n")
                policy_keys = list(log_data[ite].keys())
                print("Available Policies:")
                policy = select_option(policy_keys, "Policy")
                
                print("\n" + "-"*50 + "\n")
                category_keys = list(log_data[ite][policy].keys())
                print("Available Categories:")
                category = select_option(category_keys, "Category")
                
                print("\n" + "-"*50 + "\n")
                print(f"\n--- Logs for {category} in {policy} of {ite} ---")

                for log_file, log_lines in log_data[ite][policy][category].items():
                    print(f"\n--- {log_file} ---")
                    index = 0  # Initialize the index counter for each log file
                    for line in log_lines:
                        index = print_log_line(line, index)
                    
                    # Extract devices count from log file name
                    devices = [part.replace('DEVICES', '') for part in log_file.split('_') if 'DEVICES' in part][0]
                    log_df = parse_log_to_df(log_lines, ite, policy, devices, category)
                    all_logs_df = pd.concat([all_logs_df, log_df], ignore_index=True)
                
                exit_choice = input("Press 'q' to exit or 'w' to continue: ").lower()
                if exit_choice == 'q':
                    # Save the DataFrame to a CSV file
                    all_logs_df.to_csv('evaluation_logs.csv', index=False)
                    break
            
            print("\n--- Process Finished ---")
            print(all_logs_df)

    except KeyboardInterrupt:
        print("\n--- Exit ---")
