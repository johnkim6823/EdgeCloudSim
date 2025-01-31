import os
import tarfile
import shutil
import sys
from datetime import datetime
from natsort import natsorted
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scienceplots

plt.style.use(['science', 'ieee', 'no-latex'])

# Add parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from index_mapping import all_apps_generic

###############################################################################
# Global folder name constants
###############################################################################
RESULTS_FOLDER_NAME = "results"  # The top-level folder that contains 'logs' and 'graph'
LOGS_SUBFOLDER_NAME = "logs"
GRAPH_SUBFOLDER_NAME = "graph"


###############################################################################
# 1. Select date folder
###############################################################################
def get_available_date_folders(base_path="output"):
    try:
        date_folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]
        if not date_folders:
            print("Error: No date folders found in /output.")
            sys.exit(1)
        return natsorted(date_folders)
    except Exception as e:
        print(f"Error: Unable to read /output directory: {e}")
        sys.exit(1)


def select_date_folder(date_folders):
    print("\nAvailable Date Folders:")
    print("-" * 50)
    print("0. (Auto) Use Latest Date")

    for idx, date in enumerate(date_folders, start=1):
        print(f"{idx}. {date}")

    print("-" * 50)

    while True:
        try:
            selection = int(input("Select a date by number: ")) - 1
            if selection == -1:
                return date_folders[-1]  # Automatically select the latest date
            elif 0 <= selection < len(date_folders):
                return date_folders[selection]
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a valid number.")


###############################################################################
# 2. Create 'logs' and 'graph' folders under the selected date folder
###############################################################################
def create_date_structure(selected_date):
    """
    Creates the following folder structure:
    results/<selected_date>/logs
    results/<selected_date>/graph
    If the logs/graph folder already exists, it is removed and recreated.
    """
    # Top-level 'results' folder
    results_dir = os.path.join(os.getcwd(), RESULTS_FOLDER_NAME)
    os.makedirs(results_dir, exist_ok=True)

    # Date folder, e.g., results/31-01-2025_01-00
    date_dir = os.path.join(results_dir, selected_date)
    os.makedirs(date_dir, exist_ok=True)  # We do not remove the date folder itself

    # logs folder: results/<selected_date>/logs
    logs_dir = os.path.join(date_dir, LOGS_SUBFOLDER_NAME)
    # graph folder: results/<selected_date>/graph
    graph_dir = os.path.join(date_dir, GRAPH_SUBFOLDER_NAME)

    # If needed, remove logs/graph folder and recreate
    if os.path.exists(logs_dir):
        shutil.rmtree(logs_dir)
    os.makedirs(logs_dir, exist_ok=True)

    if os.path.exists(graph_dir):
        shutil.rmtree(graph_dir)
    os.makedirs(graph_dir, exist_ok=True)

    return date_dir, logs_dir, graph_dir


def remove_progress_folder(date_logs_dir):
    """
    If there is a 'progress' folder, remove it.
    """
    progress_dir = os.path.join(date_logs_dir, 'progress')
    if os.path.exists(progress_dir):
        shutil.rmtree(progress_dir)


###############################################################################
# 3. Extract .tar.gz and categorize logs
###############################################################################
def extract_and_categorize_tar(file_path, output_dir):
    """
    Extracts a .tar.gz file into 'output_dir', then categorizes .log files
    by parsing their filenames to get policy_name and category_name.
    """
    try:
        with tarfile.open(file_path, 'r:gz') as tar:
            tar.extractall(path=output_dir)

        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.log'):
                    parts = file.split('_')
                    # Parse policy_name and category_name
                    policy_name = next((
                        '_'.join(parts[i + 1:j])
                        for i, part in enumerate(parts) if part == 'TIER'
                        for j in range(i + 1, len(parts)) if 'DEVICES' in parts[j]
                    ), None)
                    category_name = next((
                        '_'.join(parts[j + 1:]).replace('.log', '')
                        for j in range(len(parts)) if 'DEVICES' in parts[j]
                    ), None)

                    if policy_name and category_name:
                        policy_dir = os.path.join(output_dir, policy_name)
                        category_dir = os.path.join(policy_dir, category_name)
                        os.makedirs(category_dir, exist_ok=True)
                        shutil.move(
                            os.path.join(root, file),
                            os.path.join(category_dir, file)
                        )
    except Exception as e:
        print(f"Error extracting tar file {file_path}: {e}")


