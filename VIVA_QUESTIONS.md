# Cloud Server Load Balancing Simulator
## Viva Voce & Oral Examination Preparation Guide

This guide contains **25 essential viva voce and oral defense questions** with clear, concise, and technically sound answers tailored for a Computer Systems Engineering student.

---

### Section 1: Fundamental Cloud & Distributed Computing Concepts

#### Q1: What is load balancing?
**Answer:** Load balancing is the practice of distributing incoming network or application traffic across multiple backend compute servers (nodes). The goal is to optimize resource utilization, maximize throughput, minimize latency, and prevent any individual server from becoming a performance bottleneck or failing under heavy load.

#### Q2: What is the difference between Cloud Computing and Distributed Computing?
**Answer:**
* **Distributed Computing:** The overarching architectural paradigm where multiple independent physical or virtual machines communicate over a network to solve computational tasks collaboratively as a single unified system.
* **Cloud Computing:** A practical, service-oriented delivery model built on top of distributed systems that provides on-demand, metered access to pooled computing resources (e.g., VMs, storage, networking) over the Internet with elasticity and self-service provisioning (e.g., AWS, GCP, Azure).

#### Q3: Why is load balancing essential in cloud datacenters?
**Answer:** In cloud environments, traffic is dynamic and multi-tenant. Load balancers enable **elastic horizontal scaling**—allowing servers to be added or removed without disrupting client access. They also provide high availability by detecting failed nodes and rerouting traffic exclusively to healthy servers.

#### Q4: What is the difference between Static and Dynamic load balancing?
**Answer:**
* **Static Load Balancing:** Uses fixed, predefined rules to route requests without inspecting real-time server conditions or current workload state (e.g., Round Robin, Random selection).
* **Dynamic Load Balancing:** Monitors active server states—such as current CPU utilization, active connection count, or accumulated backlog—and routes requests to the server best equipped to handle them (e.g., Least Connections, Least Loaded).

#### Q5: At which OSI layers do load balancers operate?
**Answer:**
* **Layer 4 (Transport Layer):** Routes packets based on IP addresses and TCP/UDP ports without reading application payload data (fast, high throughput, e.g., AWS Network Load Balancer).
* **Layer 7 (Application Layer):** Inspects application payloads—such as HTTP headers, cookies, URL paths, and request parameters—to make content-aware routing decisions (e.g., AWS Application Load Balancer, NGINX).

---

### Section 2: Load Balancing Mechanics & Algorithms

#### Q6: How does Round Robin scheduling work?
**Answer:** Round Robin assigns incoming tasks sequentially in cyclic order across an ordered list of $N$ servers using the modulo operator:
$$\text{Server}(i) = \text{Servers}[i \pmod N]$$
For example, across 3 servers, tasks 0, 1, 2, 3, 4, 5 route to Server 1, Server 2, Server 3, Server 1, Server 2, Server 3, respectively. It guarantees equal request counts per server but ignores request execution durations.

#### Q7: How does Least Loaded scheduling work?
**Answer:** Least Loaded inspects the accumulated processing workload of every server immediately before a request arrives and routes the request to whichever server currently has the smallest accumulated workload:
$$\text{Server}(i) = \arg\min_{s \in \text{Servers}} (\text{Workload}_s)$$
This actively directs compute-heavy requests away from busy servers to idle or lightly loaded nodes.

#### Q8: How does your implementation resolve ties in the Least Loaded algorithm?
**Answer:** Ties are resolved **deterministically** using server declaration order. When multiple servers share the identical minimum workload (e.g., at startup when all servers have 0 ms), the algorithm always selects the first server in the list (`Server 1`, then `Server 2`, then `Server 3`). This prevents non-deterministic race conditions and ensures reproducible results.

#### Q9: What is the computational time complexity of both algorithms?
**Answer:**
* **Round Robin:** $\mathcal{O}(1)$ time per request, yielding $\mathcal{O}(M)$ for $M$ requests.
* **Least Loaded:** $\mathcal{O}(N)$ time per request to search across $N$ servers, yielding $\mathcal{O}(M \times N)$ for $M$ requests. For small clusters ($N \le 10$), execution is practically instantaneous.

#### Q10: What is Weighted Round Robin (WRR) and when is it used?
**Answer:** Weighted Round Robin assigns servers proportional quotas based on their hardware capacities (e.g., a 4-core server gets weight 2, an 8-core server gets weight 4). It is essential in **heterogeneous clusters** where servers have differing CPU speeds and memory sizes.

