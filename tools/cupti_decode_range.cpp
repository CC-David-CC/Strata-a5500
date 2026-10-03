// Private Linux diagnostic. Interpose only cudaProfilerStart/Stop so an existing
// binary can collect one CUPTI user range without Nsight API interception.
// API sequence follows NVIDIA's CUDA 13.2 range_profiling sample. No replay,
// graph replacement, clock control or application kernel changes are performed.
#include <cuda.h>
#include <cuda_profiler_api.h>
#include <cuda_runtime_api.h>
#include <cupti.h>
#include <cupti_profiler_host.h>
#include <cupti_profiler_target.h>
#include <cupti_range_profiler.h>
#include <cupti_target.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
const char* metrics[] = {"dram__bytes_op_read.sum", "dram__bytes_op_write.sum", "lts__t_bytes.sum"};
std::mutex mutex;
CUpti_RangeProfiler_Object* target = nullptr;
CUpti_Profiler_Host_Object* host = nullptr;
std::vector<uint8_t> config, counters, availability;
std::string output, chip;
bool active = false, used = false;

void check(CUptiResult result, const char* operation) {
    if (result == CUPTI_SUCCESS) return;
    const char* error = nullptr;
    cuptiGetResultString(result, &error);
    throw std::runtime_error(std::string(operation) + ": " + (error ? error : "unknown CUPTI error"));
}
#define CUP(call) check((call), #call)
void driver(CUresult result, const char* operation) {
    if (result != CUDA_SUCCESS) throw std::runtime_error(std::string(operation) + " failed: " + std::to_string(result));
}
void write_blob(const std::string& path, const std::vector<uint8_t>& bytes) {
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    file.exceptions(std::ios::failbit | std::ios::badbit);
    file.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
}
[[noreturn]] void fail(const char* message) {
    std::fprintf(stderr, "fleet CUPTI failure: %s\n", message);
    std::fflush(stderr);
    // These entry points run at synchronized range boundaries. A failed
    // capture must not be mistaken for valid counter evidence by the caller.
    std::_Exit(86);
}