def copy_and_extract_files(base_dir, logs_dir):
    """
    Copies and extracts (.tar.gz and .log) files from base_dir to logs_dir.
    It creates a subfolder for each file based on the file name (without extension).
    """
    ite_dirs = []

    for file_name in os.listdir(base_dir):
        if file_name.endswith(('.tar.gz', '.log')):
            ite_name = file_name.split('.')[0]
            ite_dir = os.path.join(logs_dir, ite_name)
            os.makedirs(ite_dir, exist_ok=True)
            ite_dirs.append(ite_dir)
            full_file_name = os.path.join(base_dir, file_name)
            shutil.copy(full_file_name, ite_dir)

            if file_name.endswith('.tar.gz'):
                extract_and_categorize_tar(os.path.join(ite_dir, file_name), ite_dir)

    return ite_dirs


def remove_nested_ite_folders(ite_dirs):
    """
    If the extraction process creates a nested folder with the same name
    as the ITE folder, remove it.
    """
    for ite_dir in ite_dirs:
        nested_ite_dir = os.path.join(ite_dir, os.path.basename(ite_dir))
        if os.path.exists(nested_ite_dir):
            shutil.rmtree(nested_ite_dir)


###############################################################################
# 4. Single-pass log reading (convert to single-line on the fly)
###############################################################################
def read_log_as_single_line(log_file_path):
    """
    Reads a .log file, converts it into a single line (merging lines after the first).
    Returns the single-line string.
    """
    try:
        with open(log_file_path, 'r') as lf:
            lines = [line.strip() for line in lf]
        if len(lines) > 1:
            return ";".join(lines[1:])
        elif lines:
            return lines[0]
        else:
            return ""
    except Exception as e:
        print(f"Error reading log file {log_file_path}: {e}")
        return ""


###############################################################################
# 5. Read logs from ITE->Policy->Category structure (only ALL_APPS_GENERIC)
###############################################################################
def read_logs(logs_dir):
    """
    Recursively searches for .log files in the structure:
      <logs_dir>/<ITE>/<Policy>/<Category>
    BUT we only process the category == 'ALL_APPS_GENERIC', ignoring others.
    This way, we skip unnecessary work for other categories.
    """
    log_data = {}
    total_logs = 0
    unique_policies = set()
    unique_categories = set()

    for ite_dir in os.listdir(logs_dir):
        ite_path = os.path.join(logs_dir, ite_dir)
        if os.path.isdir(ite_path):
            log_data[ite_dir] = {}
            # Check each policy folder
            for policy_name in os.listdir(ite_path):
                policy_path = os.path.join(ite_path, policy_name)
                if os.path.isdir(policy_path):
                    log_data[ite_dir][policy_name] = {}
                    unique_policies.add(policy_name)

                    # We ONLY read logs from the 'ALL_APPS_GENERIC' category
                    category_path = os.path.join(policy_path, 'ALL_APPS_GENERIC')
                    if os.path.isdir(category_path):
                        log_files = {}
                        unique_categories.add('ALL_APPS_GENERIC')

                        for log_file in natsorted(os.listdir(category_path)):
                            if log_file.endswith('.log'):
                                log_file_path = os.path.join(category_path, log_file)
                                single_line = read_log_as_single_line(log_file_path)
                                if single_line:
                                    log_files[log_file] = [single_line]
                                    total_logs += 1
                        # Store logs under 'ALL_APPS_GENERIC'
                        log_data[ite_dir][policy_name]['ALL_APPS_GENERIC'] = log_files

    total_ites = len(log_data)
    total_unique_policies = len(unique_policies)
    total_unique_categories = len(unique_categories)

    print("\n--- Log Reading Finished ---\n")
    print(f"Total ITEs processed: {total_ites}")
    print(f"Unique Policies processed: {total_unique_policies}")
    print(f"Unique Categories processed: {total_unique_categories}")
    print(f"Total log files read: {total_logs}")

    return log_data


