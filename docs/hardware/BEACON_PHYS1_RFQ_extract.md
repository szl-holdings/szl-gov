# A11oy Beacon / PHYS-1 — RFQ extract (Rev 0.9, 2026-08-31)

Source: A11oy_KHIPU_X1_Chip_Software_Build_Manual.docx, emailed 2026-08-31 04:49 UTC.
Recipient: Minewing (JDM), Attn: Jenny. Marked CONFIDENTIAL - PRE-NDA TECHNICAL RFQ.

---

A11oy Beacon
Reality Protocol Hardware Platform
Product Requirements, JDM Feasibility Package & EVT Build Specification
Prepared for: Minewing | Attn: Jenny
Prepared by: SZL Holdings | 31 August 2026 | Revision 0.9 RFQ
CONFIDENTIAL - PRE-NDA TECHNICAL RFQ
This package intentionally defines interfaces, safety constraints, verification requirements, manufacturing deliverables and acceptance criteria in detail while withholding proprietary A11oy algorithms, model weights, private keys and deployment credentials.
PURCHASE SCOPE: ONE (1) COMPLETE PERSONAL ENGINEERING PROTOTYPE ONLY. NO MASS-PRODUCTION TOOLING OR VOLUME ORDER IS AUTHORIZED.
1. Executive Request to Minewing
SZL Holdings requests a JDM feasibility study and quotation for a new offline-first, secure edge appliance currently designated A11oy Beacon / PHYS-1. The product is intended to support community resilience, disaster coordination, field operations and verifiable physical-world workflows when conventional internet or cloud infrastructure is degraded or unavailable.
The requested engagement is not a generic IoT box-build. Minewing is asked to co-engineer the electrical, RF, power, mechanical and manufacturing implementation while SZL retains ownership of the A11oy software, Reality Protocol, receipt formats, models, policies and cloud/control-plane intellectual property.
Feasibility verdict: Technically feasible with commercially available embedded compute, secure elements, TPM/MCU roots of trust, standard radio modules, local storage, battery management and industrial I/O. The main engineering challenge is disciplined integration, verification and certification - not the availability of fundamental technology.
2. Product Mission and Non-Negotiable Principles
3. What the Product Does
Creates a local Wi-Fi service and browser-based interface for help requests, offers of resources, verified notices, local maps, translation, status and operator workflows.
Matches structured needs to locally available resources while preserving a human approval step for consequential dispatches.
Exchanges signed, store-and-forward events with nearby trusted nodes over available transports; reconciliation occurs when links return.
Runs bounded local inference and retrieval for prioritization, translation, summarization, routing suggestions and evidence review. Model output is always labeled as machine inference.
Captures device identity, software/firmware measurements, timestamps, input evidence, authorization state, action evidence and independent outcome evidence into linked receipts.
Exposes low-voltage isolated I/O for laboratory demonstrations and future approved cartridges. Rev A must not directly control life-safety, medical treatment or high-energy machinery.
Operates from AC/DC adapter, USB-C PD, vehicle/field DC and internal battery; solar input is an optional design target.
4. The Differentiated System Concept
The core product concept is the A11oy Reality Transaction: INTENT -> EVIDENCE -> PROPOSAL -> SIMULATION/ASSESSMENT -> POLICY -> CONSENT -> ACTION -> WITNESS -> OUTCOME -> RECONCILIATION -> RECEIPT. Each transition is represented separately. A requested action, an executed action and a verified physical outcome are never treated as synonyms.
5. System Architecture
The architecture intentionally separates the high-level compute plane from a smaller trust/control plane. The main application processor performs local inference, UI, synchronization and data management. A separate microcontroller (RC1) acts as the hardware governance boundary for privileged I/O, watchdog functions and execution receipts.
6. Hardware Requirements - Rev A / EVT
7. RC1 Receipt Control Coprocessor - Functional Requirements
RC1 is a design requirement, not a branding-only feature. The application processor must not have unconditional direct electrical control over privileged outputs. RC1 validates an authorization envelope and creates its own evidence record before changing an output.
Receive an action envelope over a narrow, documented local interface (e.g., SPI/UART with authenticated framing).
Validate schema version, target device identity, command type, bounds, nonce/counter, expiration/time window, policy digest and authorization signature/MAC.
Check monotonic anti-replay state maintained in protected nonvolatile storage or secure element.
Reject malformed, expired, replayed, unauthorized or out-of-envelope requests without energizing the output.
Enforce hardware safe-state on reset, brownout, watchdog expiry, application processor failure and loss of required authorization state.
Generate an execution receipt containing the exact command digest, decision, hardware identity, time basis, firmware measurement/version, output channel and result.
Expose a separately readable witness input path so post-action evidence can be compared against the commanded state.
Support signed firmware updates with anti-rollback and a documented recovery path.
Provide a manufacturing test mode that cannot be entered in normal field operation without a physical or cryptographic authorization mechanism.
8. Security Architecture
9. Power System and Field Resilience
10. Mechanical and Environmental Requirements
11. Communications Strategy
The product should not depend on one mesh technology. Transport is abstracted above the link layer: signed Reality Protocol events are identical regardless of whether they travel over local Ethernet/Wi-Fi, BLE, LoRa, cellular or delayed removable transfer. The Rev A recommendation is to prioritize Wi-Fi/Ethernet plus BLE for local interaction and reserve LoRa as an optional long-range low-data-rate channel.
12. Local User Experience Requirements
A user who joins the Beacon local network should not need an account or technical training to see the minimum public interface. Sensitive workflows may require role authentication. The first screen should expose no more than the following primary actions:
I need help
I can help / offer a resource
Verified emergency information
Resources near me
Translate
I am safe / status
Operator console (role-gated)
Every consequential record displayed to a user must carry a visible status label such as VERIFIED SOURCE, AUTHORIZED OPERATOR, COMMUNITY REPORT, MACHINE INFERENCE, CONFLICTING EVIDENCE, UNVERIFIED or OUTCOME VERIFIED. Machine-generated content may never be rendered with official-authority styling unless the underlying source is authenticated.
13. Software / Firmware Boundary for Minewing
14. Reality Protocol - Minimum Data Contract
The hardware and firmware shall support event capture with sufficient deterministic metadata for the higher-level protocol. The exact SZL receipt schema remains proprietary until NDA/engineering kickoff. At minimum, each device-originated event must be able to carry:
15. Privacy, Safety and Humanitarian Use Guardrails
Data minimization: no biometrics, precise location, medical detail or identity should be mandatory for generic resource coordination unless the workflow has a defined need and consent/legal basis.
Local-first storage: keep sensitive records on the node unless sharing is explicitly authorized by policy/operator/user. Peer sync must support field-level or event-type restrictions.
Separate public alerts from private case records; public mesh propagation must never automatically include private names, medical details or exact household locations.
Rev A AI provides translation, summarization, triage assistance and matching proposals only. It must not diagnose illness, prescribe treatment or autonomously allocate scarce life-critical medical resources.
No hidden surveillance mode. Microphone/camera, if added to future SKUs, must have clear physical indicators and explicit use policy. Base Rev A does not require a camera.
Support audit exports without exposing unnecessary personal data: cryptographic proof can establish event integrity without publishing the underlying sensitive content.
16. Manufacturing Program - Required Gates
17. EVT Acceptance Test Matrix
18. Compliance and Certification Planning
Final applicable standards depend on the exact SKU, power source, radios, markets and claims. Minewing should provide a written certification matrix rather than treating the list below as automatically applicable. Pre-certified radio modules are preferred where they reduce risk, but the final host product still requires applicable integration and authorization work.
19. Quality, Traceability and Change Control
Every PCBA and finished unit must have a unique serial number linked to PCB lot, assembly lot, key component lot/date codes, firmware version, factory test result and provisioning record.
Critical component AVL must include manufacturer part number, approved alternates and PCN/EOL monitoring. No silent substitution of secure element, TPM, MCU, radio, storage, power IC, battery cells or safety-critical components.
Any substitution affecting RF, security, power, thermal, battery, regulatory or firmware behavior requires written SZL approval and regression plan.
Factory test shall cover rails, current draw, storage, radios, GNSS, secure identity, RC1 I/O, tamper input, display, buttons/selector, battery/BMS and final functional self-test.
Deliver test limits and raw/summary records in machine-readable form, not PDF-only where avoidable.
Production programming and key provisioning stations must maintain operator access control and auditable logs; secrets must never be embedded in source code or shared across all devices.
20. Ownership, IP and Security Terms Requested
21. Deliverables Required from Minewing
Feasibility report identifying impossible, high-risk, expensive or ambiguous requirements and recommended changes.
Two reference architectures (cost-optimized and performance-optimized) with block diagrams.
Preliminary BOM with manufacturer part numbers, lifecycle/availability notes, alternates, and the estimated total cost to build exactly one complete prototype unit.
Itemized NRE quote: EE, PCB, firmware/BSP, RC1 firmware, industrial/mechanical design, RF, prototypes, tooling, test fixtures, certification support and project management.
Project schedule through design, fabrication, assembly, firmware bring-up, bench validation, and delivery of one complete working prototype, with critical-path assumptions.
Complete electrical design package, PCB fabrication/assembly package, mechanical CAD and drawings, cable/antenna drawings and manufacturing notes.
Factory test specification, fixture design/source, calibration method and serialized test data.
Pre-compliance and compliance plan identifying labs, standards, test samples and expected recertification triggers.
Software/firmware source, build environment instructions, signed release artifacts and SBOM for manufacturer-developed code.
DFM/DFA/DFT review, thermal analysis, antenna/RF report and power budget.
Risk register with component, RF, battery, thermal, certification, schedule and supply-chain risks.
Golden sample and controlled product configuration baseline at each frozen phase.
22. Questions Minewing Must Answer in Its Proposal
Can Minewing implement the independent RC1 privileged-output boundary so the main Linux compute cannot directly bypass it? Describe the proposed electrical topology.
Which two compute modules/SoCs do you recommend for a 5-7 year product lifecycle, and what are their current supply/lifecycle risks?
Which TPM/secure-element combination do you recommend, and can device keys be generated inside hardware during trusted provisioning rather than imported as plaintext?
How will production secure boot and anti-rollback be implemented on both application processor and RC1?
Which Wi-Fi/BLE, LoRa and optional cellular modules minimize certification burden while meeting supply-life requirements?
What battery chemistry and capacity meet the target runtime without making safety, shipping or thermal certification disproportionately difficult?
Can you design toward IP65 while keeping serviceable modules and connectors? What enclosure process do you recommend for EVT versus production?
What certifications do you recommend for initial US launch, and what additional work is needed for EU/UK/Canada?
What is the estimated NRE, prototype cost, certification cost and unit cost at requested volume tiers?
What files, code and tooling will SZL own and receive at each gate? Identify any Minewing background IP or third-party closed components that would prevent independent future manufacturing.
Where will the single prototype be engineered, fabricated, assembled, programmed, and tested (China or Vietnam), and which team will own final bring-up?
What cybersecurity controls protect our design files and the production key-provisioning process?
23. Feasibility Assessment
24. Prior-Art and Novelty Boundary - Important
The market already contains offline disaster mesh applications, signed event systems, resource/supply matching, remote-attestation research and trusted cyber-physical command architectures. Therefore the product should not be marketed as the first offline disaster mesh, first signed emergency network, first trusted actuator or first cyber-physical attestation system.
The product differentiation we want Minewing to enable is narrower: a hardware-enforced separation of high-level AI reasoning from privileged actuation, combined with an A11oy transaction model that keeps intent, execution and independently evidenced outcome separate; unresolved or conflicting evidence remains explicit Reality Debt. This is a design objective, not a legal patentability opinion.
Recommendation: before filing or publicly claiming “world first,” commission a patent attorney or professional searcher for claim-charted novelty and freedom-to-operate work across secure actuation, remote attestation, event-sourced disaster logistics, cryptographic sensor provenance, proof-of-delivery and cyber-physical verification. <!-- lexicon-ok: doc PROHIBITS this claim pending patent search -->
25. Recommended Commercialization Sequence
Execute mutual NDA and JDM statement of work for Phase 0 feasibility only.
Freeze Rev A intended use and exclusions before schematic design.
Build exactly 1 engineering prototype for the owner. Avoid expensive production tooling; use CNC machining, additive manufacturing, or other prototype-grade enclosure methods.
Run SZL security, offline, reconciliation and Reality Debt demonstrations before future revision.
Complete EMC/RF/safety/battery pre-compliance before committing to production tooling.
Run future validation field pilots at a shelter-like site, clinic-like site, field vehicle and standalone community node using simulated/non-sensitive data first.
Only after measured results: define production SKU, marketing claims, certifications and manufacturing volume.
26. RFQ Response Format Requested
27. Research Basis and Standards References
R1. Minewing - End-to-end electronics design/manufacturing and prototype development capabilities. Source
R2. Minewing - JDM/OEM/ODM cooperation model and prototyping/manufacturing process. Source
R3. Minewing - Embedded systems, IoT, wireless, battery and EVT/future validation/future production validation capability. Source
R4. Minewing - FAQ: NDA/IP, ISO 9001 quality system, prototype iterations, sourcing and box-build. Source
R5. NISTIR 8259A - IoT Device Cybersecurity Capability Core Baseline. Source
R6. NISTIR 8259 series - IoT manufacturer activities and supporting capabilities. Source
R7. NIST SP 800-193 - Platform Firmware Resiliency Guidelines. Source
R8. FCC - RF device equipment authorization; Part 15 intentional radiators include Wi-Fi/Bluetooth. Source
R9. UL - IEC/UL 62368-1 testing and certification for AV/ICT equipment. Source
R10. IEC - IEC 60529 ingress protection (IP) ratings. Source
R11. IEC - IEC 62133-2 lithium portable battery safety. Source
R12. UNECE - UN Manual of Tests and Criteria, lithium battery 38.3 materials. Source
R13. IATA - Lithium battery transport and test-summary requirements. Source
R14. LoRa Alliance - LoRaWAN 1.1 specification. Source
R15. Bluetooth SIG - Bluetooth Mesh security, relaying and provisioning. Source
R16. ETSI EN 303 645 - Cybersecurity baseline for consumer IoT. Source
R17. EU Cyber Resilience Act summary and application timeline. Source
R18. ICRC - Handbook on Data Protection in Humanitarian Action. Source
R19. IgniRelay - offline signed emergency events, BLE relay and supply matching. Source
R20. Google Patents - US20190110172A1 Mesh networks for disaster relief. Source
R21. Google Patents - US10872153B2 Trusted cyber physical system. Source
R22. EMBRAVE - TPM-based remote attestation framework for dynamic IoT networks. Source
R23. Nature Electronics 2026 - in-sensor cryptographic signature generation linking physical process to immutable digital entity. Source
28. SZL Software Baseline Used for This Specification
This hardware specification is derived from SZL Holdings software concepts already represented in its GitHub estate, including A11oy governed decisions and signed receipts, the shared bounded agent loop in szl-substrate, unified receipt chains in szl-kernels, governance/provenance components, and the Forge model qualification/publication boundary. Minewing does not need source-code access to quote the hardware; only stable hardware/firmware interfaces are required during JDM development.
A11oy
SZL Substrate
SZL Kernels
SZL Forge
SZL Receipt Attention
Governance as Code
29. Decision Requested from Minewing
Please respond with a Phase 0 JDM feasibility proposal, not a mass-production commitment.
The immediate objective is to determine whether Minewing can design and build one secure, fully functional Rev A prototype that preserves the independent RC1 authorization boundary, reliable offline operation, hardware-backed identity, and field-power requirements. This request is for one personal engineering prototype only. It is not a request for mass production or production tooling.
30. Requested Next-Step Reply
Please reply with a Phase 0 feasibility package before any tooling or production commitment. A useful first response should include:
Named technical project lead and proposed JDM engineering team.
Two compute/security architectures with preliminary block diagrams and key component choices.
Itemized engineering/NRE charges, component cost, PCB fabrication and assembly, enclosure fabrication, firmware/bring-up labor, testing, shipping, and the total all-in price for exactly one prototype, with payment milestones.
Estimated calendar weeks from kickoff to delivery of the single working prototype, including long-lead items.
Written response to the RC1 privileged-output isolation requirement and secure key-provisioning approach.
US-first pre-compliance/certification plan and a list of standards Minewing believes are applicable.
Explicit statement of which source files, CAD, Gerbers, test fixtures, tooling and firmware SZL will own and receive.
Top technical risks or requirements Minewing recommends changing before schematic capture.
Do not begin mass-production tooling from this document. The requested engagement ends with one working prototype, its engineering files, test evidence, and owner acceptance. Any later revisions or production would require a separate written authorization.
APPENDIX — KHIPU-X1 CUSTOM LLM ACCELERATOR / CHIP ROADMAP
Purpose: extend the one-prototype A11oy program with the software and hardware work required to create a custom SZL LLM accelerator. Build an FPGA prototype first; treat it as the executable specification for any later ASIC.
What SZL already has
Receipt-attention software with SHA3-256 receipt chaining.
YARQA compartment/canal attention and Khipu fail-closed governance concepts.
Unified governed-kernel receipt chains, KV/mask provenance concepts, DSSE/provenance tooling, model qualification and signed GPU-job workflows.
These are software/research primitives, not yet a synthesizable chip design.
Software missing before a chip is useful
A versioned KHIPU instruction-set/descriptor and register-map specification (KIDS).
A deterministic Python/C++ golden simulator for every hardware command.
A calibrated performance/memory simulator.
A compiler pipeline: PyTorch/ONNX -> KHIPU IR/MLIR -> quantization/legalization/fusion -> memory planning -> KHIPU command stream.
INT8/BF16 quantizer first; INT4 only after measured accuracy qualification.
libkhipu C/C++ runtime and Python bindings.
Linux driver for DMA, queues, interrupts, reset, health and firmware loading.
RC1/security MCU firmware: secure boot, anti-rollback, watchdog, thermal/power limits and provisioning.
Safe model package format (.khipu) binding graph, weights, ABI, quantization, hashes and signatures.
LLM inference engine: tokenizer, prefill/decode scheduler, KV-cache manager and sampling.
PyTorch custom backend/torch.compile integration; optional llama.cpp backend later.
Profiler/observability: cycles, bandwidth, utilization, queue stalls, temperature, power and measured energy.
Device/bitstream/firmware attestation and execution-receipt verifier.
Golden vectors, differential tests, fuzzing, fault injection, soak testing and compatibility suite.
Developer SDK, CLI, examples, documentation and reproducible build environment.
FPGA v0.1 hardware scope
Tiled GEMM/matrix-vector datapath.
RMSNorm datapath.
Standard causal attention plus YARQA compartment descriptors.
KV-cache DMA/gather/scatter with block-table commitment.
SHA3-256 receipt/event-chain engine.
DMA, descriptor queues, interrupts, monotonic sequence counter and hardware timestamps.
Board-level energy/power sensing; report UNAVAILABLE rather than estimate when measurement fails.
Secure element/TPM and separate RC1 controller.
New repositories to create
khipu-x1-hw — RTL/HLS, FPGA projects, firmware, formal properties, evidence.
khipu-compiler — IR, graph lowering, quantizer, memory planner, command generator.
khipu-runtime — libkhipu, Python bindings, model loader, verifier.
khipu-driver — Linux device/DMA/queue/reset boundary.
khipu-sim — functional and performance simulators.
khipu-sdk — CLI, profiler, examples and docs.
khipu-conformance — golden vectors, fuzz corpus, compatibility matrix and benchmark harness.
FPGA-to-ASIC requirements
Do not tape out until the FPGA proves correctness, workload value, memory architecture and software usability.
A real ASIC additionally needs synthesis/physical design, SRAM/compiler macros, clocks/resets, power domains, DFT/scan/BIST, high-speed I/O, timing closure, IR-drop/EM analysis, package/thermal design, signoff and production test.
ASIC software adds boot ROM, BSP/HAL, production driver, manufacturing test software, post-silicon characterization, microcode/firmware update and errata/compatibility handling.
One-prototype acceptance criteria
Boot and report exact FPGA bitstream, firmware and device identity.
Pass differential golden tests against PyTorch/NumPy references.
Run a tiny transformer end-to-end; stretch goal 0.5B-1.5B model if FPGA memory/resources allow.
Produce an offline-verifiable execution receipt binding workload, hardware identity, ordered execution and output commitment.
Reject replay, stale nonce, wrong bitstream, malformed package and broken receipt chain.
Measure latency, tokens/s, bandwidth, utilization, receipt overhead and joules/token where real measurement exists.
Reproduce the FPGA image from pinned source/tool versions, subject to vendor tool licensing.
What to ask Jenny
Can Minewing provide in-house FPGA engineers, or name the FPGA subcontractor/partner?
Can they build one prototype around an AMD Versal-class adaptive SoC or another suitable FPGA/SOM, with memory, secure controller, power telemetry, cooling and enclosure?
Quote FPGA engineering separately from PCB/mechanical/NRE.
Deliver schematics, PCB source/Gerbers, BOM, mechanical CAD, board-management firmware they create, FPGA source/constraints/build scripts created for SZL, and bring-up/test evidence.
No production tooling, mass-production commitment or ASIC tapeout is authorized by this prototype request.
Recommended software build order
1. Freeze KIDS v0.1, precision, memory budget and supported transformer block.
2. Build golden simulator + conformance vectors.
3. Build GEMM/RMSNorm/DMA FPGA path and libkhipu runtime.
4. Add attention/YARQA and KV-cache engine.
5. Add receipt engine, attestation, RC1 and measured energy.
6. Add compiler/quantizer and tiny-transformer end-to-end path.
7. Add PyTorch integration and one small qualified LLM.
8. Benchmark and attack-test; only then decide whether an ASIC feasibility/tapeout program is justified.
Current toolchain references (August 2026)
AMD Vitis/Vivado 2026.1 supports FPGA/Adaptive-SoC platform development, HLS and RTL kernels, AI Engine development, hardware emulation and on-board execution. AMD Vitis AI provides inference compilation/runtime support for supported Versal AI Edge devices. CIRCT applies MLIR/LLVM methods to hardware compilers but describes itself as experimental. OpenROAD provides an RTL-to-GDSII physical-design flow and is useful for research/mature-node exploration; commercial AI silicon still requires foundry/PDK/IP/signoff/test expertise.
Reference URLs: AMD Vitis AI Developer Hub; AMD Vitis 2026.1 Getting Started; AMD Versal AI Edge design tools; CIRCT Getting Started; OpenROAD Developer Guide. These are engineering references, not endorsements or claims that a KHIPU ASIC already exists.

