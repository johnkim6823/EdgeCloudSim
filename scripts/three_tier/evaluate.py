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
# 전역 폴더명 상수
###############################################################################
RESULTS_FOLDER_NAME = "results"  # logs/graph 가 들어갈 최상위 폴더
LOGS_SUBFOLDER_NAME = "logs"
GRAPH_SUBFOLDER_NAME = "graph"


###############################################################################
# 1. 날짜 폴더 선택 관련
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
                return date_folders[-1]  # 최신 날짜 자동 선택
            elif 0 <= selection < len(date_folders):
                return date_folders[selection]
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a valid number.")


###############################################################################
# 2. 날짜별 logs, graph 폴더 생성
###############################################################################
def create_date_structure(selected_date):
    """
    results/<selected_date>/logs
    results/<selected_date>/graph
    두 폴더를 생성 (기존에 있으면 삭제 후 재생성).
    """
    # 최상위 results 폴더
    results_dir = os.path.join(os.getcwd(), RESULTS_FOLDER_NAME)
    os.makedirs(results_dir, exist_ok=True)

    # 날짜별 폴더 (예: results/31-01-2025_01-00)
    date_dir = os.path.join(results_dir, selected_date)
    os.makedirs(date_dir, exist_ok=True)  # 날짜 폴더 자체는 지우지 않고 재사용할 수도 있음

    # logs 폴더: results/<날짜>/logs
    logs_dir = os.path.join(date_dir, LOGS_SUBFOLDER_NAME)
    # graph 폴더: results/<날짜>/graph
    graph_dir = os.path.join(date_dir, GRAPH_SUBFOLDER_NAME)

    # 필요 시, logs/graph 폴더는 매번 초기화
    if os.path.exists(logs_dir):
        shutil.rmtree(logs_dir)
    os.makedirs(logs_dir, exist_ok=True)

    if os.path.exists(graph_dir):
        shutil.rmtree(graph_dir)
    os.makedirs(graph_dir, exist_ok=True)

    return date_dir, logs_dir, graph_dir


def remove_progress_folder(date_logs_dir):
    """
    progress 폴더가 있으면 삭제.
    """
    progress_dir = os.path.join(date_logs_dir, 'progress')
    if os.path.exists(progress_dir):
        shutil.rmtree(progress_dir)


