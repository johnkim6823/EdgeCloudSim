/*
 * Title:        EdgeCloudSim - Edge Orchestrator
 * 
 * Description: 
 * SampleEdgeOrchestrator offloads tasks to proper server
 * In this scenario mobile devices can also execute tasks
 * 
 * Licence:      GPL - http://www.gnu.org/copyleft/gpl.html
 * Copyright (c) 2017, Bogazici University, Istanbul, Turkey
 */

package edu.boun.edgecloudsim.applications.three_tier;

import java.util.List;
import java.util.Random;

/*CLOUDSIM*/
import org.cloudbus.cloudsim.Host;
import org.cloudbus.cloudsim.UtilizationModelFull;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.core.SimEvent;
import edu.boun.edgecloudsim.core.SimManager;
import edu.boun.edgecloudsim.core.SimSettings;

/*CLOUD*/
import edu.boun.edgecloudsim.cloud_server.CloudVM;

/*EDGE*/
import edu.boun.edgecloudsim.edge_orchestrator.EdgeOrchestrator;
import edu.boun.edgecloudsim.edge_server.EdgeVM;
import edu.boun.edgecloudsim.edge_client.CpuUtilizationModel_Custom;
import edu.boun.edgecloudsim.edge_client.Task;

/*MOBILE*/
import edu.boun.edgecloudsim.edge_client.mobile_processing_unit.MobileVM;

/*UTIL*/
import edu.boun.edgecloudsim.utils.SimLogger;

public class ThreetierEdgeOrchestrator extends EdgeOrchestrator {

	private int numberOfHost; // used by load balancer

	public ThreetierEdgeOrchestrator(String _policy, String _simScenario) {
		super(_policy, _simScenario);
	}

	@Override
	public void initialize() {
		numberOfHost = SimSettings.getInstance().getNumOfEdgeHosts();
	}

	/*
	 * (non-Javadoc)
	 * 
	 * @see
	 * edu.boun.edgecloudsim.edge_orchestrator.EdgeOrchestrator#getDeviceToOffload(
	 * edu.boun.edgecloudsim.edge_client.Task)
	 * 
	 */
	@Override
	public int getDeviceToOffload(Task task) {
		int result = 0;

		// dummy task to simulate a task with 1 Mbit file size to upload and download
		Task dummyTask = new Task(0, 0, 0, 0, 128, 128, new UtilizationModelFull(), new UtilizationModelFull(),
				new UtilizationModelFull());

		// Network delay between mobile and cloud
		double wanDelay = SimManager.getInstance().getNetworkModel().getUploadDelay(task.getMobileDeviceId(),
				SimSettings.CLOUD_DATACENTER_ID, dummyTask /* 1 Mbit */);

		// Network bandwidth between mobile and cloud
		double wanBW = (wanDelay == 0) ? 0 : (1 / wanDelay); /* Mbps */

		// Average utilization of the edge server
		double edgeUtilization = SimManager.getInstance().getEdgeServerManager().getAvgUtilization();

		// Offloading decision based on different policies
		if (policy.equals("ONLY_MOBILE")) {
			result = SimSettings.MOBILE_DATACENTER_ID;
		} else if (policy.equals("ONLY_EDGE")) {
			result = SimSettings.GENERIC_EDGE_DEVICE_ID;
		} else if (policy.equals("ONLY_CLOUD")) {
			result = SimSettings.CLOUD_DATACENTER_ID;
		}

		//EDGE_PRIORITY Policy: combination of bandwidth and utilization
		else if (policy.equals("EDGE_PRIORITY")) {
			if (wanBW > 6) {
				if (edgeUtilization > 90) {
					result = SimSettings.CLOUD_DATACENTER_ID;
				} else {
					result = SimSettings.GENERIC_EDGE_DEVICE_ID;
				}
			} else if (wanBW > 3) {
				if (edgeUtilization > 90) {
					result = SimSettings.CLOUD_DATACENTER_ID;
				} else if (edgeUtilization < 20) {
					result = SimSettings.MOBILE_DATACENTER_ID;
				} else {
					result = SimSettings.GENERIC_EDGE_DEVICE_ID;
				}
			} else {
				result = SimSettings.MOBILE_DATACENTER_ID;
			}
		}

		// Utilization-based Policy: only consider edge server's utilization
		else if (policy.equals("UTILIZATION_BASED")) {
			if (edgeUtilization > 80) {
				if (wanBW > 2) {
					result = SimSettings.CLOUD_DATACENTER_ID; // If edge is overloaded and bandwidth is good, offload to
																// cloud
				} else {
					result = SimSettings.MOBILE_DATACENTER_ID; // If edge is overloaded but network is slow, keep task
																// on mobile
				}
			} else {
				result = SimSettings.GENERIC_EDGE_DEVICE_ID; // If edge utilization is acceptable, use edge server
			}
		}

		// Network-based Policy: only consider network delay and bandwidth
		else if (policy.equals("NETWORK_BASED")) {
			if (wanBW > 5) {
				result = SimSettings.CLOUD_DATACENTER_ID; // If network bandwidth is high, offload to cloud
			} else if (wanBW > 2) {
				result = SimSettings.GENERIC_EDGE_DEVICE_ID; // If bandwidth is moderate, offload to edge
			} else {
				result = SimSettings.MOBILE_DATACENTER_ID; // If network is slow, keep the task on mobile
			}
		}


		else if (policy.equals("RANDOM")) {
    		Random rand = new Random();
        	int randomChoice = rand.nextInt(3); // Generate a random number between 0 and 2
        	switch (randomChoice) {
            	case 0:
                	result = SimSettings.MOBILE_DATACENTER_ID;  // Mobile
                	break;
            	case 1:
                	result = SimSettings.GENERIC_EDGE_DEVICE_ID;  // Edge
                	break;
            	case 2:
                	result = SimSettings.CLOUD_DATACENTER_ID;  // Cloud
                	break;
			}
        }

		// Error handling for unknown policy
		else {
			SimLogger.printLine("Unknown edge orchestrator policy! Terminating simulation...");
			System.exit(0);
		}

		return result;
	}