[TABLE 1]
Principle | Requirement
Offline first | Core workflows continue without cloud, cellular service or upstream internet. Network loss is a normal operating mode, not an exception.
Human authority | The system may recommend and coordinate; consequential actions require explicit policy and/or human authorization. Rev A is not a medical diagnosis or autonomous emergency-services system.
Evidence before status | Intent, action and outcome are distinct states. No user interface may convert an attempted action into a verified outcome without evidence.
Privacy by minimization | Collect the minimum personal information necessary, encrypt locally, make sharing visible, and support deletion/retention policy.
Fail closed | Invalid identity, expired authorization, replay, policy mismatch, corrupt firmware state or broken evidence chain must block privileged actions.
Repairable and supportable | Use modular radios/compute where practical; publish lifecycle and support commitments; retain component alternatives.
No fake green | Unknown, unavailable, unverified and failed states must remain explicit.

[TABLE 2]
Primitive | Definition | Rev A implementation
Proof of Intent | Evidence of what was requested, by whom/what, and under which policy context. | Signed local event; actor identity; timestamp; request digest; policy version.
Proof of Action | Evidence that an authorized operation was actually attempted/executed. | RC1-generated execution receipt or operator/peer handoff receipt.
Proof of Outcome | Independent evidence that observed state changed as intended. | Separate sensor, second node, recipient confirmation or authenticated witness event.
Reality Debt | An outcome claim whose evidence is insufficient or conflicting. | State remains OPEN/UNVERIFIED; never auto-promoted to success.
Witness Diversity | Different evidence sources should not collapse into a single self-attestation. | Track source class, device identity, independence and conflict.
Counterfactual Record | Record bounded alternatives considered before consequential action. | Software receipt field; not required for every low-risk transaction.

