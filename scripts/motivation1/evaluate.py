import os
import tarfile
import shutil
import sys
from datetime import datetime

def create_evaluation_folder():
    """
    Creates an 'evaluation' folder in the current directory if it doesn't exist.
    """
    evaluation_dir = os.path.join(os.getcwd(), 'evaluation')
    os.makedirs(evaluation_dir, exist_ok=True)
    return evaluation_dir

def remove_existing_date_folder(date_dir):
    """
    Removes the existing date folder if it exists.
    
    :param date_dir: Directory where the date folder is located
    """
    if os.path.exists(date_dir):
        shutil.rmtree(date_dir)
        print(f"Removed existing date folder: {date_dir}")

def extract_tar_gz(file_path, output_dir):
    """
    Extracts a tar.gz file to the specified output directory.
    
    :param file_path: Path to the tar.gz file
    :param output_dir: Directory to extract the contents to
    """
    os.makedirs(output_dir, exist_ok=True)
    with tarfile.open(file_path, 'r:gz') as tar:
        tar.extractall(path=output_dir)
    print(f"Extracted {file_path} to {output_dir}")

def move_log_files(output_dir):
    """
    Moves and categorizes log files in the specified output directory.
    
    :param output_dir: Directory where the logs are located
    """
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.log'):
                log_file_path = os.path.join(root, file)
                parts = file.split('_')
                if len(parts) >= 6:
                    policy_parts = parts[2:]
                    for i, part in enumerate(policy_parts):
                        if 'DEVICES' in part:
                            policy_name = '_'.join(policy_parts[:i])
                            break
                    policy_name = policy_name.replace('SCENARIO_', '')
                    policy_dir = os.path.join(output_dir, policy_name)
                    os.makedirs(policy_dir, exist_ok=True)
                    shutil.move(log_file_path, policy_dir)

def remove_empty_ite_folder(output_dir):
    """
    Removes the ite1 folder if it exists and is empty.
    
    :param output_dir: Directory where the ite1 folder is located
    """
    ite_folder = os.path.join(output_dir, 'ite1')
    if os.path.exists(ite_folder):
        for root, _, files in os.walk(ite_folder):
            for file in files:
                shutil.move(os.path.join(root, file), output_dir)
        shutil.rmtree(ite_folder)
        print(f"Removed empty ite1 folder: {ite_folder}")

def process_tar_files_by_date(base_path, date_str):
    """
    Extracts all tar.gz files and copies log files corresponding to the provided date into a single ite1 folder.
    
    :param base_path: Base path where the tar.gz files are located
    :param date_str: Date string in the format DD-MM-YYYY_HH-MM
    """
    try:
        date = datetime.strptime(date_str, '%d-%m-%Y_%H-%M')
        date_dir_name = date.strftime('%d-%m-%Y_%H-%M')
        date_dir = os.path.join("evaluation", date_dir_name)
        base_dir = os.path.join(base_path, date_dir_name, 'default_config')
        
        if not os.path.exists(base_dir):
            print(f"Directory {base_dir} does not exist.")
            return
        
        evaluation_dir = create_evaluation_folder()
        output_dir = os.path.join(evaluation_dir, date_dir_name, 'ite1')
        
        remove_existing_date_folder(os.path.join(evaluation_dir, date_dir_name))
        os.makedirs(output_dir, exist_ok=True)

        times = 1
        while True:
            tar_file_name = f"ite{times}.tar.gz"
            log_file_name = f"ite{times}.log"
            tar_file_path = os.path.join(base_dir, tar_file_name)
            log_file_path = os.path.join(base_dir, log_file_name)

            if not os.path.exists(tar_file_path) and not os.path.exists(log_file_path):
                break

            if os.path.exists(tar_file_path):
                extract_tar_gz(tar_file_path, output_dir)

            if os.path.exists(log_file_path):
                shutil.copy(log_file_path, output_dir)
            
            times += 1

        if times == 1:
            print("No ite{times}.tar.gz or ite{times}.log files found in the directory.")
        
        move_log_files(output_dir)
        remove_empty_ite_folder(output_dir)

    except ValueError:
        print("Invalid date format. Please use DD-MM-YYYY_HH-MM.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <date_time>")
        print(f"Example: python3 {sys.argv[0]} 15-06-2024_19-11")
    else:
        input_date = sys.argv[1]
        base_path = "output"  # Base path where the dated directories are located
        process_tar_files_by_date(base_path, input_date)
        print("All process finished")