void begin() {
    if (active || used) throw std::runtime_error("one capture per process is required");
    const char* filename = std::getenv("STRATA_CUPTI_OUTPUT");
    if (!filename || !*filename) throw std::runtime_error("STRATA_CUPTI_OUTPUT is required");
    output = filename;
    used = true;
    CUcontext context = nullptr;
    CUdevice device = 0;
    driver(cuCtxGetCurrent(&context), "current context");
    if (!context) throw std::runtime_error("no current CUDA context");
    driver(cuCtxGetDevice(&device), "current device");
    driver(cuCtxSynchronize(), "range start synchronization");
    CUpti_Profiler_Initialize_Params init{CUpti_Profiler_Initialize_Params_STRUCT_SIZE};
    CUP(cuptiProfilerInitialize(&init));
    CUpti_Profiler_DeviceSupported_Params support{CUpti_Profiler_DeviceSupported_Params_STRUCT_SIZE};
    support.cuDevice = device;
    support.api = CUPTI_PROFILER_RANGE_PROFILING;
    CUP(cuptiProfilerDeviceSupported(&support));
    if (support.isSupported != CUPTI_PROFILER_CONFIGURATION_SUPPORTED)
        throw std::runtime_error("range profiling is unsupported on this device");
    CUpti_Device_GetChipName_Params name{CUpti_Device_GetChipName_Params_STRUCT_SIZE};
    name.deviceIndex = device;
    CUP(cuptiDeviceGetChipName(&name));
    chip = name.pChipName;
    CUpti_Profiler_GetCounterAvailability_Params avail{CUpti_Profiler_GetCounterAvailability_Params_STRUCT_SIZE};
    avail.ctx = context;
    avail.bAllowDeviceLevelCounters = 1;
    CUP(cuptiProfilerGetCounterAvailability(&avail));
    availability.resize(avail.counterAvailabilityImageSize);
    avail.pCounterAvailabilityImage = availability.data();
    CUP(cuptiProfilerGetCounterAvailability(&avail));
    CUpti_Profiler_Host_Initialize_Params hi{CUpti_Profiler_Host_Initialize_Params_STRUCT_SIZE};
    hi.profilerType = CUPTI_PROFILER_TYPE_RANGE_PROFILER;
    hi.pChipName = chip.c_str();
    hi.pCounterAvailabilityImage = availability.data();
    CUP(cuptiProfilerHostInitialize(&hi));
    host = hi.pHostObject;
    CUpti_Profiler_Host_ConfigAddMetrics_Params add{CUpti_Profiler_Host_ConfigAddMetrics_Params_STRUCT_SIZE};
    add.pHostObject = host; add.ppMetricNames = metrics; add.numMetrics = 3;
    CUP(cuptiProfilerHostConfigAddMetrics(&add));
    CUpti_Profiler_Host_GetConfigImageSize_Params size{CUpti_Profiler_Host_GetConfigImageSize_Params_STRUCT_SIZE};
    size.pHostObject = host;
    CUP(cuptiProfilerHostGetConfigImageSize(&size));
    config.resize(size.configImageSize);
    CUpti_Profiler_Host_GetConfigImage_Params image{CUpti_Profiler_Host_GetConfigImage_Params_STRUCT_SIZE};
    image.pHostObject = host; image.pConfigImage = config.data(); image.configImageSize = config.size();
    CUP(cuptiProfilerHostGetConfigImage(&image));
    CUpti_Profiler_Host_GetNumOfPasses_Params passes{CUpti_Profiler_Host_GetNumOfPasses_Params_STRUCT_SIZE};
    passes.pConfigImage = config.data(); passes.configImageSize = config.size();
    CUP(cuptiProfilerHostGetNumOfPasses(&passes));
    if (passes.numOfPasses != 1) throw std::runtime_error("metrics require more than one pass; automatic replay is forbidden");
    CUpti_RangeProfiler_Enable_Params enable{CUpti_RangeProfiler_Enable_Params_STRUCT_SIZE};
    enable.ctx = context;
    CUP(cuptiRangeProfilerEnable(&enable));
    target = enable.pRangeProfilerObject;
    CUpti_RangeProfiler_GetCounterDataSize_Params bytes{CUpti_RangeProfiler_GetCounterDataSize_Params_STRUCT_SIZE};
    bytes.pRangeProfilerObject = target; bytes.pMetricNames = metrics; bytes.numMetrics = 3;
    bytes.maxNumOfRanges = 1; bytes.maxNumRangeTreeNodes = 1;
    CUP(cuptiRangeProfilerGetCounterDataSize(&bytes));
    counters.resize(bytes.counterDataSize);
    CUpti_RangeProfiler_CounterDataImage_Initialize_Params ci{CUpti_RangeProfiler_CounterDataImage_Initialize_Params_STRUCT_SIZE};
    ci.pRangeProfilerObject = target; ci.pCounterData = counters.data(); ci.counterDataSize = counters.size();
    CUP(cuptiRangeProfilerCounterDataImageInitialize(&ci));
    CUpti_RangeProfiler_SetConfig_Params set{CUpti_RangeProfiler_SetConfig_Params_STRUCT_SIZE};
    set.pRangeProfilerObject = target; set.pConfig = config.data(); set.configSize = config.size();
    set.pCounterDataImage = counters.data(); set.counterDataImageSize = counters.size();
    set.maxRangesPerPass = 1; set.numNestingLevels = 1; set.minNestingLevel = 1;
    set.passIndex = 0; set.targetNestingLevel = 1;
    set.range = CUPTI_UserRange; set.replayMode = CUPTI_UserReplay;
    CUP(cuptiRangeProfilerSetConfig(&set));
    CUpti_RangeProfiler_Start_Params start{CUpti_RangeProfiler_Start_Params_STRUCT_SIZE};
    start.pRangeProfilerObject = target;
    CUP(cuptiRangeProfilerStart(&start));
    CUpti_RangeProfiler_PushRange_Params push{CUpti_RangeProfiler_PushRange_Params_STRUCT_SIZE};
    push.pRangeProfilerObject = target; push.pRangeName = "fleet_decode";
    CUP(cuptiRangeProfilerPushRange(&push));
    active = true;
    std::fprintf(stderr, "fleet CUPTI begin: one user range, one pass, no replay, chip=%s\n", chip.c_str());
}

