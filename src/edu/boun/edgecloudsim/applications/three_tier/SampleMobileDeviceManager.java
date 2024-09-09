/*
 * Title:        EdgeCloudSim - Mobile Device Manager
 * 
 * Description: 
 * Mobile Device Manager is one of the most important component
 * in EdgeCloudSim. It is responsible for creating the tasks,
 * submitting them to the related VM with respect to the
 * Edge Orchestrator decision, and takes proper actions when
 * the execution of the tasks are finished. It also feeds the
 * SimLogger with the relevant results.

 * SampleMobileDeviceManager sends tasks to the edge servers or
 * cloud servers. The mobile devices use WAN if the tasks are
 * offloaded to the edge servers. On the other hand, they use WLAN
 * if the target server is an edge server. Finally, the mobile
 * devices use MAN if they must be served by a remote edge server
 * due to the congestion at their own location. In this case,
 * they access the edge server via two hops where the packets
 * must go through WLAN and MAN.
 * 
 * If you want to use different topology, you should modify
 * the flow implemented in this class.
 * 
 * Licence:      GPL - http://www.gnu.org/copyleft/gpl.html
 * Copyright (c) 2017, Bogazici University, Istanbul, Turkey
 */

package edu.boun.edgecloudsim.applications.three_tier;

import org.cloudbus.cloudsim.UtilizationModel;
import org.cloudbus.cloudsim.UtilizationModelFull;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.core.CloudSimTags;
import org.cloudbus.cloudsim.core.SimEvent;

import edu.boun.edgecloudsim.core.SimManager;
import edu.boun.edgecloudsim.core.SimSettings;
import edu.boun.edgecloudsim.core.SimSettings.NETWORK_DELAY_TYPES;
import edu.boun.edgecloudsim.core.SimSettings.VM_TYPES;
import edu.boun.edgecloudsim.edge_client.CpuUtilizationModel_Custom;
import edu.boun.edgecloudsim.edge_client.MobileDeviceManager;
import edu.boun.edgecloudsim.edge_client.Task;
import edu.boun.edgecloudsim.edge_server.EdgeHost;
import edu.boun.edgecloudsim.edge_server.EdgeVM;
import edu.boun.edgecloudsim.network.NetworkModel;
import edu.boun.edgecloudsim.utils.TaskProperty;
import edu.boun.edgecloudsim.utils.Location;
import edu.boun.edgecloudsim.utils.SimLogger;

public class SampleMobileDeviceManager extends MobileDeviceManager {
	private static final int BASE = 100000; // start from base in order not to conflict cloudsim tag!

	private static final int UPDATE_MM1_QUEUE_MODEL = BASE + 1;

	private static final int REQUEST_RECEIVED_BY_MOBILE_DEVICE = BASE + 2;
	private static final int REQUEST_RECEIVED_BY_CLOUD = BASE + 3;
	private static final int REQUEST_RECEIVED_BY_EDGE_DEVICE = BASE + 4;
	private static final int REQUEST_RECEIVED_BY_REMOTE_EDGE_DEVICE = BASE + 5;
	private static final int REQUEST_RECEIVED_BY_EDGE_DEVICE_TO_RELAY_NEIGHBOR = BASE + 6;
	private static final int RESPONSE_RECEIVED_BY_MOBILE_DEVICE = BASE + 7;
	private static final int RESPONSE_RECEIVED_BY_EDGE_DEVICE_TO_RELAY_MOBILE_DEVICE = BASE + 8;

	private static final double MM1_QUEUE_MODEL_UPDATE_INTEVAL = 5; // seconds

	private int taskIdCounter = 0;

	public SampleMobileDeviceManager() throws Exception {
	}

	@Override
	public void initialize() {
	}

	@Override
	public UtilizationModel getCpuUtilizationModel() {
		return new CpuUtilizationModel_Custom();
	}