---

### Section 3: Dataset, Simulation & Experimental Setup

#### Q11: Why did you use an empirical dataset instead of purely random numbers?
**Answer:** Real-world cloud workloads do not follow uniform distributions. The provided 1,000-request dataset captures realistic operational traits:
1. **Variance:** Processing durations span from 30 ms up to 799 ms ($> 26\times$ spread).
2. **Task Categorization:** Distinct request types (`API_Read`, `File_Upload`, `Report_Generation`, `Database_Query`).
3. **Reproducibility:** A fixed trace ensures that benchmark comparisons between Round Robin and Least Loaded are strictly repeatable and scientifically verifiable.

#### Q12: What fields are present in your workload dataset?
**Answer:**
1. `Request_ID`: Unique task identifier (e.g., `REQ0001`).
2. `Arrival_Time`: Timestamp of request arrival.
3. `Request_Type`: Operational classification of the workload.
4. `Processing_Time_ms`: CPU burst duration required to execute the request (in milliseconds).
5. `Data_Size_MB`: Payload size transferred with the request (in megabytes).

#### Q13: What validation checks are performed on the dataset?
**Answer:** Before simulation, the data ingestion pipeline verifies:
* All 5 required column headers exist.
* Zero null or missing values exist (no silent imputation).
* All 1,000 `Request_ID`s are completely unique (no duplicate requests).
* `Processing_Time_ms` values are valid numeric integers $> 0$.
* `Data_Size_MB` values are valid floats $\ge 0$.

#### Q14: What is the total workload and request count in your verified dataset?
**Answer:** The dataset contains exactly **1,000 requests** with a cumulative execution workload of **195,367 milliseconds** (~195.37 seconds of CPU execution). The mean duration is **195.37 ms**, and the median is **118.00 ms**.

#### Q15: Why can simulation results differ if a different dataset is used?
**Answer:** The performance difference between Round Robin and Least Loaded depends directly on the **variance of request processing times**:
* If all requests in a dataset have identical runtimes (e.g., exactly 100 ms each), Round Robin and Least Loaded will produce identical, perfectly balanced workloads (0 ms imbalance).
* If a dataset exhibits extreme burstiness or long-tail task durations (e.g., Pareto or Weibull distribution), Round Robin's workload imbalance increases dramatically, making Least Loaded's dynamic steering even more impactful.

---

### Section 4: Metrics, Calculations & Edge Cases

#### Q16: What is workload imbalance, and how is it calculated?
**Answer:** Workload imbalance measures the disparity in total computational burden between the most overloaded server and the least loaded server in a cluster:
$$\text{Load Imbalance } (\Delta W) = W_{\max} - W_{\min}$$
In our verified 3-server benchmark:
* **Round Robin:** $67,379\text{ ms} - 63,127\text{ ms} = \mathbf{4,252\text{ ms}}$
* **Least Loaded:** $65,396\text{ ms} - 64,981\text{ ms} = \mathbf{415\text{ ms}}$

#### Q17: What does "Estimated Makespan" mean in this simulation?
**Answer:** Makespan is the total elapsed time required to complete the entire batch of requests. In our static concurrent model, where all servers execute their assigned tasks in parallel, the makespan is bounded by the slowest, most burdened server:
$$\text{Estimated Makespan} = W_{\max} = \max_{s \in \text{Servers}} (W_s)$$
Least Loaded reduced estimated makespan from **67,379 ms** to **65,396 ms** (a reduction of 1,983 ms).

#### Q18: How is the load imbalance reduction percentage calculated?
**Answer:** It calculates how much the workload spread was reduced relative to Round Robin:
$$\text{Reduction \%} = \frac{\Delta W_{\text{RR}} - \Delta W_{\text{LL}}}{\Delta W_{\text{RR}}} \times 100\%$$
Using our verified numbers:
$$\frac{4,252 - 415}{4,252} \times 100\% = \mathbf{90.24\%}$$
If the baseline imbalance $\Delta W_{\text{RR}} \le 0$, the function returns `None` to prevent division-by-zero errors.

