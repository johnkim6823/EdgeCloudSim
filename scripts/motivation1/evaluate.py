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
                    policy_name = next(('_'.join(parts[i + 1:j]) for i, part in enumerate(parts) if part == 'SCENARIO' for j in range(i + 1, len(parts)) if 'DEVICES' in parts[j]), None)
                    category_name = next(('_'.join(parts[j + 1:]).replace('.log', '') for j in range(len(parts)) if 'DEVICES' in parts[j]), None)
                    if policy_name and category_name:
                        policy_dir = os.path.join(output_dir, policy_name)
                        category_dir = os.path.join(policy_dir, category_name)
                        os.makedirs(category_dir, exist_ok=True)
                        shutil.move(os.path.join(root, file), os.path.join(category_dir, file))
    except Exception as e:
        print(f"Error extracting tar file {file_path}: {e}")

def copy_and_extract_files(base_dir, date_dir):
    ite_dirs = []

    for file_name in os.listdir(base_dir):
        if file_name.endswith(('.tar.gz', '.log')):
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

def convert_logs_to_single_line(log_file_path):
    try:
        with open(log_file_path, 'r') as lf:
            lines = [line.strip() for line in lf.readlines()]
        if len(lines) > 1:
            single_line = ";".join(lines[1:])  # Combine all lines after the header
            with open(log_file_path, 'w') as lf:
                lf.write(single_line)
    except Exception as e:
        print(f"Error converting log file {log_file_path} to single line: {e}")

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
                                    convert_logs_to_single_line(log_file_path)
                                    try:
                                        with open(log_file_path, 'r') as lf:
                                            log_files[log_file] = [line.strip() for line in lf.readlines()]
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
    print(f"0. Process all {option_name.lower()}")
    for idx, option in enumerate(options):
        print(f"{idx + 1}. {option}")
    while True:
        try:
            selection = int(input(f"Select {option_name} by number: ")) - 1
            if selection == -1:
                return 'ALL'
            elif 0 <= selection < len(options):
                return options[selection]
            else:
                print(f"Invalid {option_name} number. Try again.")
        except ValueError:
            print(f"Please enter a valid number for {option_name}.")

def print_log_line(line, data, ite, policy_name, devices, category):
    items = line.split(';')
    data['ite'].append(ite)
    data['policy_name'].append(policy_name)
    data['devices'].append(devices)
    data['category'].append(category)
    index = 0
    for item in items:
        name = index_to_name.get(index)
        data[name].append(item)
        print(f"{index}. {name}: {item}")   
        index += 1
    

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
            data = {key: [] for key in ['ite', 'policy_name', 'devices', 'category'] + list(index_to_name.values())}
            print(len(data))
            ite_keys = natsorted(list(log_data.keys()))
            print("\n" + "-"*50 + "\n")
            print("Available ITEs:")
            ite_selection = select_option(ite_keys, "ITE")

            if ite_selection == 'ALL':
                selected_ites = ite_keys
                ite_part = 'all_ites'
            else:
                selected_ites = [ite_selection]
                ite_part = ite_selection

            policy_keys = natsorted({policy for ite in selected_ites for policy in log_data.get(ite, {}).keys()})
            print("\n" + "-"*50 + "\n")
            print("Available Policies:")
            policy_selection = select_option(policy_keys, "Policies")

            if policy_selection == 'ALL':
                selected_policies = policy_keys
                policy_part = 'all_policies'
            else:
                selected_policies = [policy_selection]
                policy_part = policy_selection

            category_keys = natsorted({category for ite in selected_ites for policy in selected_policies for category in log_data.get(ite, {}).get(policy, {}).keys()})
            print("\n" + "-"*50 + "\n")
            print("Available Categories:")
            category_selection = select_option(category_keys, "Categories")

            if category_selection == 'ALL':
                selected_categories = category_keys
                category_part = 'all_categories'
            else:
                selected_categories = [category_selection]
                category_part = category_selection

            for ite in selected_ites:
                for policy in selected_policies:
                    for category in selected_categories:
                        if category in log_data[ite].get(policy, {}):
                            print(f"\n--- Logs for {category} in {policy} of {ite} ---")

                            for log_file, log_lines in log_data[ite][policy][category].items():
                                print(f"\n--- {log_file} ---")
                                devices = [part.replace('DEVICES', '') for part in log_file.split('_') if 'DEVICES' in part][0]
                                print_log_line(log_lines[0], data, ite, policy, devices, category)

            df = pd.DataFrame(data)
            print(df.iloc[:, :10])  # 첫 10개의 열만 출력

            # CSV로 저장할지 여부를 묻는 부분 추가
            save_choice = input("Do you want to save the logs to CSV? (y/n): ").lower()
            if save_choice == 'y':
                file_name = f"{input_date}_logs_{ite_part}_{policy_part}_{category_part}.csv"
                df.to_csv(file_name, index=False)

    except KeyboardInterrupt:
        print("\n--- Exit ---")