###############################################################################
# 3. tar.gz 추출 & 폴더 구조 정리
###############################################################################
def extract_and_categorize_tar(file_path, output_dir):
    try:
        with tarfile.open(file_path, 'r:gz') as tar:
            tar.extractall(path=output_dir)

        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.log'):
                    parts = file.split('_')
                    # policy_name, category_name 파싱
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
    base_dir 내의 .tar.gz, .log 파일을 logs_dir로 복사 & 압축해제 & 구조화.
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
    압축 해제 시 ITE 폴더 내부에 동일 이름 중첩 폴더가 생기면 삭제
    """
    for ite_dir in ite_dirs:
        nested_ite_dir = os.path.join(ite_dir, os.path.basename(ite_dir))
        if os.path.exists(nested_ite_dir):
            shutil.rmtree(nested_ite_dir)


###############################################################################
# 4. 로그 파일(멀티라인) -> 싱글 라인 변환
###############################################################################
def convert_logs_to_single_line(log_file_path):
    try:
        with open(log_file_path, 'r') as lf:
            lines = [line.strip() for line in lf.readlines()]
        if len(lines) > 1:
            single_line = ";".join(lines[1:])
            with open(log_file_path, 'w') as lf:
                lf.write(single_line)
    except Exception as e:
        print(f"Error converting log file {log_file_path} to single line: {e}")


###############################################################################
# 5. logs 폴더 구조(ITE->Policy->Category)에서 로그 불러오기
###############################################################################
def read_logs(logs_dir):
    log_data = {}
    total_logs = 0
    unique_policies = set()
    unique_categories = set()

    for ite_dir in os.listdir(logs_dir):
        ite_path = os.path.join(logs_dir, ite_dir)
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

    print("\n--- Log Reading Finished ---\n")
    print(f"Total ITEs processed: {total_ites}")
    print(f"Unique Policies processed: {total_unique_policies}")
    print(f"Unique Categories processed: {total_unique_categories}")
    print(f"Total log files read: {total_logs}")

    return log_data


###############################################################################
# 6. 날짜별 파일 처리
###############################################################################
def process_files_by_date(base_path, selected_date):
    """
    base_path (ex: 'output') 아래의 <selected_date>/default_config 디렉토리에 
    있는 tar.gz, log 파일들을 추출해서 
    results/<selected_date>/logs 에 정리합니다.
    """
    try:
        # 날짜 검증
        datetime.strptime(selected_date, '%d-%m-%Y_%H-%M')
    except ValueError as e:
        print(f"Invalid date format. Please use DD-MM-YYYY_HH-MM. Error: {e}")
        return {}

    # 1) 날짜별 소스 경로 (output/<date>/default_config)
    base_dir = os.path.join(base_path, selected_date, 'default_config')
    if not os.path.isdir(base_dir):
        print(f"Error: Base directory not found: {base_dir}")
        return {}

    # 2) results/<date>/logs, graph 폴더 생성
    date_dir, logs_dir, graph_dir = create_date_structure(selected_date)

    # 3) 파일 복사 & 압축해제
    ite_dirs = copy_and_extract_files(base_dir, logs_dir)
    remove_nested_ite_folders(ite_dirs)
    remove_progress_folder(logs_dir)

    # 4) 로그 읽기
    log_data = read_logs(logs_dir)
    return log_data, logs_dir, graph_dir


###############################################################################
# 7. 선택 기능 (ITE, Policy, Category)
###############################################################################
def select_option(options, option_name):
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
# 8. 로그를 DataFrame에 쌓기
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
# 9. 그래프 생성/저장
###############################################################################
def plot_graph(mean_df, input_date, graph_dir, auto=False):
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
        # 수동으로 X,Y 선택
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
                print("\n" + "-"*50)
                x_selection = int(input("\nSelect column for X axis by number: ")) - 1
                y_selection = int(input("Select column for Y axis by number: ")) - 1
                print("\n" + "-"*50)
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
        # 자동
        x_col = 'devices'
        for y_col in auto_plot_columns:
            create_and_save_plot(mean_df, x_col, y_col, input_date, graph_dir)


def create_and_save_plot(mean_df, x_col, y_col, input_date, graph_dir):
    plt.style.use(['science', 'ieee', 'no-latex'])

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
        # 라인 그래프
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
        # 바 그래프
        x_positions = np.arange(len(unique_x_values))

        for i, policy in enumerate(fixed_policy_order):
            if policy in mean_df['policy_name'].unique():
                policy_df = mean_df[mean_df['policy_name'] == policy].copy()

                # 일부 컬럼은 퍼센트로 변환
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

                # completed vs failed를 한눈에 보여주기 위한 추가 bar
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

    formatted_title = format_graph_title(y_col)
    formatted_title = formatted_title.replace('(All)', '').replace('(ALL)', '').strip()

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

    # 특정한 y값 범위
    if y_col in ['num_of_completed_tasks(ALL)', 'num_of_completed_plus_failed_tasks(ALL)']:
        plt.ylim(82, 101)

    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.grid(False, axis='x')

    unique_policies = [policy for policy in fixed_policy_order if policy in mean_df['policy_name'].unique()]
    adjust_legend_to_two_rows(unique_policies)
    plt.tight_layout(rect=[0, 0, 1, 0.9])

    # 그래프 저장 서브폴더 결정
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

    # 최종 저장 경로: results/<date>/graph/<folder>
    output_graph_dir = os.path.join(graph_dir, folder)
    os.makedirs(output_graph_dir, exist_ok=True)

    # 그래프 저장
    graph_file_name = os.path.join(output_graph_dir, f"{x_col}_per_{y_col}.png")
    plt.savefig(graph_file_name, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Graph saved to {graph_file_name}")
    print("\n" + "-"*50 + "\n")

    # 해당 그래프에 사용된 DF CSV 저장
    if plotting_data_list:
        final_plot_df = pd.concat(plotting_data_list, ignore_index=True)
        final_plot_csv = os.path.join(output_graph_dir, f"{x_col}_per_{y_col}.csv")
        final_plot_df.to_csv(final_plot_csv, index=False)
        print(f"Plot data saved to {final_plot_csv}")
        print("\n" + "-"*50 + "\n")


def adjust_legend_to_two_rows(unique_policies):
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
# 10. 메인 실행부
###############################################################################
if __name__ == "__main__":
    try:
        base_path = "output"
        date_folders = get_available_date_folders(base_path)
        input_date = select_date_folder(date_folders)
        print(f"\nSelected Date: {input_date}")

        # 파일을 날짜 기반으로 처리 -> logs, graph 폴더 생성 & 로그 가져오기
        result = process_files_by_date(base_path, input_date)
        if not result:
            sys.exit(1)  # 처리 실패시 종료

        log_data, logs_dir, graph_dir = result

        # DataFrame에 넣을 dict
        data = {key: [] for key in ['ite', 'policy_name', 'devices', 'category'] + list(all_apps_generic.values())}

        # ITE 선택
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

        # Policy 선택
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

        # Category 선택
        category_keys = natsorted({
            category
            for ite in selected_ites
            for policy in selected_policies
            for category in log_data.get(ite, {}).get(policy, {}).keys()
        })
        print("\n" + "-"*50 + "\n")
        print("Available Categories:")
        category_selection = select_option(category_keys, "Categories")

        if category_selection == 'ALL':
            selected_categories = category_keys
            category_part = 'all_categories'
        else:
            selected_categories = [category_selection]
            category_part = category_selection

        # 선택한 ITE/Policy/Category에 맞춰 DataFrame 생성
        for ite in selected_ites:
            for policy in selected_policies:
                for category in selected_categories:
                    if category in log_data[ite].get(policy, {}):
                        print(f"\n--- Logs for {category} in {policy} of {ite} ---")
                        print(f"{'Log File':<50} {'Devices':<15}")
                        print('-' * 65)

                        for log_file, log_lines in log_data[ite][policy][category].items():
                            devices = [part.replace('DEVICES', '')
                                       for part in log_file.split('_') if 'DEVICES' in part][0]
                            print(f"{log_file:<50} {devices:<15}")
                            print_log_line(log_lines[0], data, ite, policy, devices, category)

        df = pd.DataFrame(data)

        # 숫자 컬럼 변환
        numeric_cols = list(all_apps_generic.values()) + ["devices"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        # 정렬
        sorted_df = df.sort_values(by=['policy_name', 'devices'])

        # groupby mean
        numeric_columns = sorted_df.select_dtypes(include=['number']).columns
        mean_df = sorted_df.groupby(['policy_name', 'devices'], as_index=False)[numeric_columns].mean()

        # 완료+실패 합
        mean_df['num_of_completed_plus_failed_tasks(ALL)'] = \
            mean_df['num_of_completed_tasks(ALL)'] + mean_df['num_of_failed_tasks(ALL)']

        # CSV 저장용 폴더: logs_dir/csv
        csv_dir = os.path.join(logs_dir, "csv")
        os.makedirs(csv_dir, exist_ok=True)

        # 1) raw
        file_raw = os.path.join(csv_dir, f"{input_date}_logs_{ite_part}_{policy_part}_{category_part}.csv")
        df.to_csv(file_raw, index=False)
        print(f"Data saved to {file_raw}")

        # 2) sorted
        file_sorted = os.path.join(csv_dir, f"{input_date}_logs_sorted_{ite_part}_{policy_part}_{category_part}.csv")
        sorted_df.to_csv(file_sorted, index=False)
        print(f"Sorted data saved to {file_sorted}")

        # 3) mean
        file_mean = os.path.join(csv_dir, f"{input_date}_logs_mean_{ite_part}_{policy_part}_{category_part}.csv")
        mean_df.to_csv(file_mean, index=False)
        print(f"Mean data saved to {file_mean}")

        # 그래프 그릴지 여부
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