	@Override
	public Vm getVmToOffload(Task task, int deviceId) {
		Vm selectedVM = null;

		if (deviceId == SimSettings.MOBILE_DATACENTER_ID) {
			List<MobileVM> vmArray = SimManager.getInstance().getMobileServerManager()
					.getVmList(task.getMobileDeviceId());
			double requiredCapacity = ((CpuUtilizationModel_Custom) task.getUtilizationModelCpu())
					.predictUtilization(vmArray.get(0).getVmType());
			double targetVmCapacity = (double) 100
					- vmArray.get(0).getCloudletScheduler().getTotalUtilizationOfCpu(CloudSim.clock());

			if (requiredCapacity <= targetVmCapacity)
				selectedVM = vmArray.get(0);
		}

		else if (deviceId == SimSettings.GENERIC_EDGE_DEVICE_ID) {
			// Select VM on edge devices via Least Loaded algorithm!
			double selectedVmCapacity = 0; // start with min value
			for (int hostIndex = 0; hostIndex < numberOfHost; hostIndex++) {
				List<EdgeVM> vmArray = SimManager.getInstance().getEdgeServerManager().getVmList(hostIndex);
				for (int vmIndex = 0; vmIndex < vmArray.size(); vmIndex++) {
					double requiredCapacity = ((CpuUtilizationModel_Custom) task.getUtilizationModelCpu())
							.predictUtilization(vmArray.get(vmIndex).getVmType());
					double targetVmCapacity = (double) 100
							- vmArray.get(vmIndex).getCloudletScheduler().getTotalUtilizationOfCpu(CloudSim.clock());
					if (requiredCapacity <= targetVmCapacity && targetVmCapacity > selectedVmCapacity) {
						selectedVM = vmArray.get(vmIndex);
						selectedVmCapacity = targetVmCapacity;
					}
				}
			}
		}

		else if (deviceId == SimSettings.CLOUD_DATACENTER_ID) {
			// Select VM on cloud devices via Least Loaded algorithm!
			double selectedVmCapacity = 0; // start with min value
			List<Host> list = SimManager.getInstance().getCloudServerManager().getDatacenter().getHostList();
			for (int hostIndex = 0; hostIndex < list.size(); hostIndex++) {
				List<CloudVM> vmArray = SimManager.getInstance().getCloudServerManager().getVmList(hostIndex);
				for (int vmIndex = 0; vmIndex < vmArray.size(); vmIndex++) {
					double requiredCapacity = ((CpuUtilizationModel_Custom) task.getUtilizationModelCpu())
							.predictUtilization(vmArray.get(vmIndex).getVmType());
					double targetVmCapacity = (double) 100
							- vmArray.get(vmIndex).getCloudletScheduler().getTotalUtilizationOfCpu(CloudSim.clock());
					if (requiredCapacity <= targetVmCapacity && targetVmCapacity > selectedVmCapacity) {
						selectedVM = vmArray.get(vmIndex);
						selectedVmCapacity = targetVmCapacity;
					}
				}
			}
		}

		else {
			SimLogger.printLine("Unknown device id! The simulation has been terminated.");
			System.exit(0);
		}

		return selectedVM;
	}

	@Override
	public void processEvent(SimEvent arg0) {
		// Nothing to do!
	}

	@Override
	public void shutdownEntity() {
		// Nothing to do!
	}

	@Override
	public void startEntity() {
		// Nothing to do!
	}

}