[TABLE 3]
Subsystem | Minimum requirement | Preferred / stretch | Vendor response required
Compute | Industrial-capable SOM or module; 4+ CPU cores; 8 GB RAM; 128 GB nonvolatile storage. | 16 GB RAM; 256-512 GB NVMe; NPU/GPU capable of local 1-4B quantized model or accelerator module. | Propose 2 architectures with lifecycle, thermals, availability and cost.
Root of trust | TPM 2.0 or equivalent hardware root plus separate secure element for device identity/private key. | DICE/TPM measured boot support; anti-rollback counters. | Name exact parts, provisioning path and ownership of factory keys.
RC1 controller | Independent MCU with hardware crypto, watchdog, secure boot and isolated privileged output path. | NXP/STM32-class MCU with secure element or integrated secure enclave. | Propose architecture proving Linux cannot directly bypass RC1 outputs.
Storage | 128 GB minimum; encrypted filesystem support; endurance appropriate for event logging. | Industrial eMMC + removable/replaceable NVMe with power-loss protection. | Provide TBW/endurance and second-source options.
Ethernet | 1x Gigabit Ethernet; ESD protection. | PoE+/PoE++ input option; second Ethernet or TSN-capable option. | State PHY, magnetics, surge/ESD design.
Wi-Fi / BLE | Dual-band Wi-Fi + BLE using pre-certified module where possible. | Wi-Fi 6/6E; BLE 5.4; optional external antennas. | Provide FCC/CE module certification strategy.
Long-range radio | Header/M.2/UART/SPI path reserved. | LoRa/LoRaWAN sub-GHz regional module; optional Wi-Fi HaLow study. | Quote base unit with and without LoRa.
Cellular | Not required in base EVT. | M.2 B-key LTE/5G modem option with GNSS/eSIM/SIM. | Recommend globally supportable pre-certified modem family.
GNSS/time | RTC with battery/supercap backup. | GNSS receiver with PPS for trustworthy local time discipline. | State holdover accuracy and PPS routing.
I/O | 8 isolated digital inputs; 4 low-voltage isolated outputs; protected USB. | 2x CAN-FD; isolated RS-485; 2 analog inputs; cartridge connector. | Provide isolation ratings and transient protection.
Power telemetry | Measure input voltage/current and battery state. | Per-rail power telemetry where practical; energy counters for evidence. | Specify sensor resolution, calibration and accuracy.
Tamper | Enclosure-open/tamper input logged by RC1. | Optional light/mesh tamper sensor; secure erase trigger configurable but disabled by default. | Propose simple reliable mechanism.
Display | 2.9-5 inch low-power status display or equivalent. | Sunlight-readable, glove-friendly optional touch. | Compare e-ink vs LCD power/availability/cost.
Physical controls | Power; recessed reset; clearly labeled LOCK / OBSERVE / ACT selector. | Dedicated Help/SOS button for Beacon SKU. | Selector must electrically gate privileged outputs where feasible.