#### Q19: What correctness guarantees does your simulator mathematically verify?
**Answer:** Our `verify_simulation_correctness` engine validates four formal constraints:
1. **Single Assignment:** Every request is assigned to exactly one server ($1,000 / 1,000$).
2. **Zero Loss/Duplication:** Output set of `Request_ID`s strictly equals the input set.
3. **Workload Conservation:** $\sum \text{Server Loads} = 195,367\text{ ms} = \sum \text{Input Request Times}$.
4. **Assignment Sum Match:** The load attributed to each server matches the exact sum of its assigned task durations.

#### Q20: How does your code handle edge cases like 1 server or an empty dataset?
**Answer:**
* **1 Server:** All requests route to Server 1; $W_{\max} = W_{\min}$, so imbalance is $0\text{ ms}$, and reduction safely returns `None`.
* **Empty Dataset:** Returns an empty assignments table with preserved schema and 0 ms load across all servers without crashing.
* **More Servers than Requests (e.g., 5 servers, 2 requests):** Requests route to Server 1 and 2; Servers 3, 4, 5 remain idle at 0 ms load.

---

### Section 5: Real-World Cloud Translation & Extensions

#### Q21: What are the primary scientific limitations of this simulator?
**Answer:**
1. **Static Cumulative Assumption:** It tracks historical total assigned time rather than dynamically draining tasks from active queues over arrival timestamps.
2. **Zero Network Latency:** It does not model payload upload/download network transfer times ($D_i / \text{Bandwidth}$).
3. **No Scheduling or Context Overhead:** Real operating systems incur CPU interrupt and context-switching overhead when executing concurrent threads.
4. **Homogeneous Hardware:** Baseline servers are assumed to process tasks at an identical instruction clock rate.

#### Q22: How would you extend this simulator to model a real cloud deployment?
**Answer:**
1. **Discrete-Event Simulation (DES):** Use event queues (like SimPy) to simulate real-time request arrivals based on `Arrival_Time`, tracking active execution, queue waiting time, and completion events.
2. **Network Model:** Calculate total request latency as $\text{Latency} = \text{Queue Wait} + \frac{\text{Data Size}}{\text{Bandwidth}} + \frac{\text{Processing Time}}{\text{CPU Capacity}}$.
3. **Heterogeneous Instances:** Add capacity multipliers to servers (e.g., Server 1 = $2.0\times$, Server 2 = $1.0\times$, Server 3 = $0.75\times$).
4. **Health Checking:** Emulate server node crashes and dynamic instance failover.

#### Q23: How would this load balancer be deployed in production?
**Answer:** In production:
1. Backend servers would run as microservices in **Docker containers** managed by **Kubernetes**.
2. The load balancer would run as an **NGINX**, **HAProxy**, or **AWS ALB** reverse proxy instance.
3. Client requests would arrive via standard HTTP/HTTPS protocols, and the proxy would maintain connection pools, terminate TLS, and dynamically balance traffic using Least Connections or Round Robin.

#### Q24: What is the "Power of Two Random Choices" (P2C) algorithm?
**Answer:** In large distributed clusters (e.g., 10,000 servers), querying every server for its load is too expensive ($\mathcal{O}(N)$). The **Power of Two Choices** algorithm picks two servers at random and assigns the request to the one with the smaller load. Mathematically, this achieves near-optimal load balancing in $\mathcal{O}(1)$ time.

#### Q25: Why did Round Robin assign 334 requests to Server 1 and 333 to Servers 2 and 3?
**Answer:** Because $1,000 \div 3 = 333$ with a remainder of $1$ ($1000 \pmod 3 = 1$). Since indexing starts at Server 1 (index 0), the extra 1,000th request cycled back and was assigned to Server 1.

---

### Section 4: Cloud Chaos Lab, Fault Recovery & Adaptive Balancing

#### Q26: What is Chaos Engineering and why is it applied to cloud systems?
**Answer:** Chaos Engineering is the discipline of experimenting on a distributed system by intentionally injecting turbulent conditions (node crashes, CPU throttling, network partition, traffic spikes) to build confidence in the system's capability to withstand unexpected production failures. In our Cloud Chaos Lab, it allows us to empirically verify that request recovery, health probes, and auto-scalers function correctly under stress.

#### Q27: How does your simulator distinguish between failure occurrence and failure detection?
**Answer:** In real distributed systems, failures are not instantaneously known. When a server crashes at $t_{\text{fail}}$, the load balancer continues to assume it is healthy until heartbeat probes miss or connection timeouts occur. Our simulator models this with an explicit **Failure Detection Delay** ($\Delta t_{\text{detect}} \approx 1.5\text{s}$). The event is detected at $t_{\text{detect}} = t_{\text{fail}} + \Delta t_{\text{detect}}$, during which tasks assigned to the dead node are interrupted and must be recovered.