###############################################################################
# 6. Process files by date
###############################################################################
def process_files_by_date(base_path, selected_date):
    """
    1) Check and parse 'selected_date'.
    2) Locate base_dir = output/<selected_date>/default_config.
    3) Create results/<selected_date>/logs & graph folders.
    4) Copy and extract files from base_dir to logs_dir.
    5) Read logs (only ALL_APPS_GENERIC) and return (log_data, logs_dir, graph_dir).
    """
    try:
        # Validate date format
        datetime.strptime(selected_date, '%d-%m-%Y_%H-%M')
    except ValueError as e:
        print(f"Invalid date format. Please use DD-MM-YYYY_HH-MM. Error: {e}")
        return {}

    # 1) Source directory: output/<date>/default_config
    base_dir = os.path.join(base_path, selected_date, 'default_config')
    if not os.path.isdir(base_dir):
        print(f"Error: Base directory not found: {base_dir}")
        return {}

    # 2) Create logs/graph folders under results/<date>
    date_dir, logs_dir, graph_dir = create_date_structure(selected_date)

    # 3) Copy and extract files
    ite_dirs = copy_and_extract_files(base_dir, logs_dir)
    remove_nested_ite_folders(ite_dirs)
    remove_progress_folder(logs_dir)

    # 4) Read logs (ALL_APPS_GENERIC only)
    log_data = read_logs(logs_dir)
    return log_data, logs_dir, graph_dir

###############################################################################
# 7. Selection menu (ITE, Policy)
###############################################################################
def select_option(options, option_name):
    """
    Displays options in two columns, returns a single selected item
    or 'ALL' if the user chooses '0'.
    """
    options = natsorted(options)
    max_width = max(len(option) for option in options) + 2
    format_str = f"{{:<{max_width}}}  |  {{:<{max_width}}}"

    print(f"0. Process all {option_name.lower()}s")
    for idx in range(0, len(options), 2):
        if idx + 1 < len(options):
            print(format_str.format(f"{idx + 1}. {options[idx]}", f"{idx + 2}. {options[idx + 1]}"))
        else:
            print(f"{idx + 1}. {options[idx]}")
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


###############################################################################
# 8. Append log lines to DataFrame (via dict)
###############################################################################
def print_log_line(line, data, ite, policy_name, devices, category):
    items = line.split(';')
    data['ite'].append(ite)
    data['policy_name'].append(policy_name)
    data['devices'].append(devices)
    data['category'].append(category)
    index = 0
    for item in items:
        name = all_apps_generic.get(index)
        data[name].append(item)
        index += 1


###############################################################################
# 9. Generate and save plots
###############################################################################
def plot_graph(mean_df, input_date, graph_dir, auto=False):
    """
    If auto=True, automatically plot a predefined list of columns
    with x='devices' and y in auto_plot_columns.
    If auto=False, ask the user to select X and Y columns.
    """
    auto_plot_columns = [
        # ALL
        'num_of_completed_tasks(ALL)',
        'num_of_failed_tasks(ALL)',
        'num_of_uncompleted_tasks(ALL)',
        'num_of_failed_tasks_due_network(ALL)',
        'num_of_failed_tasks_due_vm_capacity(ALL)',
        'num_of_failed_tasks_due_mobility(ALL)',
        'average_service_time(ALL)_(sec)',
        'average_processing_time(ALL)_(sec)',
        'average_network_delay(ALL)_(sec)',
        # CLOUD
        'num_of_completed_tasks(Cloud)',
        'num_of_failed_tasks(Cloud)',
        'num_of_uncompleted_tasks(Cloud)',
        'average_service_time(Cloud)_(sec)',
        'average_processing_time(Cloud)_(sec)',
        'average_server_utilization(Cloud)_(%)',
        'num_of_failed_tasks_due_vm_capacity(Cloud)',
        # EDGE
        'num_of_completed_tasks(Edge)',
        'num_of_failed_tasks(Edge)',
        'num_of_uncompleted_tasks(Edge)',
        'average_service_time(Edge)_(sec)',
        'average_processing_time(Edge)_(sec)',
        'average_server_utilization(Edge)_(%)',
        'num_of_failed_tasks_due_vm_capacity(Edge)',
        # MOBILE
        'num_of_completed_tasks(Mobile)',
        'num_of_failed_tasks(Mobile)',
        'num_of_uncompleted_tasks(Mobile)',
        'average_service_time(Mobile)_(sec)',
        'average_processing_time(Mobile)_(sec)',
        'average_server_utilization(Mobile)_(%)',
        'num_of_failed_tasks_due_vm_capacity(Mobile)'
    ]
    auto_plot_columns.append('num_of_completed_plus_failed_tasks(ALL)')

    if not auto:
        # Manual selection of X and Y
        columns = mean_df.columns.tolist()
        max_width = max(len(column) for column in columns) + 2
        format_str = f"{{:<{max_width}}}  |  {{:<{max_width}}}"

        print("\nSelect the columns for the X and Y axis of the graph:\n")
        for idx in range(0, len(columns), 2):
            if idx + 1 < len(columns):
                print(format_str.format(f"{idx + 1}. {columns[idx]}", f"{idx + 2}. {columns[idx + 1]}"))
            else:
                print(f"{idx + 1}. {columns[idx]}")

        while True:
            try:
                print("\n" + "-" * 50)
                x_selection = int(input("\nSelect column for X axis by number: ")) - 1
                y_selection = int(input("Select column for Y axis by number: ")) - 1
                print("\n" + "-" * 50)
                if 0 <= x_selection < len(columns) and 0 <= y_selection < len(columns):
                    x_col = columns[x_selection]
                    y_col = columns[y_selection]
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        create_and_save_plot(mean_df, x_col, y_col, input_date, graph_dir)
    else:
        # Automatic mode
        x_col = 'devices'
        for y_col in auto_plot_columns:
            create_and_save_plot(mean_df, x_col, y_col, input_date, graph_dir)