	@Override
	public void startEntity() {
		super.startEntity();
		schedule(getId(), SimSettings.CLIENT_ACTIVITY_START_TIME +
				MM1_QUEUE_MODEL_UPDATE_INTEVAL, UPDATE_MM1_QUEUE_MODEL);
	}

	/**
	 * Submit cloudlets to the created VMs.
	 * 
	 * @pre $none
	 * @post $none
	 */
	protected void submitCloudlets() {
		// do nothing!
	}

	/**
	 * Process a cloudlet return event.
	 * 
	 * @param ev a SimEvent object
	 * @pre ev != $null
	 * @post $none
	 */
	protected void processCloudletReturn(SimEvent ev) {
		NetworkModel networkModel = SimManager.getInstance().getNetworkModel();
		Task task = (Task) ev.getData();

		SimLogger.getInstance().taskExecuted(task.getCloudletId());

		if (task.getAssociatedDatacenterId() == SimSettings.CLOUD_DATACENTER_ID) {
			// Handle the case where the task is from the cloud datacenter
			double WanDelay = networkModel.getDownloadDelay(SimSettings.CLOUD_DATACENTER_ID, task.getMobileDeviceId(),
					task);
			if (WanDelay > 0) {
				Location currentLocation = SimManager.getInstance().getMobilityModel()
						.getLocation(task.getMobileDeviceId(), CloudSim.clock() + WanDelay);
				if (task.getSubmittedLocation().getServingWlanId() == currentLocation.getServingWlanId()) {
					networkModel.downloadStarted(task.getSubmittedLocation(), SimSettings.CLOUD_DATACENTER_ID);
					SimLogger.getInstance().setDownloadDelay(task.getCloudletId(), WanDelay,
							NETWORK_DELAY_TYPES.WAN_DELAY);
					schedule(getId(), WanDelay, RESPONSE_RECEIVED_BY_MOBILE_DEVICE, task);
				} else {
					SimLogger.getInstance().failedDueToMobility(task.getCloudletId(), CloudSim.clock());
				}
			} else {
				SimLogger.getInstance().failedDueToBandwidth(task.getCloudletId(), CloudSim.clock(),
						NETWORK_DELAY_TYPES.WAN_DELAY);
			}
		} else if (task.getAssociatedDatacenterId() == SimSettings.GENERIC_EDGE_DEVICE_ID) {
			// Handle the case where the task is from a generic edge device
			double delay = networkModel.getDownloadDelay(task.getAssociatedDatacenterId(), task.getMobileDeviceId(),
					task);

			if (delay > 0) {
				Location currentLocation = SimManager.getInstance().getMobilityModel()
						.getLocation(task.getMobileDeviceId(), CloudSim.clock() + delay);
				if (task.getSubmittedLocation().getServingWlanId() == currentLocation.getServingWlanId()) {
					networkModel.downloadStarted(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID);
					SimLogger.getInstance().setDownloadDelay(task.getCloudletId(), delay,
							NETWORK_DELAY_TYPES.WLAN_DELAY);
					schedule(getId(), delay, RESPONSE_RECEIVED_BY_MOBILE_DEVICE, task);
				} else {
					SimLogger.getInstance().failedDueToMobility(task.getCloudletId(), CloudSim.clock());
				}
			} else {
				SimLogger.getInstance().failedDueToBandwidth(task.getCloudletId(), CloudSim.clock(),
						NETWORK_DELAY_TYPES.WLAN_DELAY);
			}
		} else if (task.getAssociatedDatacenterId() == SimSettings.MOBILE_DATACENTER_ID) {
			// Handle the case where the task is from a mobile datacenter
			SimLogger.getInstance().taskEnded(task.getCloudletId(), CloudSim.clock());

		} else {
			// Handle unknown datacenter ID
			SimLogger.printLine("Unknown datacenter id! Terminating simulation...");
			System.exit(0);
		}
	}