void end() {
    if (!active) throw std::runtime_error("stop without active capture");
    driver(cuCtxSynchronize(), "range stop synchronization");
    CUpti_RangeProfiler_PopRange_Params pop{CUpti_RangeProfiler_PopRange_Params_STRUCT_SIZE};
    pop.pRangeProfilerObject = target;
    CUP(cuptiRangeProfilerPopRange(&pop));
    CUpti_RangeProfiler_Stop_Params stop{CUpti_RangeProfiler_Stop_Params_STRUCT_SIZE};
    stop.pRangeProfilerObject = target;
    CUP(cuptiRangeProfilerStop(&stop));
    if (!stop.isAllPassSubmitted) throw std::runtime_error("counter pass is incomplete");
    CUpti_RangeProfiler_DecodeData_Params decode{CUpti_RangeProfiler_DecodeData_Params_STRUCT_SIZE};
    decode.pRangeProfilerObject = target;
    CUP(cuptiRangeProfilerDecodeData(&decode));
    if (decode.numOfRangeDropped != 0) throw std::runtime_error("counter ranges were dropped");
    CUpti_RangeProfiler_GetCounterDataInfo_Params info{CUpti_RangeProfiler_GetCounterDataInfo_Params_STRUCT_SIZE};
    info.pCounterDataImage = counters.data(); info.counterDataImageSize = counters.size();
    CUP(cuptiRangeProfilerGetCounterDataInfo(&info));
    if (info.numTotalRanges != 1) throw std::runtime_error("expected exactly one counter range");
    double values[3]{};
    CUpti_Profiler_Host_EvaluateToGpuValues_Params eval{CUpti_Profiler_Host_EvaluateToGpuValues_Params_STRUCT_SIZE};
    eval.pHostObject = host; eval.pCounterDataImage = counters.data(); eval.counterDataImageSize = counters.size();
    eval.ppMetricNames = metrics; eval.numMetrics = 3; eval.rangeIndex = 0; eval.pMetricValues = values;
    CUP(cuptiProfilerHostEvaluateToGpuValues(&eval));
    for (double x : values) if (!std::isfinite(x) || x < 0) throw std::runtime_error("invalid counter value");
    write_blob(output + ".counterdata", counters);
    write_blob(output + ".configimage", config);
    CUpti_RangeProfiler_Disable_Params disable{CUpti_RangeProfiler_Disable_Params_STRUCT_SIZE};
    disable.pRangeProfilerObject = target;
    CUP(cuptiRangeProfilerDisable(&disable));
    target = nullptr;
    CUpti_Profiler_Host_Deinitialize_Params hd{CUpti_Profiler_Host_Deinitialize_Params_STRUCT_SIZE};
    hd.pHostObject = host;
    CUP(cuptiProfilerHostDeinitialize(&hd));
    host = nullptr;
    CUpti_Profiler_DeInitialize_Params deinit{CUpti_Profiler_DeInitialize_Params_STRUCT_SIZE};
    CUP(cuptiProfilerDeInitialize(&deinit));
    active = false;
    std::ofstream file(output, std::ios::trunc);
    file.exceptions(std::ios::failbit | std::ios::badbit);
    file << std::setprecision(17) << "{\"completed\":true,\"passes\":1,\"ranges\":1,\"dropped\":0,"
         << "\"replay\":false,\"unit\":\"byte\",\"metrics\":{";
    for (int i = 0; i < 3; ++i) file << (i ? "," : "") << '"' << metrics[i] << "\":" << values[i];
    file << "}}\n";
    file.close();
    std::fprintf(stderr, "fleet CUPTI complete: %s\n", output.c_str());
}
} // namespace

extern "C" cudaError_t CUDARTAPI cudaProfilerStart(void) {
    std::lock_guard<std::mutex> lock(mutex);
    try { begin(); return cudaSuccess; }
    catch (const std::exception& e) { fail(e.what()); }
}
extern "C" cudaError_t CUDARTAPI cudaProfilerStop(void) {
    std::lock_guard<std::mutex> lock(mutex);
    try { end(); return cudaSuccess; }
    catch (const std::exception& e) { fail(e.what()); }
}