def create_and_save_plot(mean_df, x_col, y_col, input_date, graph_dir):
    mean_df[x_col] = mean_df[x_col].astype(int)

    first_row_policies = ['ONLY_MOBILE','ONLY_EDGE','ONLY_CLOUD']
    second_row_policies = ['NETWORK_BASED','UTILIZATION_BASED','EDGE_PRIORITY']
    fixed_policy_order = first_row_policies + second_row_policies

    colors = ['#2b83ba', '#abdda4', '#fdae61', '#d7191c', '#8c564b', '#9467bd',
              '#ff7f0e', '#17becf', '#1f77b4', '#bcbd22']
    markers = ['o', 'x', 's', 'd', '^']

    line_graph_metrics = [
        'average_processing_time(ALL)_(sec)', 'average_service_time(ALL)_(sec)',
        'average_network_delay(ALL)_(sec)', 'average_service_time(Cloud)_(sec)',
        'average_processing_time(Cloud)_(sec)', 'average_service_time(Edge)_(sec)',
        'average_processing_time(Edge)_(sec)', 'average_service_time(Mobile)_(sec)',
        'average_processing_time(Mobile)_(sec)'
    ]

    plt.figure(figsize=(16, 10), dpi=300)
    bar_width = 0.15
    unique_x_values = mean_df[x_col].unique()

    plotting_data_list = []

    if y_col in line_graph_metrics:
        # Line graph
        for i, policy in enumerate(fixed_policy_order):
            if policy in mean_df['policy_name'].unique():
                policy_df = mean_df[mean_df['policy_name'] == policy].copy()
                plotting_data_list.append(policy_df[['policy_name', x_col, y_col]])
                plt.plot(
                    policy_df[x_col], policy_df[y_col],
                    label=policy, color=colors[i % len(colors)],
                    marker=markers[i % len(markers)], markersize=8, linewidth=2
                )
        plt.xticks(unique_x_values, fontsize=18)
    else:
        # Bar graph
        x_positions = np.arange(len(unique_x_values))

        for i, policy in enumerate(fixed_policy_order):
            if policy in mean_df['policy_name'].unique():
                policy_df = mean_df[mean_df['policy_name'] == policy].copy()

                # Convert some columns to percentages
                if y_col in [
                    'num_of_completed_tasks(ALL)',
                    'num_of_failed_tasks(ALL)',
                    'num_of_uncompleted_tasks(ALL)',
                    'num_of_completed_plus_failed_tasks(ALL)'
                ]:
                    total = (policy_df['num_of_completed_tasks(ALL)'] +
                             policy_df['num_of_failed_tasks(ALL)'])
                    total[total == 0] = 1
                    policy_df[y_col] = (policy_df[y_col] / total) * 100

                elif y_col in [
                    'num_of_failed_tasks_due_network(ALL)',
                    'num_of_failed_tasks_due_vm_capacity(ALL)',
                    'num_of_failed_tasks_due_mobility(ALL)'
                ]:
                    total_failed = policy_df['num_of_failed_tasks(ALL)']
                    total_failed[total_failed == 0] = 1
                    policy_df[y_col] = (policy_df[y_col] / total_failed) * 100

                plotting_data_list.append(policy_df[['policy_name', x_col, y_col]])

                if y_col == 'num_of_completed_plus_failed_tasks(ALL)':
                    plt.bar(x_positions + i * bar_width,
                            policy_df[y_col],
                            bar_width,
                            label=policy,
                            color=colors[i % len(colors)],
                            alpha=0.5)
                else:
                    plt.bar(x_positions + i * bar_width,
                            policy_df[y_col],
                            bar_width,
                            label=policy,
                            color=colors[i % len(colors)])

                # Additional bar for completed vs. failed tasks
                if y_col == 'num_of_completed_plus_failed_tasks(ALL)':
                    completed_tasks = policy_df['num_of_completed_tasks(ALL)']
                    total = (policy_df['num_of_completed_tasks(ALL)'] +
                             policy_df['num_of_failed_tasks(ALL)'])
                    total[total == 0] = 1
                    completed_tasks_pct = (completed_tasks / total) * 100
                    plt.bar(x_positions + i * bar_width,
                            completed_tasks_pct,
                            bar_width,
                            color=colors[i % len(colors)],
                            label='_nolegend_')

        plt.xticks(x_positions + bar_width * (len(fixed_policy_order) - 1) / 2,
                   labels=unique_x_values, fontsize=18, ha='center')

    # Format axis labels
    from_value = format_graph_title(y_col)
    from_value = from_value.replace('(All)', '').replace('(ALL)', '').strip()
    formatted_x_label = format_axis_label(x_col, axis="x")
    formatted_y_label = format_axis_label(y_col, axis="y")

    plt.xlabel(formatted_x_label, labelpad=10, fontsize=20)

    if y_col in ['num_of_completed_tasks(ALL)', 'num_of_completed_plus_failed_tasks(ALL)']:
        plt.ylabel('Task Completion (%)', labelpad=10, fontsize=20)
    elif y_col in [
        'num_of_failed_tasks(ALL)',
        'num_of_failed_tasks_due_network(ALL)',
        'num_of_failed_tasks_due_vm_capacity(ALL)',
        'num_of_failed_tasks_due_mobility(ALL)'
    ]:
        plt.ylabel('Task Failure (%)', labelpad=10, fontsize=20)
    else:
        plt.ylabel(formatted_y_label, labelpad=10, fontsize=20)

    # Set y-axis range for these columns
    if y_col in ['num_of_completed_tasks(ALL)', 'num_of_completed_plus_failed_tasks(ALL)']:
        plt.ylim(82, 101)

    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.grid(False, axis='x')

    unique_policies = [policy for policy in fixed_policy_order if policy in mean_df['policy_name'].unique()]
    adjust_legend_to_two_rows(unique_policies)
    plt.tight_layout(rect=[0, 0, 1, 0.9])

    # Decide subfolder (ALL, CLOUD, EDGE, MOBILE, OTHERS) based on y_col
    if 'ALL' in y_col:
        folder = 'ALL'
    elif 'Cloud' in y_col:
        folder = 'CLOUD'
    elif 'Edge' in y_col:
        folder = 'EDGE'
    elif 'Mobile' in y_col:
        folder = 'MOBILE'
    else:
        folder = 'OTHERS'

    # Final path to save the graph: results/<date>/graph/<folder>
    output_graph_dir = os.path.join(graph_dir, folder)
    os.makedirs(output_graph_dir, exist_ok=True)

    # Save the plot
    graph_file_name = os.path.join(output_graph_dir, f"{x_col}_per_{y_col}.png")
    plt.savefig(graph_file_name, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Graph saved to {graph_file_name}")
    print("\n" + "-" * 50 + "\n")

    # Save the DataFrame that was used to create this plot
    if plotting_data_list:
        final_plot_df = pd.concat(plotting_data_list, ignore_index=True)
        final_plot_csv = os.path.join(output_graph_dir, f"{x_col}_per_{y_col}.csv")
        final_plot_df.to_csv(final_plot_csv, index=False)
        print(f"Plot data saved to {final_plot_csv}")
        print("\n" + "-" * 50 + "\n")


def adjust_legend_to_two_rows(unique_policies):
    """
    Dynamically create a two-row legend if necessary,
    distributing policies evenly across columns.
    """
    num_policies = len(unique_policies)
    ncol = (num_policies + 1) // 2
    plt.legend(
        unique_policies,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.15),
        fontsize=18,
        ncol=ncol,
        frameon=True
    )