#### Q28: What is the difference between Restart-from-Beginning and Checkpoint-Based recovery?
**Answer:**
* **Restart-from-Beginning (Default):** The interrupted request is restarted from scratch on a healthy node. Any computational progress made before the crash is lost and recorded as **Lost Work (ms)**.
* **Checkpoint Recovery:** The task periodically saves state checkpoints to shared storage (e.g., distributed cache or S3). Upon reassignment, execution resumes from the latest checkpoint, saving computational time.

#### Q29: How does the system prevent duplicate task completions or lost requests?
**Answer:** Every request has a unique `Request_ID`. The `RecoveryManager` tracks a finalized request set. When a server crashes, active and queued requests are harvested, incremented by retry count, and reassigned. Once a request completes or permanently fails (exceeding `max_retries`), its ID is finalized, preventing duplicate completion events from stale delayed events. Total request conservation is mathematically verified:
$$\text{Submitted} = \text{Completed} + \text{In-Flight} + \text{Queued} + \text{Permanently Failed}$$

#### Q30: How does Adaptive Capacity-Aware Load Balancing (ACALB) work?
**Answer:** ACALB is a state-aware scheduling algorithm that calculates an explainable Estimated Completion Time (ECT) score for each healthy server:
$$\text{Score}(s) = \frac{\text{Queued Work}(s) + \text{Incoming Request Work}}{\text{Effective Capacity}(s) \times 1000.0} + \text{Network Latency}(s)$$
It filters out `FAILED`, `RECOVERING`, or `DRAINING` servers, factors in current CPU throttling (degradation factor), and picks the server that will finish the task earliest with deterministic tie-breaking.

#### Q31: Why does ACALB outperform Round Robin and Least Loaded under chaos conditions?
**Answer:**
* **Round Robin** blindly routes requests to crashed or degraded servers, causing task pile-ups and high failure rates.
* **Least Loaded** tracks historical cumulative workload without factoring in CPU degradation; if Server 3 is throttled to 25% speed, Least Loaded treats it as normal, causing massive queuing delays.
* **ACALB** directly down-weights throttled nodes and actively steers traffic to healthy, high-capacity instances.

#### Q32: How does the Horizontal Auto-Scaler prevent scaling oscillations ("thrashing")?
**Answer:** If an auto-scaler immediately scaled in whenever utilization dipped for a second, the cluster would thrash (rapidly spinning up and tearing down instances). Our auto-scaler uses:
1. **Sustained Evaluation Windows ($5.0\text{s}$):** Requires average CPU across healthy nodes to stay above 80% or below 25%.
2. **Cooldown Period ($12.0\text{s}$):** Enforces a minimum resting time between consecutive scaling actions.
3. **Graceful Draining:** Servers being scaled in stop accepting new requests, safely process their existing backlog, and only decommission once idle.

#### Q33: How does the system handle a total cluster outage when all servers fail?
**Answer:** Rather than silently discarding incoming or in-flight requests, our simulator deposits them into a **Cluster Outage Backlog Buffer**. As soon as any server completes its recovery startup delay and passes health checks, the backlog is immediately dispatched to the newly restored server.

#### Q34: What mathematical model is used to estimate server energy consumption?
**Answer:** We model server power consumption based on standard datacenter power curves:
$$\text{Power}(t) = P_{\text{idle}} + (P_{\text{busy}} - P_{\text{idle}}) \times \text{Utilization}(t)$$
Integrating over simulated time yields energy in Watt-seconds (Joules), converted to Kilowatt-hours (kWh):
$$\text{Energy (kWh)} = \frac{(P_{\text{idle}} \times T_{\text{idle}}) + (P_{\text{busy}} \times T_{\text{busy}})}{3,600 \times 1,000}$$
with default parameters $P_{\text{idle}} = 120\text{W}$ and $P_{\text{busy}} = 300\text{W}$.

#### Q35: Is ACALB an Artificial Intelligence (AI) or Machine Learning (ML) algorithm?
**Answer:** No. ACALB is a deterministic, state-aware algorithmic heuristic based on queuing theory and estimated completion times. It is explainable, requires no training dataset or inference engine, and operates in $\mathcal{O}(N)$ time complexity. We deliberately avoid labeling it as AI to maintain scientific accuracy.