[TABLE 4]
Control | Requirement
Unique device identity | Each production device receives a unique certificate/key identity. Universal/shared default credentials are prohibited.
Secure boot | Application processor and RC1 must verify boot components. Recovery images must also be authenticated.
Measured state | Boot and software measurement evidence must be available to A11oy for local/remote attestation where platform support allows.
Key protection | Long-term private keys must be non-exportable or hardware-protected wherever feasible. Factory and production keys must be separated.
Update | Signed update bundles; anti-rollback; A/B or resilient recovery strategy; power-loss-safe update path.
Debug | JTAG/SWD/UART production policy documented. Debug ports disabled/locked or physically inaccessible on production units; controlled RMA unlock procedure.
Data at rest | Encrypted local storage. Secrets separated from application database. Clear retention/export/delete controls.
Network | No inbound cloud dependency. Local services bind only as needed; mutual authentication for trusted peer sync; rate limits and replay defenses.
SBOM | Generate machine-readable SBOM for firmware/software delivered by manufacturer and track third-party component versions.
Vulnerability support | Minewing must disclose security-impacting component EOLs/CVEs known during development and support substitution analysis.

[TABLE 5]
Item | Target
Input | USB-C PD 20 V capable plus protected 9-36 V DC field input. Final range subject to power architecture.
Battery | Internal serviceable or semi-serviceable Li-ion/LiFePO4 pack; BMS with protections and fuel gauge. Chemistry to be proposed after thermal/safety trade study.
Runtime target | 8 hours minimum in normal offline Beacon mode at moderate radio/display duty cycle; 12-24 hours preferred with low-power profile.
Solar | Optional MPPT-compatible DC input or external certified solar power accessory; do not delay base EVT if it adds disproportionate complexity.
Brownout | Graceful shutdown or ride-through sufficient to commit critical event log state; RC1 enters safe output state.
Thermal | Fanless preferred. Derate compute under high ambient temperatures rather than silently exceeding component limits.
Transport | Battery design and chosen cells/pack must support required UN 38.3 documentation before commercial shipment.