def format_graph_title(y_col):
    title_mappings = {
        'average_processing_time(ALL)_(sec)': 'Average Processing Time (All) (sec)',
        'average_service_time(ALL)_(sec)': 'Average Service Time (All) (sec)',
        'average_network_delay(ALL)_(sec)': 'Average Network Delay (All) (sec)',
        'average_service_time(Cloud)_(sec)': 'Average Service Time (Cloud) (sec)',
        'average_processing_time(Cloud)_(sec)': 'Average Processing Time (Cloud) (sec)',
        'average_service_time(Edge)_(sec)': 'Average Service Time (Edge) (sec)',
        'average_processing_time(Edge)_(sec)': 'Average Processing Time (Edge) (sec)',
        'average_service_time(Mobile)_(sec)': 'Average Service Time (Mobile) (sec)',
        'average_processing_time(Mobile)_(sec)': 'Average Processing Time (Mobile) (sec)',
        'num_of_completed_tasks(ALL)': 'Number of Completed Tasks (All)',
        'num_of_failed_tasks(ALL)': 'Number of Failed Tasks (All)',
        'num_of_uncompleted_tasks(ALL)': 'Number of Uncompleted Tasks (All)',
        'num_of_completed_tasks(Cloud)': 'Number of Completed Tasks (Cloud)',
        'num_of_failed_tasks(Cloud)': 'Number of Failed Tasks (Cloud)',
        'num_of_uncompleted_tasks(Cloud)': 'Number of Uncompleted Tasks (Cloud)',
        'num_of_completed_tasks(Edge)': 'Number of Completed Tasks (Edge)',
        'num_of_failed_tasks(Edge)': 'Number of Failed Tasks (Edge)',
        'num_of_uncompleted_tasks(Edge)': 'Number of Uncompleted Tasks (Edge)',
        'num_of_completed_tasks(Mobile)': 'Number of Completed Tasks (Mobile)',
        'num_of_failed_tasks(Mobile)': 'Number of Failed Tasks (Mobile)',
        'num_of_uncompleted_tasks(Mobile)': 'Number of Uncompleted Tasks (Mobile)',
        'num_of_failed_tasks_due_network(ALL)': 'Number of Failed Tasks Due to Network (All)',
        'num_of_failed_tasks_due_vm_capacity(ALL)': 'Number of Failed Tasks Due to VM Capacity (All)',
        'num_of_failed_tasks_due_mobility(ALL)': 'Number of Failed Tasks Due to Mobility (All)',
        'num_of_failed_tasks_due_network(Cloud)': 'Number of Failed Tasks (Network - Cloud)',
        'num_of_failed_tasks_due_vm_capacity(Cloud)': 'Number of Failed Tasks (VM Capacity - Cloud)',
        'num_of_failed_tasks_due_network(Edge)': 'Number of Failed Tasks (Network - Edge)',
        'num_of_failed_tasks_due_vm_capacity(Edge)': 'Number of Failed Tasks (VM Capacity - Edge)',
        'num_of_failed_tasks_due_network(Mobile)': 'Number of Failed Tasks (Network - Mobile)',
        'num_of_failed_tasks_due_vm_capacity(Mobile)': 'Number of Failed Tasks (VM Capacity - Mobile)',
        'num_of_completed_plus_failed_tasks(ALL)': 'Number of Completed + Failed Tasks (All)'
    }
    return title_mappings.get(y_col, y_col)