	protected void processOtherEvent(SimEvent ev) {
		if (ev == null) {
			SimLogger.printLine(
					getName() + ".processOtherEvent(): " + "Error - an event is null! Terminating simulation...");
			System.exit(0);
			return;
		}

		NetworkModel networkModel = SimManager.getInstance().getNetworkModel();

		switch (ev.getTag()) {
			case UPDATE_MM1_QUEUE_MODEL: {
				((SampleNetworkModel) networkModel).updateMM1QueeuModel();
				schedule(getId(), MM1_QUEUE_MODEL_UPDATE_INTEVAL, UPDATE_MM1_QUEUE_MODEL);
				break;
			}
			case REQUEST_RECEIVED_BY_MOBILE_DEVICE: {
				Task task = (Task) ev.getData();
				submitTaskToVm(task, SimSettings.VM_TYPES.MOBILE_VM);
				break;
			}
			case REQUEST_RECEIVED_BY_CLOUD: {
				Task task = (Task) ev.getData();
				networkModel.uploadFinished(task.getSubmittedLocation(), SimSettings.CLOUD_DATACENTER_ID);
				submitTaskToVm(task, SimSettings.VM_TYPES.CLOUD_VM);
				break;
			}
			case REQUEST_RECEIVED_BY_EDGE_DEVICE: {
				Task task = (Task) ev.getData();
				networkModel.uploadFinished(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID);
				submitTaskToVm(task, SimSettings.VM_TYPES.EDGE_VM);
				break;
			}
			case REQUEST_RECEIVED_BY_REMOTE_EDGE_DEVICE: {
				Task task = (Task) ev.getData();
				networkModel.uploadFinished(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID + 1);
				submitTaskToVm(task, SimSettings.VM_TYPES.EDGE_VM);
				break;
			}
			case REQUEST_RECEIVED_BY_EDGE_DEVICE_TO_RELAY_NEIGHBOR: {
				Task task = (Task) ev.getData();
				networkModel.uploadFinished(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID);

				double manDelay = networkModel.getUploadDelay(SimSettings.GENERIC_EDGE_DEVICE_ID,
						SimSettings.GENERIC_EDGE_DEVICE_ID, task);
				if (manDelay > 0) {
					networkModel.uploadStarted(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID + 1);
					SimLogger.getInstance().setUploadDelay(task.getCloudletId(), manDelay,
							NETWORK_DELAY_TYPES.MAN_DELAY);
					schedule(getId(), manDelay, REQUEST_RECEIVED_BY_REMOTE_EDGE_DEVICE, task);
				} else {
					SimLogger.getInstance().rejectedDueToBandwidth(task.getCloudletId(), CloudSim.clock(),
							SimSettings.VM_TYPES.EDGE_VM.ordinal(), NETWORK_DELAY_TYPES.MAN_DELAY);
				}
				break;
			}
			case RESPONSE_RECEIVED_BY_EDGE_DEVICE_TO_RELAY_MOBILE_DEVICE: {
				Task task = (Task) ev.getData();
				networkModel.downloadFinished(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID + 1);

				double delay = networkModel.getDownloadDelay(task.getAssociatedHostId(), task.getMobileDeviceId(),
						task);
				if (delay > 0) {
					Location currentLocation = SimManager.getInstance().getMobilityModel()
							.getLocation(task.getMobileDeviceId(), CloudSim.clock() + delay);
					if (task.getSubmittedLocation().getServingWlanId() == currentLocation.getServingWlanId()) {
						networkModel.downloadStarted(currentLocation, SimSettings.GENERIC_EDGE_DEVICE_ID);
						SimLogger.getInstance().setDownloadDelay(task.getCloudletId(), delay,
								NETWORK_DELAY_TYPES.WLAN_DELAY);
						schedule(getId(), delay, RESPONSE_RECEIVED_BY_MOBILE_DEVICE, task);
					} else {
						SimLogger.getInstance().failedDueToMobility(task.getCloudletId(), CloudSim.clock());
					}
				} else {
					SimLogger.getInstance().failedDueToBandwidth(task.getCloudletId(), CloudSim.clock(),
							NETWORK_DELAY_TYPES.WLAN_DELAY);
				}
				break;
			}
			case RESPONSE_RECEIVED_BY_MOBILE_DEVICE: {
				Task task = (Task) ev.getData();
				if (task.getAssociatedDatacenterId() == SimSettings.CLOUD_DATACENTER_ID) {
					networkModel.downloadFinished(task.getSubmittedLocation(), SimSettings.CLOUD_DATACENTER_ID);
				} else {
					networkModel.downloadFinished(task.getSubmittedLocation(), SimSettings.GENERIC_EDGE_DEVICE_ID);
				}
				SimLogger.getInstance().taskEnded(task.getCloudletId(), CloudSim.clock());
				break;
			}

			default: {
				SimLogger.printLine(getName() + ".processOtherEvent(): "
						+ "Error - event unknown by this DatacenterBroker. Terminating simulation...");
				System.exit(0);
				break;
			}
		}
	}