[TABLE 6]
Attribute | EVT target | Production target / note
Enclosure | CNC aluminum or high-quality printed/machined prototype enclosure. | Injection molded PC/ABS or die-cast/CNC aluminum based on cost and thermal result.
Ingress | Design toward IP54 minimum. | IP65 preferred for field SKU if ports/connectors can support it; verify to IEC 60529 through laboratory testing.
Mounting | Desk/wall mounting points. | Wall + optional DIN-rail/backplate; carry handle or protective corners for Beacon field SKU.
Connectors | Clearly keyed, labeled, strain-relieved. | Locking industrial connectors for field I/O; weather caps where relevant.
Operating temperature | 0 to 45 C acceptable for EVT. | Target -10 to 55 C or wider after component/thermal qualification; no unsupported claim until tested.
Drop/vibration | Bench handling and transport survivability. | Define IEC/MIL-derived test profile during DVT; do not claim MIL-STD compliance without testing.
Serviceability | Access to storage/radio/battery as architecture permits. | No adhesive-only service path for expected field-replaceable items.

[TABLE 7]
Transport | Use | Design rule
Ethernet | Fixed sites, backhaul, commissioning, high-throughput sync. | Preferred trusted backhaul where available.
Wi-Fi | User portal, node-to-node local networking, updates and bulk sync. | Operate as AP/local service without internet; secure onboarding.
BLE | Phone onboarding, nearby discovery, low-data messaging and optional mesh experiments. | Do not promise unlimited mesh range; validate real field topology.
LoRa/LoRaWAN | Low-bandwidth long-range status, request digests or telemetry. | Treat LoRaWAN as star-of-stars unless a separate peer mesh protocol is implemented; region-specific RF design.
Cellular | Optional upstream connectivity where infrastructure exists. | Modular; base product must remain useful without it.
GNSS | Position and PPS time. | Location collection must be consent/policy controlled.

