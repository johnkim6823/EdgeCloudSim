# EdgeCloudSim

EdgeCloudSim provides a simulation environment specific to Edge Computing scenarios where it is possible to conduct experiments that considers both computational and networking resources. EdgeCloudSim is based on CloudSim but adds considerable functionality so that it can be efficiently used for Edge Computing scenarios. EdgeCloudSim is an open source tool and any contributions are welcome. If you want to contribute EdgeCloudSim, please check below feature list and the [contributing guidelines](/CONTRIBUTING.md). If you want to use EdgeCloudSim in your research work, please cite our paper [[3]](https://onlinelibrary.wiley.com/doi/abs/10.1002/ett.3493).

## Environment
Ubuntu 20.0.4.6


## PREREQUISITE 
```
sudo apt-get update
```
```
sudo apt-get upgrade
```
```
sudo apt install default-jre default-jdk maven
```
## Discussion Forum

The discussion forum for EdgeCloudSim can be found [here](https://groups.google.com/forum/#!forum/edgecloudsim).
We hope to meet with all interested parties in this forum.
Please feel free to join and let us discuss issues, share ideas related to EdgeCloudSim all together.

## YouTube Channel

The YouTube channel of EdgeCloudSim can be found [here](https://www.youtube.com/channel/UC2gnXTWHHN6h4bk1D5gpcIA).
You can find some videos presenting our works and tutorials on this channel.
Click [here](https://youtu.be/SmQgRANWUts) to watch the video with brief information about EdgeCloudSim.

## Needed Features

* Task migration among the Edge or Cloud VMs
* Energy consumption model for the mobile and edge devices as well as the cloud datacenters
* Adding probabilistic network failure model by considering the congestion or other parameters such as the distance between mobile device and the WiFi access point.
* Visual tool for displaying the network topology

# EdgeCloudSim: An Environment for Performance Evaluation of Edge Computing Systems

EdgeCloudSim provides a modular architecture to provide support for a variety of crucial functionalities such as network modeling specific to WLAN and WAN, device mobility model, realistic and tunable load generator. As depicted in Figure 2, the current EdgeCloudSim version has five main modules available: Core Simulation, Networking, Load Generator, Mobility and Edge Orchestrator. To ease fast prototyping efforts, each module contains a default implementation that can be easily extended.

<p align="center">
  <img src="/doc/images/edgecloudsim_diagram.png" width="55%">
  <p align="center">
    Figure 1: Relationship between EdgeCloudSim modules.
  </p>
</p>

## Mobility Module
The mobility module manages the location of edge devices and clients. Since CloudSim focuses on the conventional cloud computing principles, the mobility is not considered in the framework. In our design, each mobile device has x and y coordinates which are updated according to the dynamically managed hash table. By default, we provide a nomadic mobility model, but different mobility models can be implemented by extending abstract MobilityModel class.

<p align="center">
  <img src="/doc/images/mobility_module.png" width="55%">
</p>

## Load Generator Module
The load generator module is responsible for generating tasks for the given configuration. By default, the tasks are generated according to a Poisson distribution via active/idle task generation pattern. If other task generation patterns are required, abstract LoadGeneratorModel class should be extended.

<p align="center">
  <img src="/doc/images/task_generator_module.png" width="50%">
</p>

## Networking Module
The networking module particularly handles the transmission delay in the WLAN and WAN by considering both upload and download data. The default implementation of the networking module is based on a single server queue model. Users of EdgeCloudSim can incorporate their own network behavior models by extending abstract NetworkModel class.

<p align="center">
  <img src="/doc/images/network_module.png" width="55%">
</p>

## Edge Orchestrator Module
The edge orchestrator module is the decision maker of the system. It uses the information collected from the other modules to decide how and where to handle incoming client requests. In the first version, we simply use a probabilistic approach to decide where to handle incoming tasks, but more realistic edge orchestrator can be added by extending abstract EdgeOrchestrator class.

<p align="center">
  <img src="/doc/images/edge_orchestrator_module.png" width="65%">
</p>

## Core Simulation Module
The core simulation module is responsible for loading and running the Edge Computing scenarios from the configuration files. In addition, it offers a logging mechanism to save the simulation results into the files. The results are saved in comma-separated value (CSV) data format by default, but it can be changed to any format.

## Extensibility
EdgeCloudSim uses a factory pattern making easier to integrate new models mentioned above. As shown in Figure 2, EdgeCloudsim requires a scenario factory class which knows the creation logic of the abstract modules. If you want to use different mobility, load generator, networking and edge orchestrator module, you can use your own scenario factory which provides the concrete implementation of your custom modules.

<p align="center">
  <img src="/doc/images/class_diagram.png" width="100%">
  <p align="center">
    Figure 2: Class Diagram of Important Modules
  </p>
</p>

## Ease of Use
At the beginning of our study, we observed that too many parameters are used in the simulations and managing these parameters programmatically is difficult.
As a solution, we propose to use configuration files to manage the parameters.
EdgeCloudSim reads parameters dynamically from the following files:
- **config.properties:** Simulation settings are managed in configuration file
- **applications.xml:** Application properties are stored in xml file
- **edge_devices.xml:** Edge devices (datacenters, hosts, VMs etc.) are defined in xml file

<p align="center">
  <img src="/doc/images/ease_of_use.png" width="60%">
</p>

## Compilation and Running
To compile sample application, *compile.sh* script which is located in *scripts/sample_application* folder can be used. You can rewrite similar script for your own application by modifying the arguments of javac command in way to declare the java file which includes your main method. Please note that this script can run on Linux based systems, including Mac OS. You can also use your favorite IDE (eclipse, netbeans etc.) to compile your project.

In order to run multiple sample_application scenarios in parallel, you can use *run_scenarios.sh* script which is located in *scripts/sample_application* folder. To run your own application, modify the java command in *runner.sh* script in a way to declare the java class which includes your main method. The details of using this script is explained in [this](/wiki/How-to-run-EdgeCloudSim-application-in-parallel) wiki page.

You can also monitor each process via the output files located under *scripts/sample_application/output/date* folder. For example:
```
./run_scenarios.sh {# of parallel Processes} {# of iteration}
tail -f output/date/ite_1.log
```
# To make new scenario
## Change following files
**scripts/{scenario_name}** 
  1. compile.sh
  2. runner.sh
  3. matlab/getConfiguration.m

**src/edu/boun/edgecloudsim**
  1. Change all .java file's pakage to corresponding scenario_name
  2. In MainApp.java, change SCENARIO_NAME into corresponding scenario_name


# Scenario Descriptions

## Three-Tier
| Policy                | Description                                                                                                                                                           |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ONLY_MOBILE           | - Tasks are processed only on the mobile device                                                                                                                        |
| ONLY_EDGE             | - Tasks are processed only on the edge server                                                                                                                          |
| ONLY_CLOUD            | - Tasks are processed only on the cloud                                                                                                                                |
| UTILIZATION_BASED      | - Considers only edge server utilization.<br>- If edge utilization > 80%:<br>&nbsp;&nbsp;&nbsp;- Offload to the cloud if bandwidth is high (wanBW > 2)<br>&nbsp;&nbsp;&nbsp;- Keep task on mobile if bandwidth is low.<br>- If edge utilization ≤ 80%: use the edge server. |
| NETWORK_BASED          | - Considers only network delay and bandwidth.<br>- If bandwidth > 5: offload to the cloud.<br>- If bandwidth > 2: offload to the edge server.<br>- If bandwidth ≤ 2: keep the task on mobile. |
| RANDOM                 | - Randomly assigns tasks to one of the following:<br>&nbsp;&nbsp;&nbsp;- Mobile device<br>&nbsp;&nbsp;&nbsp;- Edge server<br>&nbsp;&nbsp;&nbsp;- Cloud. |
| EDGE_PRIORITY          | - Prioritizes the edge server.<br>- If bandwidth > 6:<br>&nbsp;&nbsp;&nbsp;- Offload to edge server if utilization ≤ 90%<br>&nbsp;&nbsp;&nbsp;- Offload to cloud if edge utilization > 90%.<br>- If bandwidth > 3:<br>&nbsp;&nbsp;&nbsp;- Offload to cloud if edge utilization > 90%<br>&nbsp;&nbsp;&nbsp;- Offload to mobile if edge utilization < 20%<br>&nbsp;&nbsp;&nbsp;- Otherwise, offload to edge server.<br>- If bandwidth ≤ 3: keep task on mobile. |


## Fuzzy
| Policy                | Description                                                                                                                                                           |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FUZZY_BASED            | - Uses fuzzy logic to make decisions based on various factors.<br>- Inputs: manual delay, nearest edge utilization, best remote edge utilization.<br>- If offload decision > 50, offload to the best remote edge host.<br>- Considers task size, bandwidth, delay sensitivity, and edge utilization for final decision.<br>&nbsp;&nbsp;&nbsp;- Offload to mobile if decision > 60<br>&nbsp;&nbsp;&nbsp;- Offload to cloud if decision between 50 and 60<br>&nbsp;&nbsp;&nbsp;- Otherwise, use the best edge server. |
| FUZZY_COMPETITOR       | - Competitor-based fuzzy decision making.<br>- Inputs: bandwidth, CPU speed, video execution, and data size.<br>- If offload decision > 60, offload to mobile.<br>&nbsp;&nbsp;&nbsp;- If decision between 50 and 60, offload to cloud.<br>&nbsp;&nbsp;&nbsp;- Otherwise, use the edge server. |

# How to Use evalute.py
1. Change extract_and_categorize_tar(file_path, output_dir)'s Scenario Name
Update the following line inside the extract_and_categorize_tar() function:

python
policy_name = next(('_'.join(parts[i + 1:j]) for i, part in enumerate(parts) if part == 'TIER' for j in range(i + 1, len(parts)) if 'DEVICES' in parts[j]), None)
Modify the condition:

python
if part == '[]'
This change ensures that scenarios are correctly named according to the desired format.

2. Modify create_and_save_plot(mean_df, x_col, y_col)'s Policy Legend
To ensure consistency and clarity in the plot legends, define a fixed order for policies in the legend. Split the legend into two rows for better readability:

python
first_row_policies = []
second_row_policies = []
By doing this, the plot's legend will be more organized, enhancing the overall presentation.

These adjustments aim to enhance the functionality of the evalute.py script and improve the clarity of visual outputs.