def format_axis_label(label, axis="x"):
    label_mappings = {
        'devices': 'Number of MDs',
        'average_processing_time(ALL)_(sec)': 'Processing Time (sec)',
        'average_service_time(ALL)_(sec)': 'Service Time (sec)',
        'average_network_delay(ALL)_(sec)': 'Network Delay (sec)',
        'average_service_time(Cloud)_(sec)': 'Cloud Service Time (sec)',
        'average_processing_time(Cloud)_(sec)': 'Cloud Processing Time (sec)',
        'average_service_time(Edge)_(sec)': 'Edge Service Time (sec)',
        'average_processing_time(Edge)_(sec)': 'Edge Processing Time (sec)',
        'average_service_time(Mobile)_(sec)': 'Mobile Service Time (sec)',
        'average_processing_time(Mobile)_(sec)': 'Mobile Processing Time (sec)',
        'num_of_completed_tasks(ALL)': 'Completed Tasks',
        'num_of_failed_tasks(ALL)': 'Failed Tasks',
        'num_of_uncompleted_tasks(ALL)': 'Uncompleted Tasks',
        'num_of_completed_tasks(Cloud)': 'Completed Tasks (Cloud)',
        'num_of_failed_tasks(Cloud)': 'Failed Tasks (Cloud)',
        'num_of_uncompleted_tasks(Cloud)': 'Uncompleted Tasks (Cloud)',
        'num_of_completed_tasks(Edge)': 'Completed Tasks (Edge)',
        'num_of_failed_tasks(Edge)': 'Failed Tasks (Edge)',
        'num_of_uncompleted_tasks(Edge)': 'Uncompleted Tasks (Edge)',
        'num_of_completed_tasks(Mobile)': 'Completed Tasks (Mobile)',
        'num_of_failed_tasks(Mobile)': 'Failed Tasks (Mobile)',
        'num_of_uncompleted_tasks(Mobile)': 'Uncompleted Tasks (Mobile)',
        'num_of_failed_tasks_due_network(ALL)': 'Failed Tasks (Network)',
        'num_of_failed_tasks_due_vm_capacity(ALL)': 'Failed Tasks (VM Capacity)',
        'num_of_failed_tasks_due_mobility(ALL)': 'Failed Tasks (Mobility)',
        'num_of_failed_tasks_due_network(Cloud)': 'Failed Tasks (Network - Cloud)',
        'num_of_failed_tasks_due_vm_capacity(Cloud)': 'Failed Tasks (VM Capacity - Cloud)',
        'num_of_failed_tasks_due_network(Edge)': 'Failed Tasks (Network - Edge)',
        'num_of_failed_tasks_due_vm_capacity(Edge)': 'Failed Tasks (VM Capacity - Edge)',
        'num_of_failed_tasks_due_network(Mobile)': 'Failed Tasks (Network - Mobile)',
        'num_of_failed_tasks_due_vm_capacity(Mobile)': 'Failed Tasks (VM Capacity - Mobile)',
        'num_of_completed_plus_failed_tasks(ALL)': 'Completed+Failed Tasks'
    }
    return label_mappings.get(label, label)