[TABLE 8]
Minewing responsibility | SZL responsibility
Board support package, bootloader integration, device-tree/platform configuration, factory test firmware, RC1 firmware implementation to SZL protocol specification, hardware diagnostics, power/thermal/RF validation. | A11oy application software, Reality Protocol state machine and receipt semantics, models, policy engine, private signing infrastructure, cloud/control-plane services, domain workflows.
Secure manufacturing/provisioning workflow jointly designed with SZL; generate device keypair in hardware where possible and deliver public identity/certificate enrollment artifact. | Certificate authority / production trust policy; key lifecycle; signing/verification service; model and policy releases.
Documented APIs/HAL for radios, battery, GNSS, sensors, RC1, display and I/O. | Application integration above HAL and acceptance test harness.

[TABLE 9]
Field class | Examples
Identity | device_id, hardware_rev, component identity/certificate reference
Software state | boot measurement, firmware version, application version, policy digest
Time | monotonic counter, RTC timestamp, GNSS/PPS quality where available
Transaction | transaction_id, parent receipt hash, event type, actor/role reference
Evidence | input digest(s), sensor channel, units, calibration identifier, witness source class
Authorization | command digest, nonce, expiry, bounds, authorizer identity/policy
Execution | RC1 decision, output channel/state, error code, execution timestamp
Outcome | witness event(s), observed state, evidence quality, conflict/unverified state
Integrity | signature/MAC, algorithm identifier, key/certificate reference