	public void submitTask(TaskProperty edgeTask) {
		double delay = 0;
		int nextEvent = 0;
		int nextDeviceForNetworkModel = 0;
		VM_TYPES vmType = null;
		NETWORK_DELAY_TYPES delayType = null;

		NetworkModel networkModel = SimManager.getInstance().getNetworkModel();

		// Create a task
		Task task = createTask(edgeTask);

		// Get the current location of the mobile device
		Location currentLocation = SimManager.getInstance().getMobilityModel().getLocation(task.getMobileDeviceId(),
				CloudSim.clock());

		// Set the location of the mobile device that generated this task
		task.setSubmittedLocation(currentLocation);

		// Add the task to the log list
		SimLogger.getInstance().addLog(task.getMobileDeviceId(),
				task.getCloudletId(),
				task.getTaskType(),
				(int) task.getCloudletLength(),
				(int) task.getCloudletFileSize(),
				(int) task.getCloudletOutputSize());

		// Determine the next hop (destination) for offloading the task
		int nextHopId = SimManager.getInstance().getEdgeOrchestrator().getDeviceToOffload(task);

		// Determine the next hop and corresponding delay
		if (nextHopId == SimSettings.CLOUD_DATACENTER_ID) {
			delay = networkModel.getUploadDelay(task.getMobileDeviceId(), SimSettings.CLOUD_DATACENTER_ID, task);
			vmType = SimSettings.VM_TYPES.CLOUD_VM;
			nextEvent = REQUEST_RECEIVED_BY_CLOUD;
			delayType = NETWORK_DELAY_TYPES.WAN_DELAY;
			nextDeviceForNetworkModel = SimSettings.CLOUD_DATACENTER_ID;
		} else if (nextHopId == SimSettings.GENERIC_EDGE_DEVICE_ID) {
			delay = networkModel.getUploadDelay(task.getMobileDeviceId(), nextHopId, task);
			vmType = SimSettings.VM_TYPES.EDGE_VM;
			nextEvent = REQUEST_RECEIVED_BY_EDGE_DEVICE;
			delayType = NETWORK_DELAY_TYPES.WLAN_DELAY;
			nextDeviceForNetworkModel = SimSettings.GENERIC_EDGE_DEVICE_ID;
		} else if (nextHopId == SimSettings.MOBILE_DATACENTER_ID) {
			vmType = VM_TYPES.MOBILE_VM;
			nextEvent = REQUEST_RECEIVED_BY_MOBILE_DEVICE;
			// TODO: Handle D2D communication and D2D delay if required.
		} else {
			SimLogger.printLine("Unknown nextHopId! Terminating simulation...");
			System.exit(0);
		}

		// If there is a valid delay or the next hop is the mobile datacenter
		if (delay > 0 || nextHopId == SimSettings.MOBILE_DATACENTER_ID) {
			// Get the VM to offload the task to
			Vm selectedVM = SimManager.getInstance().getEdgeOrchestrator().getVmToOffload(task, nextHopId);

			if (selectedVM != null) {
				// Set associated datacenter, host, and VM IDs
				task.setAssociatedDatacenterId(nextHopId);
				task.setAssociatedHostId(selectedVM.getHost().getId());
				task.setAssociatedVmId(selectedVM.getId());

				// Bind the task to the VM and add it to the cloudlet list
				getCloudletList().add(task);
				bindCloudletToVm(task.getCloudletId(), selectedVM.getId());

				// If the task is offloaded to an Edge VM, check if the device is a neighbor
				if (selectedVM instanceof EdgeVM) {
					EdgeHost host = (EdgeHost) (selectedVM.getHost());
					if (host.getLocation().getServingWlanId() != task.getSubmittedLocation().getServingWlanId()) {
						nextEvent = REQUEST_RECEIVED_BY_EDGE_DEVICE_TO_RELAY_NEIGHBOR;
					}
				}

				// Start upload process if offloading to a non-mobile datacenter
				if (nextHopId != SimSettings.MOBILE_DATACENTER_ID) {
					networkModel.uploadStarted(task.getSubmittedLocation(), nextDeviceForNetworkModel);
					SimLogger.getInstance().setUploadDelay(task.getCloudletId(), delay, delayType);
				}

				// Log the task start and schedule the next event
				SimLogger.getInstance().taskStarted(task.getCloudletId(), CloudSim.clock());
				schedule(getId(), delay, nextEvent, task);
			} else {
				// If no VM is available to offload the task
				SimLogger.getInstance().rejectedDueToVMCapacity(task.getCloudletId(), CloudSim.clock(),
						vmType.ordinal());
			}
		} else {
			// If the task is rejected due to insufficient bandwidth
			SimLogger.getInstance().rejectedDueToBandwidth(task.getCloudletId(), CloudSim.clock(), vmType.ordinal(),
					delayType);
		}
	}

