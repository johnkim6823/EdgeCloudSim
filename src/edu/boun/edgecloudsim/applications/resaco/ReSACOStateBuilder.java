/*
 * Title:        EdgeCloudSim - ReSACO State Builder
 *
 * Description:
 * Builds the state vector s_t = (L, U, D, mu_d, mu_e1..mu_eN, mu_c,
 * b_wlan, b_man, b_wan) described in Section IV-A-2 of the ReSACO paper,
 * so it can be sent to the Python inference/online-learning bridge
 * (ReSACO/bridge/inference_server.py). The edge utilization slots are
 * filled with the network-wide average edge utilization (rather than one
 * slot per physical edge host) so this stays valid regardless of how many
 * edge hosts edge_devices.xml actually defines; RESACO_NUM_EDGE_SLOTS must
 * match resaco/config.py's NUM_EDGE_SERVERS for the state vector length to
 * line up with the trained network.
 *
 * Licence:      GPL - http://www.gnu.org/copyleft/gpl.html
 */

package edu.boun.edgecloudsim.applications.resaco;

import java.util.List;

import org.cloudbus.cloudsim.core.CloudSim;

import edu.boun.edgecloudsim.core.SimManager;
import edu.boun.edgecloudsim.core.SimSettings;
import edu.boun.edgecloudsim.edge_client.Task;
import edu.boun.edgecloudsim.edge_client.mobile_processing_unit.MobileVM;

public class ReSACOStateBuilder {
	public static final int RESACO_NUM_EDGE_SLOTS = 10;
	/** Must match resaco/config.py's TMAX_SECONDS (network failure delay threshold, Eq. 2/9). */
	public static final double RESACO_TMAX_SECONDS = 5.0;

	/**
	 * ReSACOMainApp reuses the same JVM (and the same long-lived bridge
	 * connection/replay buffer) across many scenario runs (device count x
	 * scenario x policy loops), each of which starts a fresh SimManager and
	 * resets its own Task cloudlet-id counter back to 1. Scoping the bridge
	 * request id by the current SimManager's identity prevents cloudlet id
	 * "1" from a new run colliding with an in-flight (never-completed, e.g.
	 * still airborne when the previous scenario's simulation clock hit
	 * STOP_SIMULATION) request id "1" left over from an earlier run.
	 */
	public static String requestIdFor(Task task) {
		return System.identityHashCode(SimManager.getInstance()) + "-" + task.getCloudletId();
	}

	public static double[] buildStateForTask(Task task) {
		return build(task.getCloudletLength(), task.getCloudletFileSize(), task.getCloudletOutputSize(),
				mobileUtilization(task.getMobileDeviceId()));
	}

	public static double[] buildStateForDevice(int mobileDeviceId) {
		// no in-flight task known (used when reporting an outcome's "next state"),
		// so approximate L/U/D with zero -- only the utilization/network fields matter there.
		return build(0, 0, 0, mobileUtilization(mobileDeviceId));
	}

	private static double mobileUtilization(int mobileDeviceId) {
		List<MobileVM> vmArray = SimManager.getInstance().getMobileServerManager().getVmList(mobileDeviceId);
		if (vmArray == null || vmArray.isEmpty()) {
			return 0;
		}
		return vmArray.get(0).getCloudletScheduler().getTotalUtilizationOfCpu(CloudSim.clock());
	}

	private static double[] build(double length, double upload, double download, double mobileUtilization) {
		double edgeUtilization = SimManager.getInstance().getEdgeServerManager().getAvgUtilization();
		double cloudUtilization = SimManager.getInstance().getCloudServerManager().getAvgUtilization();
		SimSettings settings = SimSettings.getInstance();

		double[] state = new double[4 + RESACO_NUM_EDGE_SLOTS + 1 + 3];
		int i = 0;
		state[i++] = length;
		state[i++] = upload;
		state[i++] = download;
		state[i++] = mobileUtilization;
		for (int e = 0; e < RESACO_NUM_EDGE_SLOTS; e++) {
			state[i++] = edgeUtilization;
		}
		state[i++] = cloudUtilization;
		// SimSettings.getXxxBandwidth()'s JavaDoc claims "Mbps unit" but that's
		// stale -- the underlying BANDWITH_XXX fields are the config file's Mbps
		// value pre-multiplied by 1000 for internal Kbps-based delay math (see
		// SimSettings.java's loadSimulationParameters() and
		// ThreeTierNetworkModel.calculateMM1()'s explicit /*Kbps*/ comment).
		// resaco/config.py's *_BANDWIDTH_MBPS constants (and everything trained
		// against them, including resaco/normalize.py's fixed scale factors) are
		// in Mbps, so without the /1000.0 here every b_wlan/b_man/b_wan value
		// reaching the trained policy would be ~1000x anything it ever saw
		// during training.
		state[i++] = settings.getWlanBandwidth() / 1000.0;
		state[i++] = settings.getManBandwidth() / 1000.0;
		state[i++] = settings.getWanBandwidth() / 1000.0;
		return state;
	}
}
