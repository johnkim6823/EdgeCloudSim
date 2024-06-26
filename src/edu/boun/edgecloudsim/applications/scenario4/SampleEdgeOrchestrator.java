/*
 * Title:        EdgeCloudSim - Edge Orchestrator
 * 
 * Description: 
 * SampleEdgeOrchestrator offloads tasks to proper server
 * based on the applied scenario
 * 
 * Licence:      GPL - http://www.gnu.org/copyleft/gpl.html
 * Copyright (c) 2022, Bogazici University, Istanbul, Turkey
 */

package edu.boun.edgecloudsim.applications.scenario4;

import java.util.List;

import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.core.SimEvent;

import edu.boun.edgecloudsim.core.SimManager;
import edu.boun.edgecloudsim.core.SimSettings;
import edu.boun.edgecloudsim.edge_orchestrator.EdgeOrchestrator;
import edu.boun.edgecloudsim.edge_server.EdgeVM;
import edu.boun.edgecloudsim.edge_client.Task;
import edu.boun.edgecloudsim.utils.Location;
import edu.boun.edgecloudsim.utils.SimLogger;

public class SampleEdgeOrchestrator extends EdgeOrchestrator {
	
	public SampleEdgeOrchestrator(String _policy, String _simScenario) {
		super(_policy, _simScenario);
	}

	@Override
	public void initialize() {
	}

	/*
	 * (non-Javadoc)
	 * @see edu.boun.edgecloudsim.edge_orchestrator.EdgeOrchestrator#getDeviceToOffload(edu.boun.edgecloudsim.edge_client.Task)
	 * 
	 * It is assumed that the edge orchestrator app is running on the edge devices in a distributed manner
	 */
	@Override
	public int getDeviceToOffload(Task task) {
		int result = 0;

		//in this scenario, we can only offload to edge servers'
		result = SimSettings.GENERIC_EDGE_DEVICE_ID;

		return result;
	}

	@Override
	public Vm getVmToOffload(Task task, int deviceId) {
		Vm selectedVM = null;
		
		//in this scenario, clients can only offload to edge servers located in the serving WLAN place
		//serving wlan ID is equal to the host id because there is only one host in one place
		if(deviceId == SimSettings.GENERIC_EDGE_DEVICE_ID){
			Location deviceLocation = SimManager.getInstance().getMobilityModel().getLocation(task.getMobileDeviceId(), CloudSim.clock());
			int relatedHostId=deviceLocation.getServingWlanId();
			
			List<EdgeVM> vmArray = SimManager.getInstance().getEdgeServerManager().getVmList(relatedHostId);
			
			//use least loaded policy (WORST FIT) to select VM on Host located in the serving WLAN place
			double selectedVmCapacity = 0; //start with min value
			for(int vmIndex=0; vmIndex<vmArray.size(); vmIndex++){
				double requiredCapacity = ((SampleCpuUtilizationModel)task.getUtilizationModelCpu()).predictUtilization(vmArray.get(vmIndex));
				double targetVmCapacity = (double)100 - vmArray.get(vmIndex).getCloudletScheduler().getTotalUtilizationOfCpu(CloudSim.clock());
				if(requiredCapacity <= targetVmCapacity && targetVmCapacity > selectedVmCapacity){
					selectedVM = vmArray.get(vmIndex);
					selectedVmCapacity = targetVmCapacity;
				}
			}
		}

		else{
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