	private void submitTaskToVm(Task task, SimSettings.VM_TYPES vmType) {
		// 로그 출력: 클라우드렛이 특정 VM에 제출됨
		// SimLogger.printLine(CloudSim.clock() + ": Cloudlet#" + task.getCloudletId() + " is submitted to VM#" + task.getVmId());
		
		// 클라우드렛을 VM에 제출하는 이벤트 스케줄링
		schedule(getVmsToDatacentersMap().get(task.getVmId()), 0, CloudSimTags.CLOUDLET_SUBMIT, task);
	
		// 로그 기록: 태스크가 특정 VM에 할당됨
		SimLogger.getInstance().taskAssigned(task.getCloudletId(),
				task.getAssociatedDatacenterId(),
				task.getAssociatedHostId(),
				task.getAssociatedVmId(),
				vmType.ordinal());
	}
	
	private Task createTask(TaskProperty edgeTask) {
		// CPU 사용 모델 및 기타 자원 사용 모델을 설정
		UtilizationModel utilizationModel = new UtilizationModelFull(); // 자원 사용 모델 설정
		UtilizationModel utilizationModelCPU = getCpuUtilizationModel();
	
		// 태스크 생성: edgeTask 속성에 기반하여 Task 객체 생성
		Task task = new Task(edgeTask.getMobileDeviceId(), ++taskIdCounter,
				edgeTask.getLength(), edgeTask.getPesNumber(),
				edgeTask.getInputFileSize(), edgeTask.getOutputFileSize(),
				utilizationModelCPU, utilizationModel, utilizationModel);
	
		// 태스크 소유자 설정 (사용자 ID)
		task.setUserId(this.getId());
		task.setTaskType(edgeTask.getTaskType());
	
		// 커스텀 CPU 사용 모델이 있는 경우, 해당 모델에 태스크 정보 설정
		if (utilizationModelCPU instanceof CpuUtilizationModel_Custom) {
			((CpuUtilizationModel_Custom) utilizationModelCPU).setTask(task);
		}
	
		// 태스크 반환
		return task;
	}
	
}