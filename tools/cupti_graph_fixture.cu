// A bounded reproduction of a graph whose GPU waits for its launching CPU.
// This diagnoses profiler synchronization; it is not a performance benchmark.
#include <cuda/atomic>
#include <cuda_profiler_api.h>
#include <cuda_runtime.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <vector>

struct alignas(64) Flags { unsigned request, response; };
using Atomic = cuda::atomic_ref<unsigned, cuda::thread_scope_system>;

__global__ void handshake(Flags* flags) {
    Atomic(flags->request).store(1, cuda::memory_order_release);
    while (!Atomic(flags->response).load(cuda::memory_order_acquire)) __nanosleep(100);
}

__global__ void write_payload(unsigned* data, unsigned n) {
    unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) data[i] += i ^ 0x12345678u;
}
__global__ void marker(unsigned* count) { if (threadIdx.x == 0) ++*count; }

static void ck(cudaError_t e, const char* name) {
    if (e != cudaSuccess) {
        std::fprintf(stderr, "%s: %s\n", name, cudaGetErrorString(e));
        std::exit(2);
    }
}

int main(int argc, char** argv) {
    const char* strategy = "reuse";
    bool with_handshake = true;
    unsigned nodes = 1, n = 1u << 20;
    for (int a = 1; a < argc; ++a) {
        if (!std::strcmp(argv[a], "--strategy") && a + 1 < argc) strategy = argv[++a];
        else if (!std::strcmp(argv[a], "--no-handshake")) with_handshake = false;
        else if (!std::strcmp(argv[a], "--nodes") && a + 1 < argc) nodes = (unsigned)std::strtoul(argv[++a], nullptr, 10);
        else if (!std::strcmp(argv[a], "--large-payload")) n = 1u << 27;
        else return 3;
    }
    const bool upload_once = !std::strcmp(strategy, "upload-once");
    const bool upload_each = !std::strcmp(strategy, "upload-each");
    const bool fresh_each = !std::strcmp(strategy, "fresh-each");
    if (!upload_once && !upload_each && !fresh_each && std::strcmp(strategy, "reuse")) return 3;
    std::printf("strategy=%s handshake=%d\n", strategy, (int)with_handshake);
    if (nodes < 1 || nodes > 8192) return 3;
    Flags *host, *device;
    ck(cudaHostAlloc(&host, sizeof(Flags), cudaHostAllocMapped), "host allocation");
    ck(cudaHostGetDevicePointer(&device, host, 0), "device alias");
    unsigned* data;
    unsigned* marks;
    ck(cudaMalloc(&data, n * sizeof(unsigned)), "payload allocation");
    ck(cudaMalloc(&marks, sizeof(unsigned)), "marker allocation");
    ck(cudaMemset(marks, 0, sizeof(unsigned)), "initialize marker");
    ck(cudaMemset(data, 0, n * sizeof(unsigned)), "initialize payload");
    ck(cudaDeviceSynchronize(), "initialize wait");
    cudaStream_t stream;
    ck(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking), "stream");
    cudaGraph_t graph;
    cudaGraphExec_t executable;
    ck(cudaStreamBeginCapture(stream, cudaStreamCaptureModeThreadLocal), "capture");
    if (with_handshake) handshake<<<1, 1, 0, stream>>>(device);
    for (unsigned node = 0; node < nodes; ++node) marker<<<1, 1, 0, stream>>>(marks);
    write_payload<<<n / 256, 256, 0, stream>>>(data, n);
    ck(cudaStreamEndCapture(stream, &graph), "end capture");
    ck(cudaGraphInstantiate(&executable, graph, nullptr, nullptr, 0), "instantiate");
    ck(cudaGraphUpload(executable, stream), "upload");
    ck(cudaStreamSynchronize(stream), "upload wait");
    int interventions = 0;
    for (int step = 0; step < 5; ++step) {
        if (step == 3) {
            ck(cudaProfilerStart(), "profiler start");
        }
        if (step >= 3 && fresh_each) {
            ck(cudaGraphExecDestroy(executable), "replace executable");
            ck(cudaGraphInstantiate(&executable, graph, nullptr, nullptr, 0), "fresh instantiate");
        }
        if ((step == 3 && upload_once) || (step >= 3 && (upload_each || fresh_each))) {
            // Compare one upload per range with one before every launch. A
            // fresh executable distinguishes reuse from graph instantiation.
            ck(cudaGraphUpload(executable, stream), "in-range graph upload");
            ck(cudaStreamSynchronize(stream), "in-range upload wait");
        }
        Atomic(host->request).store(0, cuda::memory_order_release);
        Atomic(host->response).store(0, cuda::memory_order_release);
        std::atomic<bool> finished{false}, intervened{false};
        // Release the GPU even if the profiler blocks cudaGraphLaunch or Query.
        // A release by this watchdog makes the fixture fail, never pass.
        std::thread watchdog([&] {
            const auto limit = std::chrono::steady_clock::now() + std::chrono::seconds(2);
            while (!finished.load() && std::chrono::steady_clock::now() < limit)
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            if (with_handshake && !finished.load()) {
                intervened.store(true);
                Atomic(host->response).store(1, cuda::memory_order_release);
            }
        });
        ck(cudaGraphLaunch(executable, stream), "launch");
        std::printf("step=%d launch_returned=1\n", step); std::fflush(stdout);
        const auto q = cudaStreamQuery(stream);
        if (q != cudaSuccess && q != cudaErrorNotReady) ck(q, "query");
        std::printf("step=%d query_returned=1\n", step); std::fflush(stdout);
        if (with_handshake) {
            while (!Atomic(host->request).load(cuda::memory_order_acquire)) std::this_thread::yield();
            Atomic(host->response).store(1, cuda::memory_order_release);
        }
        ck(cudaStreamSynchronize(stream), "graph wait");
        finished.store(true);
        watchdog.join();
        interventions += intervened.load();
        std::printf("step=%d profiled=%d watchdog=%d\n", step, step >= 3, (int)intervened.load());
        std::fflush(stdout);
    }
    ck(cudaProfilerStop(), "profiler stop");
    std::vector<unsigned> result(n);
    ck(cudaMemcpy(result.data(), data, n * sizeof(unsigned), cudaMemcpyDeviceToHost), "result");
    bool bytes_ok = true;
    for (unsigned i = 0; i < n; ++i) bytes_ok &= result[i] == 5u * (i ^ 0x12345678u);
    unsigned marker_result = 0;
    ck(cudaMemcpy(&marker_result, marks, sizeof(marker_result), cudaMemcpyDeviceToHost), "marker result");
    bytes_ok &= marker_result == 5u * nodes;
    std::printf("payload_correct=%d watchdog_interventions=%d\n", (int)bytes_ok, interventions);
    ck(cudaGraphExecDestroy(executable), "destroy executable");
    ck(cudaGraphDestroy(graph), "destroy graph");
    ck(cudaStreamDestroy(stream), "destroy stream");
    ck(cudaFree(data), "free payload");
    ck(cudaFree(marks), "free marker");
    ck(cudaFreeHost(host), "free host");
    return bytes_ok && interventions == 0 ? 0 : 4;
}