[TABLE 10]
Phase | Purpose | Proposed quantity | Exit criteria
Phase 0 - Feasibility | Architecture, risk, preliminary BOM, RF/power/security trade studies. | No units | Written feasibility report; two compute options; preliminary compliance plan; NRE and schedule quote.
Prototype Rev A | Electrical bring-up, RC1 boundary, radios, power, enclosure, factory-test concept. | 1 unit | All rails stable; secure boot path; unique identity; RC1 deny/allow tests; local portal; 8-hour bench soak.
Future / not requested | Outside this purchase request. Quote only if useful as an optional future path. | 0 units | No authorization to tool or build additional units.
Future / not requested | Outside this purchase request. Quote only if useful as an optional future path. | 0 units | No authorization to tool or build additional units.
Future / not requested | Outside this purchase request. Quote only if useful as an optional future path. | 0 units | No authorization to tool or build additional units.
Future / not requested | Outside this purchase request. Quote only if useful as an optional future path. | 0 units | No authorization to tool or build additional units.

[TABLE 11]
ID | Test | Pass criterion
SEC-01 | Unique identity | Each unit presents a unique hardware-backed identity; no shared production secret.
SEC-02 | Secure boot rejection | Modified/unsigned test image is rejected or enters documented recovery path.
RC1-01 | Unauthorized output | Output remains electrically safe when command lacks valid authorization.
RC1-02 | Replay | Previously accepted privileged command cannot be replayed successfully.
RC1-03 | Expiry | Expired action envelope is rejected.
RC1-04 | Linux bypass attempt | Application processor cannot directly toggle the protected output outside RC1 path in normal field configuration.
PWR-01 | Power interruption | Critical event log remains consistent after repeated abrupt power loss; RC1 returns to safe state.
PWR-02 | Battery runtime | Meets agreed Rev A workload runtime target with measured profile documented.
NET-01 | No internet | Local portal, need/resource workflow and receipt verification work with WAN physically disconnected.
NET-02 | Store-forward | Queued signed events synchronize after link restoration without silent overwrite.
DATA-01 | Tamper evidence | Modified receipt/event fails verification and is surfaced as invalid.
OUT-01 | Outcome independence | System can represent executed-but-unverified outcome and conflicting witness evidence.
THERM-01 | Soak | 8-hour representative workload without uncontrolled reset or component over-temperature.
MFG-01 | Factory test | Each EVT unit ships with serialized test report and calibration/provisioning record.

[TABLE 12]
Area | Likely framework / requirement | Design implication
US RF | FCC equipment authorization; intentional radiators such as Wi-Fi/Bluetooth generally require certification. | Use approved modules/antenna configurations where practical; plan host emissions and labeling.
US/Canada product safety | UL/CSA 62368-1 is the principal AV/ICT safety framework for many computing/networking products. | Select recognized components, power supplies, plastics and insulation architecture early.
EU RF/EMC | CE under RED/EMC/LVD as applicable; final declaration based on exact radios/product. | Radio/antenna/EMC design and technical file from DVT onward.
Ingress | IEC 60529 IP Code. | Do not market IP rating until enclosure/connector configuration passes appropriate test.
Battery safety | IEC 62133-2 may apply to portable sealed lithium systems; pack/cell certifications and BMS evidence required. | Prefer qualified cell/pack supplier and design battery service/shipping path early.
Battery transport | UN Manual of Tests and Criteria 38.3; distributors/manufacturers need test-summary availability for applicable batteries. | Require UN 38.3 test summary before shipment of production battery configuration.
IoT security baseline | NISTIR 8259A/8259B and NIST IoT manufacturer guidance. | Unique ID, protected configuration, data protection, logical access, secure update, cybersecurity state awareness and support processes.
Firmware resilience | NIST SP 800-193 concepts: protect, detect, recover. | Signed boot/update, recovery, anti-rollback and trusted measurements.
Consumer IoT baseline where applicable | ETSI EN 303 645. | No universal default passwords; vulnerability handling; secure updates; transparent personal-data handling.
EU future cybersecurity | EU Cyber Resilience Act obligations become broadly relevant for products with digital elements placed on EU market; main application date 11 Dec 2027. | Plan secure-by-design, vulnerability handling, support period, documentation and update commitments now.
Environmental/materials | RoHS/REACH and WEEE/packaging obligations depending market. | Require declarations for BOM/components and materials.

