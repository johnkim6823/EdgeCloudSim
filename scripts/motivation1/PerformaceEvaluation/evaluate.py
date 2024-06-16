import os
import tarfile
import shutil
from datetime import datetime

def extract_tar_gz(file_path, output_dir):
    """
    Extracts a tar.gz file to the specified output directory and removes redundant nested directories.
    
    :param file_path: Path to the tar.gz file
    :param output_dir: Directory to extract the contents to
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    with tarfile.open(file_path, 'r:gz') as tar:
        tar.extractall(path=output_dir)
        print(f"Extracted {file_path} to {output_dir}")
    
    # Check if there's a redundant nested directory
    for root, dirs, files in os.walk(output_dir):
        if len(dirs) == 1 and not files and dirs[0].startswith("ite"):
            nested_dir = os.path.join(root, dirs[0])
            for nested_root, nested_dirs, nested_files in os.walk(nested_dir):
                for file in nested_files:
                    shutil.move(os.path.join(nested_root, file), output_dir)
                for nested_dir in nested_dirs:
                    shutil.move(os.path.join(nested_root, nested_dir), output_dir)
            shutil.rmtree(nested_dir)
            break

def process_tar_files_by_date(base_path, date_str):
    """
    Extracts all tar.gz files corresponding to the provided date.
    
    :param base_path: Base path where the tar.gz files are located
    :param date_str: Date string in the format DD-MM-YYYY_HH-MM
    """
    try:
        date = datetime.strptime(date_str, '%d-%m-%Y_%H-%M')
        date_dir = date.strftime('%d-%m-%Y_%H-%M')
        base_dir = os.path.join(base_path, date_dir, 'default_config')
        
        if not os.path.exists(base_dir):
            print(f"Directory {base_dir} does not exist.")
            return
        
        times = 1
        while True:
            file_name = f"ite{times}.tar.gz"
            file_path = os.path.join(base_dir, file_name)
            if not os.path.exists(file_path):
                break
            output_dir = os.path.join(os.getcwd(), date_dir, f'ite{times}')
            extract_tar_gz(file_path, output_dir)
            times += 1

        if times == 1:
            print("No ite{times}.tar.gz files found in the directory.")
            
    except ValueError:
        print("Invalid date format. Please use DD-MM-YYYY_HH-MM.")

# Example usage
base_path = "../output"  # Base path where the dated directories are located
input_date = '15-06-2024_19-09'  # Replace with the desired date input
process_tar_files_by_date(base_path, input_date)