###############################################################################
# 10. Main
###############################################################################
if __name__ == "__main__":
    try:
        base_path = "output"
        date_folders = get_available_date_folders(base_path)
        input_date = select_date_folder(date_folders)
        print("\n" + "-" * 20)
        print(f"Selected Date: {input_date}")
        print("-" * 20)

        # Process files by date -> create logs, graph folders & read logs
        result = process_files_by_date(base_path, input_date)
        if not result:
            sys.exit(1)  # Exit if processing fails

        log_data, logs_dir, graph_dir = result

        # Prepare a dict for building a DataFrame
        data = {key: [] for key in ['ite', 'policy_name', 'devices', 'category'] + list(all_apps_generic.values())}

        # ITE selection
        ite_keys = natsorted(list(log_data.keys()))
        print("\n" + "-" * 50 + "\n")
        print("Available ITEs:")
        ite_selection = select_option(ite_keys, "ITE")

        if ite_selection == 'ALL':
            selected_ites = ite_keys
            ite_part = 'all_ites'
        else:
            selected_ites = [ite_selection]
            ite_part = ite_selection

        # Policy selection
        policy_keys = natsorted({policy for ite in selected_ites for policy in log_data.get(ite, {}).keys()})
        print("\n" + "-" * 50 + "\n")
        print("Available Policies:")
        policy_selection = select_option(policy_keys, "Policies")

        if policy_selection == 'ALL':
            selected_policies = policy_keys
            policy_part = 'all_policies'
        else:
            selected_policies = [policy_selection]
            policy_part = policy_selection

        # ----------------------------------------------------------------
        # Category selection is forced to ALL_APPS_GENERIC, so we skip 
        # interactive picking. We'll just print a reference list (if needed).
        # ----------------------------------------------------------------
        # (We keep the old block commented, as requested.)
        """
        category_keys = natsorted({
            category
            for ite in selected_ites
            for policy in selected_policies
            for category in log_data.get(ite, {}).get(policy, {}).keys()
        })
        print("\n" + "-" * 50 + "\n")
        print("Available Categories:")
        category_selection = select_option(category_keys, "Categories")

        if category_selection == 'ALL':
            selected_categories = category_keys
            category_part = 'all_categories'
        else:
            selected_categories = [category_selection]
            category_part = category_selection
        """
        # Instead, we directly use:
        print("\n--- Forcing Category to: ALL_APPS_GENERIC ---\n")
        selected_categories = ["ALL_APPS_GENERIC"]
        category_part = "ALL_APPS_GENERIC"

        # Build the DataFrame based on the selected ITE/Policy/Category
        for ite in selected_ites:
            for policy in selected_policies:
                for category in selected_categories:
                    # We only have logs under 'ALL_APPS_GENERIC' anyway
                    if category in log_data[ite].get(policy, {}):
                        print(f"\n--- Logs for {category} in {policy} of {ite} ---")
                        print(f"{'Log File':<50} {'Devices':<15}")
                        print('-' * 65)

                        for log_file, log_lines in log_data[ite][policy][category].items():
                            devices = [
                                part.replace('DEVICES', '')
                                for part in log_file.split('_') if 'DEVICES' in part
                            ][0]
                            print(f"{log_file:<50} {devices:<15}")
                            print_log_line(log_lines[0], data, ite, policy, devices, category)

        df = pd.DataFrame(data)

        # Convert numeric columns
        numeric_cols = list(all_apps_generic.values()) + ["devices"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        # Sort the DataFrame
        sorted_df = df.sort_values(by=['policy_name', 'devices'])

        # Group by [policy_name, devices] and compute mean
        numeric_columns = sorted_df.select_dtypes(include=['number']).columns
        mean_df = sorted_df.groupby(['policy_name', 'devices'], as_index=False)[numeric_columns].mean()

        # Add a new column: completed + failed
        mean_df['num_of_completed_plus_failed_tasks(ALL)'] = \
            mean_df['num_of_completed_tasks(ALL)'] + mean_df['num_of_failed_tasks(ALL)']

        # Directory for CSV files: logs_dir/csv
        csv_dir = os.path.join(logs_dir, "csv")
        os.makedirs(csv_dir, exist_ok=True)

        # 1) Raw
        file_raw = os.path.join(csv_dir, f"{input_date}_logs_{ite_part}_{policy_part}_{category_part}.csv")
        df.to_csv(file_raw, index=False)
        print(f"Data saved to {file_raw}")

        # 2) Sorted
        file_sorted = os.path.join(csv_dir, f"{input_date}_logs_sorted_{ite_part}_{policy_part}_{category_part}.csv")
        sorted_df.to_csv(file_sorted, index=False)
        print(f"Sorted data saved to {file_sorted}")

        # 3) Mean
        file_mean = os.path.join(csv_dir, f"{input_date}_logs_mean_{ite_part}_{policy_part}_{category_part}.csv")
        mean_df.to_csv(file_mean, index=False)
        print(f"Mean data saved to {file_mean}")

        # Ask if the user wants to plot graphs
        print("-" * 50)
        while True:
            plot_choice = input("Do you want to plot graphs automatically or manually? (a/m): ").lower()
            if plot_choice == 'a':
                print("\n--- Automatic Plotting ---\n")
                plot_graph(mean_df, input_date, graph_dir, auto=True)
                break
            elif plot_choice == 'm':
                plot_graph(mean_df, input_date, graph_dir, auto=False)
                break
            else:
                print("Invalid choice. Please enter 'a' for automatic or 'm' for manual.")

    except KeyboardInterrupt:
        print("\n--- Exit ---")