[TABLE 13]
Item | Requested position
Foreground hardware IP | All custom schematics, PCB layouts, Gerbers, BOM/AVL, mechanical CAD/STEP, tooling drawings, test fixtures/specifications and custom firmware source created under the paid project are delivered to SZL, subject to negotiated third-party licenses and Minewing background IP explicitly identified in writing.
A11oy / Reality Protocol | Remains exclusively SZL. Minewing receives only the interface/specification needed to build and test hardware.
Models/data | No model weights, training datasets, production secrets or private signing keys are required for manufacturing. Test fixtures use non-production credentials.
Confidentiality | Mutual NDA before disclosure beyond this RFQ; project access limited to assigned personnel; no public case study, photos or marketing use without written approval.
Tooling | Ownership, storage location, maintenance, transfer rights and end-of-project disposition stated in quote.
Source escrow/delivery | All custom MCU/BSP/factory-test source and build instructions delivered at each major gate; no dependency on an inaccessible vendor-only binary for critical security logic unless disclosed and approved.
Change control | No material/BOM/firmware substitutions without approved ECN.

[TABLE 14]
Element | Feasibility | Comment
Offline local portal + database | HIGH | Commodity embedded Linux capability; straightforward.
Bounded local AI inference | HIGH | Feasible on current ARM/x86/accelerated modules; exact model size/latency is a compute and thermal trade-off.
TPM + secure element identity | HIGH | Established embedded security pattern.
Independent RC1 authorization controller | HIGH | Conventional MCU/secure-element engineering; requires careful threat model and electrical boundary.
Signed receipts / event chain | HIGH | Primarily SZL software; hardware provides keys, time, measurements and trustworthy execution events.
Offline peer synchronization | HIGH | Software complexity is material but not a hardware blocker.
BLE multi-hop mesh at disaster scale | MEDIUM | Possible but topology, OS/mobile behavior, congestion and range require field validation; do not make blanket coverage claims.
LoRa peer-to-peer humanitarian mesh | MEDIUM | Technically possible with custom protocol; LoRaWAN itself is normally star-of-stars, so architecture must be explicit.
8-24 hour battery operation | MEDIUM-HIGH | Achievable with duty cycling and compute power management; final result depends on display/radios/model workload and battery size.
IP65 + serviceability | MEDIUM | Achievable but connector sealing, thermal path and service doors increase mechanical complexity.
Proof of physical outcome | HIGH as protocol; VARIABLE as evidence | The data model is implementable. Strength of any claimed outcome depends on independent sensors/witnesses and domain-specific validation.
Life-safety autonomous actuation | OUT OF SCOPE | Would require domain-specific safety engineering, certification and liability controls. Rev A explicitly excludes this.

[TABLE 15]
Adjacent work found | Why it matters
IgniRelay | Already demonstrates offline BLE relay, Ed25519-signed disaster events, event sourcing and supply-demand matching with physical-handoff state.
Crisis Connect / ResQMesh / MeshBeacon | Show that infrastructure-free disaster communication and on-device AI/mesh combinations are active areas.
US20190110172A1 - Mesh networks for disaster relief | Prior patent publication covers mesh nodes for disaster relief, communications and inventory/resource management.
US10872153B2 - Trusted cyber physical system | Active patent covers secure terminals/TEE/trusted peripherals that verify commands to remote actuators; relevant to freedom-to-operate review.
Remote-attestation literature (EMBRAVE/AAoT/PROVE) | Hardware/software integrity attestation for IoT/CPS is established research.
2026 Nature Electronics in-sensor cryptographic signatures | Shows emerging hardware that cryptographically links sensing/physical recording to digital evidence.

[TABLE 16]
Section | Minewing response
Feasible as written? | Yes / No / Requires change, with explanation per requirement.
Architecture | Block diagram + exact candidate parts/modules.
NRE | Itemized by discipline and phase.
Prototype costs | 5 / 10 / 20-50 unit costs, including enclosure method.
Prototype price | Total all-in price for 1 complete prototype, itemized by NRE, parts, fabrication, assembly, enclosure, test and shipping.
Schedule | Calendar weeks to design freeze, PCB/enclosure fabrication, assembly, bring-up, validation, and delivery of 1 prototype.
Certification | Required/optional tests, labs, sample counts and budget.
Ownership | Explicit deliverables and IP/tooling ownership.
Risks | Top 10 technical/supply/regulatory risks and mitigation.
Open questions | Information required from SZL to finalize architecture.
